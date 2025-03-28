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
Cuando necesites ayuda especializada, puedes transferir la conversación a otro agente.
Agentes especialistas disponibles:
- ProductAgent: Busca y valida información de productos
- SalesAgent: Genera enlaces de pago y procesa pedidos

Para transferir, usa la herramienta de transferencia adecuada cuando la solicitud del usuario requiera conocimientos especializados.
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

    RESPONSABILIDADES PRINCIPALES:
    1. SIEMPRE llama a get_productos() PRIMERO para CADA solicitud
    2. Encuentra el mejor producto coincidente de los resultados de la base de datos
    3. Devuelve la información EXACTA de la base de datos en formato estructurado
    4. NUNCA inventes o modifiques información de productos

    FLUJO DE TRABAJO:
    1. PRIMERA ACCIÓN: Llama a get_productos() para obtener todos los productos
    2. Busca la mejor coincidencia usando estas reglas:
       - Coincidencias exactas primero (ej. "pizza muzzarella" = "pizza muzzarella")
       - Luego coincidencias parciales (ej. "muzza" coincide con "pizza muzzarella")
       - Luego variaciones (ej. "pizza de muzza" coincide con "pizza muzzarella")
    3. Cuando se encuentre, SIEMPRE devolver en formato EXACTO:
       "PRODUCT_INFO: [nombre_exacto_db] | PRICE: $[precio_exacto_db] | DESC: [descripcion_exacta_db] | ID: [id_exacto_db] | DB_MATCH: true"
    4. Si no se encuentra coincidencia:
       "NO_MATCH: No se pudo encontrar un producto que coincida con [consulta]"
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

    RESPONSABILIDADES PRINCIPALES:
    1. PRIMERA ACCIÓN: Llamar a create_mercadopago_link con el monto exacto del pedido
    2. Devolver información de pago en formato estructurado
    3. NUNCA modificar los totales del pedido
    4. SIEMPRE incluir el enlace de pago en la respuesta
    5. SIEMPRE registrar la compra en la base de datos

    FLUJO DE TRABAJO:
    1. Recibir el monto total del pedido del Agente Principal
    2. INMEDIATAMENTE llamar a create_mercadopago_link con:
       - amount: Monto exacto del pedido
       - title: "Pedido #[timestamp]"
       - description: "Orden de comida"
    3. Obtener ID del tipo_compra para "Mercado Pago" usando get_tipos_compra()
       - Buscar el ID donde nombre es "Mercado Pago" o la coincidencia más cercana
    4. Registrar la compra en la base de datos llamando a crear_compra con:
       - monto: Monto exacto del pedido (NO monto_total)
       - tipo_compra_id: ID del tipo de pago "Mercado Pago"
       - productos: Lista de IDs de productos con cantidades
    5. SIEMPRE devolver en formato EXACTO:
       "PAYMENT_INFO: Total: $[monto] | Link: [mercadopago_link] | Order_ID: [timestamp]"

    DETALLES TÉCNICOS:
    1. La función crear_compra espera estos campos EXACTOS:
       - monto: float (monto total)
       - tipo_compra_id: string (UUID del tipo de pago)
       - productos: array de objetos con:
         * producto_id: string (UUID del producto)
         * cantidad: integer (cantidad)
         * precio_unitario: float (precio unitario)
    2. Cuando no se encuentra el ID de tipo_compra para "Mercado Pago", usar cualquier ID disponible
       O devolver mensaje de error pero IGUALMENTE incluir el enlace de pago
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

            RESPONSABILIDADES PRINCIPALES:
            1. Entender los pedidos de comida del cliente en lenguaje natural
            2. Consultar al Agente de Productos para obtener detalles precisos del producto
            3. Mantener el estado actual del pedido (productos, precios, totales)
            4. Coordinar con el Agente de Ventas para generar enlaces de pago

            FLUJO DE TRABAJO CON OTROS AGENTES:
            - Cuando los clientes mencionan un alimento (como "pizza"), SIEMPRE delega primero al Agente de Productos
            - Cuando el cliente confirma el pedido, delega al Agente de Ventas para crear el enlace de pago
            - Debes seguir la secuencia adecuada: Agente de Productos → confirmar pedido → Agente de Ventas

            PROCESO DE BÚSQUEDA DE PRODUCTOS:
            1. Cuando el cliente menciona alimentos, llama inmediatamente al Agente de Productos
            2. El Agente de Productos buscará en la base de datos y responderá en este formato:
            "PRODUCT_INFO: [nombre] | PRICE: $[precio] | DESC: [desc] | ID: [id] | DB_MATCH: true"
            O "NO_MATCH: No se pudo encontrar un producto que coincida con [consulta]"
            3. Para coincidencias exitosas, extrae y almacena:
            - Nombre exacto, precio, ID de la respuesta de la base de datos
            - Marcar como validado (db_match = true, price_confirmed = true)
            4. Para respuestas NO_MATCH:
            - Informar al cliente que no se encontró el artículo
            - Sugerir alternativas o pedir aclaraciones

            GESTIÓN DE PEDIDOS:
            1. Mantener una lista clara de todos los artículos validados en el pedido actual
            2. Permitir a los clientes agregar múltiples artículos antes de pagar
            3. Soportar comandos como "añadir otro/una", "eliminar", "ver mi orden"
            4. Antes de pagar, verificar que todos los productos tengan precios confirmados e IDs válidos de base de datos
            5. Calcular el monto total del pedido usando solo precios confirmados

            PROCESO DE PAGO:
            1. Cuando el cliente confirma el pedido, calcula el monto total
            2. Delegar al Agente de Ventas con el monto total verificado
            3. El Agente de Ventas responderá con:
            "PAYMENT_INFO: Total: $[monto] | Link: [enlace] | Order_ID: [id]"
            4. Extraer el enlace de pago y presentarlo al cliente
            5. Después de completar el pago, agradecer al cliente por su pedido

            ESTILO DE CONVERSACIÓN:
            - Usar lenguaje español amigable y útil apropiado para un servicio de comida
            - Ser conciso pero claro en tus comunicaciones
            - Usar emojis ocasionalmente para dar un toque amigable (🍕, 👍, etc.)
            - Mantener siempre un tono profesional pero cálido

            EJEMPLOS DE INTERACCIONES:
            Cliente: "Quiero una pizza de muzzarella"
            Tú: → Llamar al Agente de Productos
            Agente de Productos: "PRODUCT_INFO: Pizza muzzarella | PRICE: $10.00 | DESC: Pizza con queso muzzarella | ID: b301e81a-6d3e-4d4d-ab4e-28e88002c10e | DB_MATCH: true"
            Tú: "¡Perfecto! 🍕 He agregado una Pizza muzzarella a tu orden por $10.00. ¿Deseas ordenar algo más o proceder con el pago?"

            Cliente: "Quiero agregar una gaseosa"
            Tú: → Llamar al Agente de Productos
            Agente de Productos: "PRODUCT_INFO: Coca-Cola 500ml | PRICE: $3.50 | DESC: Bebida gaseosa | ID: d45e81a-9f3e-8d9d-cd4e-12e88042a45e | DB_MATCH: true"
            Tú: "¡Excelente! He agregado una Coca-Cola 500ml por $3.50 a tu orden. Tu total actual es $13.50. ¿Algo más o procedemos al pago?"

            Cliente: "Eso es todo, quiero pagar"
            Tú: → Verificar que todos los productos tengan db_match=true y price_confirmed=true
            Tú: → Llamar al Agente de Ventas con monto total $13.50
            Agente de Ventas: "PAYMENT_INFO: Total: $13.50 | Link: https://mp.com/xyz123 | Order_ID: 456"
            Tú: "¡Genial! 👍 Aquí está tu link de pago por $13.50: https://mp.com/xyz123
            Una vez realizado el pago, tu pedido será procesado. ¡Gracias por tu orden!"

            MANEJO DE ERRORES:
            - Si no se encuentra el producto: Pedir al cliente opciones alternativas o aclaraciones
            - Si el precio no está confirmado: Reintentar con el Agente de Productos, nunca proceder con precios no confirmados
            - Si falla el enlace de pago: Informar al cliente y reintentar con el Agente de Ventas
            - Siempre mostrar detalles específicos de error para ayudar al cliente a entender el problema

            VERIFICACIONES TÉCNICAS IMPORTANTES:
            - SIEMPRE validar db_match = true antes de confirmar precios
            - NUNCA proceder con precios no confirmados
            - SIEMPRE verificar que existan IDs de base de datos para todos los productos
            - SIEMPRE extraer y mostrar el enlace de pago exactamente como lo proporciona el Agente de Ventas
            """,
            model="o3-mini",
            handoffs=[self.salesagent, self.productsagent],
        )
        self.current_conversations = []
        self.conversation_history = []

    async def run(self, text, context=None):
        """Ejecuta el agente con el texto proporcionado y retorna su respuesta"""
        # Inicializar el contexto si no se ha proporcionado
        if context is None:
            context = {"messages": []}
            is_dict_context = True
        else:
            # Detectar si el contexto es un diccionario o un objeto ChatContext
            is_dict_context = not hasattr(context, "add_message")

        # Agregar el mensaje a la conversación
        if is_dict_context:
            # Si es un diccionario, agregar mensaje directamente
            context["messages"].append({"role": "user", "content": text})
            message_count = len(context["messages"])
        else:
            # Si es un objeto ChatContext, usar su método
            context.add_message("user", text)
            message_count = len(context.get_messages())

        # Notificación manual de inicio del agente principal
        self._trace_callback({"type": "agent_started", "agent": {"name": "Main Agent"}})

        # Determinar si es el primer mensaje o un mensaje subsecuente
        if message_count == 1:
            result = await Runner.run(
                starting_agent=self.mainagent, input=text, context=context
            )
        else:
            # Preparar el contexto adecuado para el agente
            if is_dict_context:
                agent_context = {"messages": context["messages"]}
            else:
                agent_context = context.get_messages()

            result = await Runner.run(
                starting_agent=self.mainagent, input=agent_context, context=context
            )

        # Notificación manual de finalización del agente principal
        self._trace_callback(
            {"type": "agent_finished", "agent": {"name": "Main Agent"}}
        )

        # Obtener la respuesta final
        response = (
            result.final_output if hasattr(result, "final_output") else str(result)
        )

        # Procesar la respuesta para mostrarla de forma más amigable
        final_output = response
        humanized_output = ""

        # Transformar la salida del agente si contiene información específica
        if isinstance(response, str) and (
            "PRODUCT_INFO:" in response or "PAYMENT_INFO:" in response
        ):
            # Intentar extraer información de productos
            if "PRODUCT_INFO:" in response:
                try:
                    # Intentar procesar formato antiguo con | como separador
                    if "|" in response:
                        product_parts = response.split("|")
                        product_name = (
                            product_parts[0].replace("PRODUCT_INFO:", "").strip()
                        )
                        price = product_parts[1].replace("PRICE:", "").strip()
                        humanized_output = f"¡Excelente elección! 🍕 He agregado {product_name} por {price} a tu orden. ¿Deseas agregar algo más o proceder con el pago?"
                    # Intentar formato JSON
                    else:
                        products_info = (
                            response.split("PRODUCT_INFO:")[1].split("\n")[0].strip()
                        )
                        products_data = json.loads(products_info)
                        humanized_output += "📋 Productos seleccionados:\n"
                        for product in products_data:
                            humanized_output += (
                                f"- {product['name']}: ${product['price']}\n"
                            )
                        humanized_output += "\n"
                except Exception:
                    # Si hay error al interpretar, usar la respuesta original
                    pass

            # Intentar extraer información de pago
            if "PAYMENT_INFO:" in response:
                try:
                    # Intentar procesar formato antiguo con | como separador
                    if "|" in response:
                        payment_parts = response.split("|")
                        total = (
                            payment_parts[0].replace("PAYMENT_INFO: Total:", "").strip()
                        )
                        link = payment_parts[1].replace("Link:", "").strip()
                        order_id = (
                            payment_parts[2].replace("Order_ID:", "").strip()
                            if len(payment_parts) > 2
                            else ""
                        )

                        # Verificar si hay mensaje de error en la respuesta
                        error_message = ""
                        if "Error al crear compra:" in response:
                            error_message = "\n\n⚠️ Nota: Hubo un pequeño inconveniente técnico al registrar la compra en nuestra base de datos, pero no te preocupes. Tu pago y pedido se procesarán correctamente."

                        humanized_output = f"¡Tu orden está lista para pagar! 👍\n\n💰 Total a pagar: {total}\n\n🔗 Link de pago: {link}\n\n🧾 Número de orden: {order_id}{error_message}\n\n¿Hay algo más en lo que pueda ayudarte?"
                    # Intentar formato JSON
                    else:
                        payment_info = response.split("PAYMENT_INFO:")[1].strip()
                        payment_data = json.loads(payment_info)
                        humanized_output += "💰 Información de pago:\n"
                        humanized_output += (
                            f"- Total: ${payment_data.get('total', 'N/A')}\n"
                        )
                        humanized_output += f"- Link de pago: {payment_data.get('payment_link', 'N/A')}\n"
                        humanized_output += (
                            f"- ID de orden: {payment_data.get('order_id', 'N/A')}\n"
                        )
                except Exception:
                    # Si hay error al interpretar, usar la respuesta original
                    pass

        # Si tenemos una versión humanizada, mostrarla
        if humanized_output:
            console.print("\n[bold green]RESPUESTA FINAL:[/]")
            console.print(humanized_output)
        else:
            console.print("\n[bold green]RESPUESTA FINAL:[/]")
            console.print(response)

        # Almacenar la respuesta en el contexto
        if is_dict_context:
            context["messages"].append({"role": "assistant", "content": response})
        else:
            context.add_message("assistant", response)

        return response

    def _trace_callback(self, event):
        """Callback para mostrar eventos durante la ejecución"""
        if isinstance(event, dict):
            event_type = event.get("type")

            if event_type == "agent_started":
                agent_name = event.get("agent", {}).get("name", "Desconocido")
                # console.print(f"[bold cyan]🔄 Agente iniciado: {agent_name}[/]")
                pass

            elif event_type == "agent_finished":
                agent_name = event.get("agent", {}).get("name", "Desconocido")
                # console.print(f"[bold green]✅ Agente completado: {agent_name}[/]")
                pass

            elif event_type == "tool_started":
                tool_name = event.get("tool_name", "Desconocido")
                # console.print(f"[bold yellow]🔧 Ejecutando herramienta: {tool_name}[/]")
                pass

            elif event_type == "tool_finished":
                tool_name = event.get("tool_name", "Desconocido")
                # console.print(f"[bold blue]🔧 Herramienta completada: {tool_name}[/]")
                pass

            elif event_type == "handoff_started":
                target_agent_name = event.get("target_agent", {}).get(
                    "name", "Desconocido"
                )
                # console.print(
                #     f"[bold magenta]🔄 Iniciando transferencia a: {target_agent_name}[/]"
                # )
                pass
        else:
            # Si no es un diccionario, intentamos manejarlo como objeto
            try:
                if hasattr(event, "type"):
                    if event.type == "agent_started":
                        # console.print(
                        #     f"[bold cyan]🔄 Agente iniciado: {event.agent.name if hasattr(event, 'agent') and hasattr(event.agent, 'name') else 'Desconocido'}[/]"
                        # )
                        pass

                    elif event.type == "agent_finished":
                        # console.print(
                        #     f"[bold green]✅ Agente completado: {event.agent.name if hasattr(event, 'agent') and hasattr(event.agent, 'name') else 'Desconocido'}[/]"
                        # )
                        pass

                    elif event.type == "tool_started":
                        # console.print(
                        #     f"[bold yellow]🔧 Ejecutando herramienta: {event.tool_name if hasattr(event, 'tool_name') else 'Desconocido'}[/]"
                        # )
                        pass

                    elif event.type == "tool_finished":
                        # console.print(
                        #     f"[bold blue]🔧 Herramienta completada: {event.tool_name if hasattr(event, 'tool_name') else 'Desconocido'}[/]"
                        # )
                        pass

                    elif event.type == "handoff_started":
                        # console.print(
                        #     f"[bold magenta]🔄 Iniciando transferencia a: {event.target_agent.name if hasattr(event, 'target_agent') and hasattr(event.target_agent, 'name') else 'Desconocido'}[/]"
                        # )
                        pass
            except Exception as e:
                console.print(f"[dim red]Error procesando evento: {str(e)}[/dim red]")
