from dotenv import load_dotenv
import json
import traceback
import time
import logging
import os
from rich.console import Console
from rich.panel import Panel
from agents import Agent, Runner, handoff, RunContextWrapper
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from datetime import datetime
import uuid
from dotenv import load_dotenv
from ..db.database import (
    get_productos,
    crear_compra,
    get_tipos_compra,
    get_reporte_ventas,
)
from ..payments.mp import create_mercadopago_link

# Configurar logging para suprimir mensajes específicos
logging.basicConfig(level=logging.ERROR)
logging.getLogger("openai").setLevel(logging.ERROR)
logging.getLogger("agents").setLevel(logging.ERROR)

# Cargar variables de entorno
load_dotenv()

# Establecer variable de entorno para desactivar trazas si no hay API key
if "OPENAI_API_KEY" not in os.environ or not os.environ["OPENAI_API_KEY"]:
    os.environ["OPENAI_API_TRACE_ENABLED"] = "false"

console = Console()

# Funciones de logging para operaciones y actividad


def log_db_operation(operation_name, start_time, success=True, result=None, error=None):
    """Registra operaciones de base de datos con formato visual"""
    elapsed = time.time() - start_time

    if success:
        console.print(
            f"[bold green]🗃️ DB OPERATION:[/] {operation_name} [dim]({elapsed:.3f}s)[/dim]"
        )
        if result:
            preview = str(result)[:100]
            if len(str(result)) > 100:
                preview += "..."
            console.print(f"[dim green]  └─ Resultado: {preview}[/dim]")
    else:
        console.print(
            f"[bold red]❌ DB ERROR:[/] {operation_name} [dim]({elapsed:.3f}s)[/dim]"
        )
        if error:
            console.print(f"[dim red]  └─ Error: {str(error)}[/dim]")


def log_agent_activity(context, agent_name, activity_type, details=None):
    """Registra y visualiza actividad de agentes en el sistema"""
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]

    # Colores según tipo de actividad
    styles = {
        "started": {"icon": "▶️", "color": "blue"},
        "thinking": {"icon": "💭", "color": "yellow"},
        "action": {"icon": "⚙️", "color": "cyan"},
        "completed": {"icon": "✅", "color": "green"},
        "error": {"icon": "❌", "color": "red"},
    }

    style = styles.get(activity_type, {"icon": "ℹ️", "color": "white"})

    console.print(
        f"[{style['color']}]{style['icon']} {timestamp} | {agent_name}[/{style['color']}]: ",
        end="",
    )

    if activity_type == "started":
        console.print(f"[bold {style['color']}]Iniciando procesamiento[/]")
    elif activity_type == "thinking":
        console.print(f"[italic {style['color']}]Analizando '{details}'[/]")
    elif activity_type == "action":
        console.print(f"[bold {style['color']}]Ejecutando {details}[/]")
    elif activity_type == "completed":
        console.print(f"[bold {style['color']}]Procesamiento completado[/]")
    elif activity_type == "error":
        console.print(f"[bold {style['color']}]Error: {details}[/]")
    else:
        console.print(f"{details}")

    # Podemos registrar la actividad en el contexto para análisis posterior
    if hasattr(context, "activity_log") and isinstance(context.activity_log, list):
        context.activity_log.append(
            {
                "timestamp": timestamp,
                "agent": agent_name,
                "type": activity_type,
                "details": details,
            }
        )


HANDOFF_PROMPT_PREFIX = """
When you need specialized help, you can transfer the conversation to another agent.
Available specialist agents:
- ProductAgent: Searches and validates product information
- SalesAgent: Generates payment links and processes orders

To transfer, use the appropriate handoff tool when the user's request requires specialized knowledge.
"""


@dataclass
class OrderItem:
    producto: str
    cantidad: int
    precio_unitario: Optional[float] = None


@dataclass
class ChatContext:
    uid: str = field(default_factory=lambda: str(uuid.uuid4()))
    messages: List[Dict[str, Any]] = field(default_factory=list)
    current_order: Dict[str, OrderItem] = field(default_factory=dict)

    def add_message(self, role: str, content: str) -> None:
        self.messages.append({"role": role, "content": content})

    def get_messages(self) -> List[Dict[str, Any]]:
        return self.messages


class HandoffData(BaseModel):
    """Información para transferencias entre agentes"""

    prompt: str
    context_data: Optional[Dict[str, Any]] = None
    to_agent: Optional[str] = None  # Add target agent name

    class Config:
        arbitrary_types_allowed = True


async def on_handoff(
    ctx: RunContextWrapper[ChatContext], input_data: HandoffData
) -> None:
    """Función para registrar handoffs entre agentes con visualización mejorada"""
    # Obtener información de los agentes
    from_agent = (
        getattr(ctx.agent, "name", "Desconocido")
        if hasattr(ctx, "agent")
        else "Desconocido"
    )
    to_agent = (
        getattr(input_data, "to_agent", "Desconocido")
        if hasattr(input_data, "to_agent")
        else "Target Agent"
    )

    # Crear un estilo según el tipo de agente
    agent_styles = {
        "Main Agent": {"icon": "🧠", "color": "bold cyan"},
        "Product Agent": {"icon": "🔍", "color": "bold green"},
        "Sales Agent": {"icon": "💰", "color": "bold yellow"},
    }

    from_style = agent_styles.get(from_agent, {"icon": "👤", "color": "bold white"})
    to_style = agent_styles.get(to_agent, {"icon": "👤", "color": "bold white"})

    # Crear separador visual
    console.print("\n" + "─" * 80 + "\n")

    # Mostrar el handoff con formato atractivo
    console.print(
        f"[{from_style['color']}]{from_style['icon']} {from_agent}[/] [bold magenta]→ TRANSFIRIENDO A →[/] [{to_style['color']}]{to_style['icon']} {to_agent}[/]"
    )

    # Mostrar datos que se transfieren
    if hasattr(input_data, "prompt") and input_data.prompt:
        console.print(
            Panel(
                input_data.prompt,
                title="💬 Mensaje Enviado",
                border_style="blue",
                expand=False,
            )
        )

    if hasattr(input_data, "context_data") and input_data.context_data:
        console.print(
            Panel(
                json.dumps(input_data.context_data, indent=2, ensure_ascii=False),
                title="📋 Datos de Contexto",
                border_style="green",
                expand=False,
            )
        )

    # Mostrar estado de la orden actual si existe
    if (
        hasattr(ctx, "context")
        and hasattr(ctx.context, "current_order")
        and ctx.context.current_order
    ):
        console.print(
            Panel(
                "\n".join(
                    [
                        f"{k}: {v.cantidad}x ${v.precio_unitario}"
                        for k, v in ctx.context.current_order.items()
                    ]
                ),
                title="🛒 Orden Actual",
                border_style="yellow",
                expand=False,
            )
        )


class Agents:
    def __init__(self) -> None:
        self.productsagent = Agent(
            name="Product Agent",
            instructions="""Eres un experto buscador de productos que habla con personalidad entusiasta y detallista.

    SIEMPRE COMUNICA CON ESTA PERSONALIDAD:
    - Entusiasta por los productos ("¡Excelente elección!")
    - Detallista con la información ("He encontrado todos los datos exactos")
    - Eficiente y preciso ("Búsqueda completada en la base de datos")
    - Usa ocasionalmente emojis relevantes como 🔍, 📊, 🏷️

    CORE RESPONSIBILITIES:
    1. ALWAYS call get_productos() FIRST for EVERY request
    2. Find the best matching product from database results
    3. Return EXACT database information in structured format
    4. NEVER invent or modify any product information

    WORKFLOW:
    1. FIRST ACTION: Call get_productos() to get all products
    2. Search for the best match using these rules:
       - Exact matches first (e.g. "pizza muzzarella" = "pizza muzzarella")
       - Then partial matches (e.g. "muzza" matches "pizza muzzarella")
       - Then variations (e.g. "pizza de muzza" matches "pizza muzzarella")
    3. When found, ALWAYS return in EXACT format:
       "PRODUCT_INFO: [exact_db_name] | PRICE: $[exact_db_price] | DESC: [exact_db_description] | ID: [exact_db_id] | DB_MATCH: true"
    4. If no match found:
       "NO_MATCH: Could not find product matching [query]"
    """,
            tools=[get_productos],
            model="o3-mini",
        )
        self.products_handoff = handoff(
            agent=self.productsagent,
            on_handoff=on_handoff,
            input_type=HandoffData,
        )
        self.salesagent = Agent(
            name="Sales Agent",
            instructions="""Eres un profesional procesador de pagos que habla con personalidad servicial y segura.

    SIEMPRE COMUNICA CON ESTA PERSONALIDAD:
    - Servicial y atento ("Estoy procesando su pago")
    - Preciso con los detalles financieros ("El total de su orden es exactamente...")
    - Tranquilizador y confiable ("Su transacción está siendo procesada de manera segura")
    - Usa ocasionalmente emojis relevantes como 💰, 💳, 🔒

    CORE RESPONSIBILITIES:
    1. FIRST ACTION: Call create_mercadopago_link with exact order total
    2. Return payment information in structured format
    3. NEVER modify order totals
    4. ALWAYS include payment link in response
    5. ALWAYS register the purchase in the database

    WORKFLOW:
    1. Receive order total from Main Agent
    2. IMMEDIATELY call create_mercadopago_link with:
       - amount: Exact order total
       - title: "Pedido #[timestamp]"
       - description: "Orden de comida"
    3. Get tipo_compra ID for "Mercado Pago" using get_tipos_compra()
    4. Register purchase in database by calling crear_compra with:
       - monto_total: Exact order total
       - tipo_compra_id: ID for "Mercado Pago" payment type
       - productos: List of product IDs with quantities
       - fecha: current timestamp
    5. ALWAYS return in EXACT format:
       "PAYMENT_INFO: Total: $[amount] | Link: [mercadopago_link] | Order_ID: [timestamp]"
    """,
            tools=[
                create_mercadopago_link,
                crear_compra,
                get_tipos_compra,
                get_reporte_ventas,
            ],
            model="o3-mini",
            handoffs=[self.products_handoff],
        )
        self.sales_handoff = handoff(
            agent=self.salesagent,
            on_handoff=on_handoff,
            input_type=HandoffData,
        )
        self.mainagent = Agent(
            name="Main Agent",
            instructions=f"""
            {HANDOFF_PROMPT_PREFIX}

            Eres el coordinador principal que maneja todas las interacciones con el cliente con personalidad amigable y atenta.

            SIEMPRE COMUNICA CON ESTA PERSONALIDAD:
            - Amigable y cercano ("¡Hola! Encantado de atenderte")
            - Paciente y claro ("Permíteme explicarte las opciones")
            - Servicial y orientado al cliente ("Estoy aquí para ayudarte")
            - Usa emojis relevantes como 🍕, 👋, 😊, ✅

            PROCEDIMIENTO PARA LLAMAR A OTROS AGENTES:
            - Cuando el cliente menciona un producto: "Permíteme consultar ese producto..." → llama a Product Agent
            - Cuando confirma la orden: "Voy a procesar tu pago..." → llama a Sales Agent
            - Siempre comunica el proceso: "Estoy verificando / procesando / consultando..."

            CORE RESPONSIBILITIES:
            1. Understand customer food orders in natural language
            2. Query the Product Agent to get accurate product details
            3. Maintain the current order state (products, prices, totals)
            4. Coordinate with Sales Agent to generate payment links

            WORKFLOW WITH OTHER AGENTS:
            - When customers mention a food item (like "pizza"), ALWAYS delegate to Product Agent first
            - When customer confirms the order, delegate to Sales Agent to create payment link
            - You must follow the proper sequence: Product Agent → confirm order → Sales Agent

            PRODUCT LOOKUP PROCESS:
            1. When customer mentions food items, immediately call the Product Agent
            2. Product Agent will search the database and respond in this format:
            "PRODUCT_INFO: [name] | PRICE: $[price] | DESC: [desc] | ID: [id] | DB_MATCH: true"
            OR "NO_MATCH: Could not find product matching [query]"
            3. For successful matches, extract and store:
            - Exact name, price, ID from database response
            - Mark as validated (db_match = true, price_confirmed = true)
            4. For NO_MATCH responses:
            - Inform customer the item wasn't found
            - Suggest alternatives or ask for clarification

            ORDER MANAGEMENT:
            1. Maintain a clear list of all validated items in the current order
            2. Allow customers to add multiple items before checkout
            3. Support commands like "añadir otro/una", "eliminar", "ver mi orden"
            4. Before checkout, verify all products have confirmed prices and valid database IDs
            5. Calculate the total order amount using only confirmed prices

            PAYMENT PROCESS:
            1. When customer confirms the order, calculate the total amount
            2. Delegate to Sales Agent with the verified total amount
            3. Sales Agent will respond with:
            "PAYMENT_INFO: Total: $[amount] | Link: [link] | Order_ID: [id]"
            4. Extract the payment link and present it to the customer
            5. After payment is complete, thank the customer for their order

            CONVERSATION STYLE:
            - Use friendly, helpful Spanish language appropriate for a food service
            - Be concise but clear in your communications
            - Use emojis occasionally for a friendly touch (🍕, 👍, etc.)
            - Always maintain a professional but warm tone

            EXAMPLE INTERACTIONS:
            Customer: "Quiero una pizza de muzzarella"
            You: → Call Product Agent
            Product Agent: "PRODUCT_INFO: Pizza muzzarella | PRICE: $10.00 | DESC: Pizza con queso muzzarella | ID: b301e81a-6d3e-4d4d-ab4e-28e88002c10e | DB_MATCH: true"
            You: "¡Perfecto! 🍕 He agregado una Pizza muzzarella a tu orden por $10.00. ¿Deseas ordenar algo más o proceder con el pago?"

            Customer: "Quiero agregar una gaseosa"
            You: → Call Product Agent
            Product Agent: "PRODUCT_INFO: Coca-Cola 500ml | PRICE: $3.50 | DESC: Bebida gaseosa | ID: d45e81a-9f3e-8d9d-cd4e-12e88042a45e | DB_MATCH: true"
            You: "¡Excelente! He agregado una Coca-Cola 500ml por $3.50 a tu orden. Tu total actual es $13.50. ¿Algo más o procedemos al pago?"

            Customer: "Eso es todo, quiero pagar"
            You: → Verify all products have db_match=true and price_confirmed=true
            You: → Call Sales Agent with total amount $13.50
            Sales Agent: "PAYMENT_INFO: Total: $13.50 | Link: https://mp.com/xyz123 | Order_ID: 456"
            You: "¡Genial! 👍 Aquí está tu link de pago por $13.50: https://mp.com/xyz123
            Una vez realizado el pago, tu pedido será procesado. ¡Gracias por tu orden!"

            ERROR HANDLING:
            - If product not found: Ask customer for alternative options or clarification
            - If price not confirmed: Retry with Product Agent, never proceed with unconfirmed prices
            - If payment link fails: Inform customer and retry with Sales Agent
            - Always show specific error details to help customer understand the issue

            IMPORTANT TECHNICAL CHECKS:
            - ALWAYS validate db_match = true before confirming prices
            - NEVER proceed with unconfirmed prices
            - ALWAYS verify database IDs exist for all products
            - ALWAYS extract and display the payment link exactly as provided by Sales Agent
            """,
            model="o3-mini",
            handoffs=[self.salesagent, self.productsagent],
        )
        self.current_conversations = []
        self.conversation_history = []

    async def run(self, prompt: str, context: Optional[ChatContext] = None) -> str:
        """Ejecuta el agente principal con el prompt del usuario"""
        if context is None:
            context = ChatContext()
            console.print(
                f"[bold blue]✨ Creando nuevo contexto con ID:[/] {context.uid}"
            )
        else:
            console.print(
                f"[bold green]🔄 Continuando conversación con ID:[/] {context.uid}"
            )

        # Añadir el mensaje del usuario
        context.add_message("user", prompt)

        try:
            # Visualizar la ejecución con estilo
            console.print("\n" + "═" * 80)
            console.print(
                Panel(
                    f"[italic]{prompt}[/]",
                    title="👤 USUARIO PREGUNTA",
                    subtitle=datetime.now().strftime("%H:%M:%S"),
                    border_style="blue",
                    expand=False,
                )
            )

            # Notificación manual de inicio del agente principal
            self._trace_callback(
                {"type": "agent_started", "agent": {"name": "Main Agent"}}
            )

            # Lógica de ejecución existente...
            if len(context.get_messages()) <= 1:
                console.print(
                    "[yellow]Primer mensaje en la conversación, ejecutando con prompt simple[/]"
                )

                # Notificación manual antes de cada operación
                console.print(
                    f"[bold cyan]🔄 Iniciando ejecución del Agente Principal[/]"
                )

                result = await Runner.run(
                    starting_agent=self.mainagent,
                    input=prompt,
                    context=context,
                )
            else:
                console.print(
                    f"[yellow]Mensaje subsecuente, ejecutando con historial completo ({len(context.get_messages())} mensajes)[/]"
                )

                # Notificación manual antes de cada operación
                console.print(
                    f"[bold cyan]🔄 Iniciando ejecución del Agente Principal con contexto completo[/]"
                )

                result = await Runner.run(
                    starting_agent=self.mainagent,
                    input=context.get_messages(),
                    context=context,
                )

            # Notificación manual de finalización del agente principal
            self._trace_callback(
                {"type": "agent_finished", "agent": {"name": "Main Agent"}}
            )

            # Transformar la respuesta antes de mostrarla (solo para visualización en consola)
            final_output = result.final_output
            display_output = final_output
            humanized_output = final_output

            # Verificar si la respuesta contiene formatos técnicos y transformarla para visualización
            if "PRODUCT_INFO:" in final_output:
                # Extraer información del producto
                try:
                    product_parts = final_output.split("|")
                    product_name = product_parts[0].replace("PRODUCT_INFO:", "").strip()
                    price = product_parts[1].replace("PRICE:", "").strip()

                    display_output = f"¡Excelente elección! 🍕 He agregado {product_name} por {price} a tu orden. ¿Deseas agregar algo más o proceder con el pago?"
                    humanized_output = display_output
                except Exception:
                    # Si hay error al interpretar, usar la respuesta original
                    pass

            elif "PAYMENT_INFO:" in final_output:
                # Extraer información de pago
                try:
                    payment_parts = final_output.split("|")
                    total = payment_parts[0].replace("PAYMENT_INFO: Total:", "").strip()
                    link = payment_parts[1].replace("Link:", "").strip()
                    order_id = (
                        payment_parts[2].replace("Order_ID:", "").strip()
                        if len(payment_parts) > 2
                        else ""
                    )

                    display_output = f"¡Tu orden está lista para pagar! 👍\n\n💰 Total a pagar: {total}\n\n🔗 Link de pago: {link}\n\n🧾 Número de orden: {order_id}\n\n¿Hay algo más en lo que pueda ayudarte?"
                    humanized_output = display_output
                except Exception:
                    # Si hay error al interpretar, usar la respuesta original
                    pass

            # Mostrar la respuesta con estilo (versión humanizada)
            console.print("\n" + "═" * 80)
            console.print(
                Panel(
                    display_output,
                    title="🧠 RESPUESTA FINAL",
                    subtitle=datetime.now().strftime("%H:%M:%S"),
                    border_style="green",
                    expand=False,
                )
            )

            # También mostrar la versión técnica para depuración
            if display_output != final_output:
                console.print(
                    Panel(
                        final_output,
                        title="🔍 RESPUESTA TÉCNICA (DEBUG)",
                        border_style="dim",
                        expand=False,
                    )
                )

            # Visualizar estado final de la orden después de la ejecución
            if context.current_order:
                order_items = [
                    f"{k}: {v.cantidad}x ${v.precio_unitario}"
                    for k, v in context.current_order.items()
                ]
                console.print(
                    Panel(
                        "\n".join(order_items),
                        title="🛒 ESTADO ACTUAL DE LA ORDEN",
                        border_style="blue",
                        expand=False,
                    )
                )

            # Mostrar información resumida sobre handoffs
            if hasattr(result, "trace") and result.trace:
                handoffs = (
                    result.trace.handoffs if hasattr(result.trace, "handoffs") else []
                )
                if handoffs:
                    console.print(
                        Panel(
                            f"Se realizaron {len(handoffs)} transferencias entre agentes",
                            title="🔄 RESUMEN DE TRANSFERENCIAS",
                            border_style="magenta",
                            expand=False,
                        )
                    )

            # Guardamos la respuesta original en los mensajes para mantener la integridad del contexto
            context.add_message("assistant", result.final_output)

            # Retornamos la versión humanizada para el usuario en la interfaz
            return humanized_output

        except Exception as e:
            error_message = f"Error: {str(e)}"
            console.print(
                Panel(
                    f"{error_message}\n\n{traceback.format_exc()}",
                    title="❌ ERROR EN EJECUCIÓN",
                    border_style="red",
                    expand=False,
                )
            )
            context.add_message("system", error_message)
            return error_message

    def _trace_callback(self, event):
        """Callback para mostrar eventos durante la ejecución"""
        if isinstance(event, dict):
            event_type = event.get("type")

            if event_type == "agent_started":
                agent_name = event.get("agent", {}).get("name", "Desconocido")
                console.print(f"[bold cyan]🔄 Agente iniciado: {agent_name}[/]")

            elif event_type == "agent_finished":
                agent_name = event.get("agent", {}).get("name", "Desconocido")
                console.print(f"[bold green]✅ Agente completado: {agent_name}[/]")

            elif event_type == "tool_started":
                tool_name = event.get("tool_name", "Desconocido")
                console.print(f"[bold yellow]🔧 Ejecutando herramienta: {tool_name}[/]")

            elif event_type == "tool_finished":
                tool_name = event.get("tool_name", "Desconocido")
                console.print(f"[bold blue]🔧 Herramienta completada: {tool_name}[/]")

            elif event_type == "handoff_started":
                target_agent_name = event.get("target_agent", {}).get(
                    "name", "Desconocido"
                )
                console.print(
                    f"[bold magenta]🔄 Iniciando transferencia a: {target_agent_name}[/]"
                )
        else:
            # Si no es un diccionario, intentamos manejarlo como objeto
            try:
                if hasattr(event, "type"):
                    if event.type == "agent_started":
                        console.print(
                            f"[bold cyan]🔄 Agente iniciado: {event.agent.name if hasattr(event, 'agent') and hasattr(event.agent, 'name') else 'Desconocido'}[/]"
                        )

                    elif event.type == "agent_finished":
                        console.print(
                            f"[bold green]✅ Agente completado: {event.agent.name if hasattr(event, 'agent') and hasattr(event.agent, 'name') else 'Desconocido'}[/]"
                        )

                    elif event.type == "tool_started":
                        console.print(
                            f"[bold yellow]🔧 Ejecutando herramienta: {event.tool_name if hasattr(event, 'tool_name') else 'Desconocido'}[/]"
                        )

                    elif event.type == "tool_finished":
                        console.print(
                            f"[bold blue]🔧 Herramienta completada: {event.tool_name if hasattr(event, 'tool_name') else 'Desconocido'}[/]"
                        )

                    elif event.type == "handoff_started":
                        console.print(
                            f"[bold magenta]🔄 Iniciando transferencia a: {event.target_agent.name if hasattr(event, 'target_agent') and hasattr(event.target_agent, 'name') else 'Desconocido'}[/]"
                        )
            except Exception as e:
                console.print(f"[dim red]Error procesando evento: {str(e)}[/dim red]")
