from agents import Agent, Runner, handoff, RunContextWrapper
from dotenv import load_dotenv
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from ..db.database import (
    get_productos,
    get_producto,
    crear_producto,
    crear_compra,
    get_tipos_compra,
    get_reporte_ventas,
)

# --- Env configs ---#
load_dotenv()
console = Console()

# Constantes para el manejo del contexto
MAX_MESSAGES = 10  # Número máximo de mensajes a mantener en el contexto
MAX_TURNS = 15  # Número máximo de turnos antes de limpiar el contexto


# --- Context --- #
@dataclass
class OrderItem:
    """Representa un item en la orden actual."""

    producto: str
    cantidad: int
    precio_unitario: Optional[float] = None


@dataclass
class ChatContext:
    uid: int
    messages: List[Dict[str, Any]] = field(default_factory=list)
    current_order: Dict[str, OrderItem] = field(default_factory=dict)
    current_agent: str = "main"
    conversation_state: Dict[str, Any] = field(default_factory=dict)
    turn_count: int = 0

    def add_message(self, role: str, content: str) -> None:
        """Add a new message to the chat history."""
        self.messages.append({"role": role, "content": content})
        self.turn_count += 1

        # Limpiar el contexto si se excede el número máximo de turnos
        if self.turn_count >= MAX_TURNS:
            self._cleanup_context()

        # Actualizar el estado de la conversación basado en el contenido
        self._update_conversation_state(role, content)

    def add_to_order(
        self, producto: str, cantidad: int, precio_unitario: Optional[float] = None
    ) -> None:
        """Agregar un producto a la orden actual."""
        if producto in self.current_order:
            self.current_order[producto].cantidad += cantidad
        else:
            self.current_order[producto] = OrderItem(
                producto=producto, cantidad=cantidad, precio_unitario=precio_unitario
            )

        # Actualizar el estado de la conversación
        self.conversation_state["has_items"] = True
        self.current_agent = "sales"

    def get_current_order(self) -> Dict[str, OrderItem]:
        """Obtener la orden actual."""
        return self.current_order

    def clear_order(self) -> None:
        """Limpiar la orden actual."""
        self.current_order = {}
        self.conversation_state["has_items"] = False

    def get_messages(self) -> List[Dict[str, Any]]:
        """Get all messages in the chat history."""
        return self.messages

    def get_recent_messages(self, n: int = MAX_MESSAGES) -> List[Dict[str, Any]]:
        """Get the n most recent messages."""
        return self.messages[-n:]

    def clear_messages(self) -> None:
        """Clear the chat history."""
        self.messages = []
        self.current_order = {}
        self.conversation_state = {}
        self.current_agent = "main"
        self.turn_count = 0
        console.clear()

    def _cleanup_context(self) -> None:
        """Clean up the context while maintaining important information."""
        # Mantener solo los últimos MAX_MESSAGES mensajes
        self.messages = self.messages[-MAX_MESSAGES:]

        # Mantener el estado actual de la conversación y la orden
        current_state = {
            "intent": self.conversation_state.get("intent"),
            "order_complete": self.conversation_state.get("order_complete"),
            "payment_method": self.conversation_state.get("payment_method"),
            "delivery_info": self.conversation_state.get("delivery_info"),
            "has_items": bool(self.current_order),
        }

        # Limpiar el estado manteniendo solo la información relevante
        self.conversation_state = {
            k: v for k, v in current_state.items() if v is not None
        }

        # Reiniciar el contador de turnos
        self.turn_count = 0

    def _update_conversation_state(self, role: str, content: str) -> None:
        """Update the conversation state based on the message content."""
        if role == "user":
            content_lower = content.lower()

            # Detectar productos y cantidades
            words = content_lower.split()
            for i, word in enumerate(words):
                if word.isdigit() and i + 1 < len(words):
                    cantidad = int(word)
                    producto = words[i + 1]
                    if "pizza" in producto or "pizzas" in producto:
                        self.add_to_order("pizza muzzarella", cantidad)
                        break

            # Detectar intención de compra
            if any(
                word in content_lower
                for word in ["comprar", "quiero", "necesito", "busco"]
            ):
                self.conversation_state["intent"] = "purchase"
                self.current_agent = "sales"

            # Detectar detalles de pago
            if any(
                word in content_lower
                for word in ["pagar", "transferencia", "efectivo", "tarjeta"]
            ):
                self.conversation_state["payment_method"] = content
                if "transferencia" in content_lower:
                    self.conversation_state["payment_type"] = "transferencia"
                elif "efectivo" in content_lower:
                    self.conversation_state["payment_type"] = "efectivo"
                elif "tarjeta" in content_lower:
                    self.conversation_state["payment_type"] = "tarjeta"

            # Detectar finalización de pedido
            if "eso es todo" in content_lower or "finalizar" in content_lower:
                self.conversation_state["order_complete"] = True

            # Detectar detalles de entrega
            if any(
                word in content_lower for word in ["entregar", "dirección", "domicilio"]
            ):
                self.conversation_state["delivery_info"] = content


class HandoffData(BaseModel):
    prompt: str
    task: str
    instructions: str
    messages: List[str]
    context: Dict[str, Any]
    current_order: Optional[Dict[str, Any]] = None


async def on_handoff(
    ctx: RunContextWrapper[ChatContext], input_data: HandoffData
) -> None:
    """Callback function executed when a handoff occurs."""
    # Incluir la orden actual en el handoff
    input_data.current_order = {
        k: {
            "producto": v.producto,
            "cantidad": v.cantidad,
            "precio_unitario": v.precio_unitario,
        }
        for k, v in ctx.context.current_order.items()
    }

    console.print("\n[bold yellow]Transferring to Sales Agent...[/bold yellow]")

    # Create a table for handoff information
    table = Table(title="[bold yellow]Handoff Information[/bold yellow]")
    table.add_column("Field", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Task", input_data.task)
    table.add_row("Instructions", input_data.instructions)
    table.add_row("Current State", str(ctx.context.conversation_state))
    if input_data.current_order:
        table.add_row("Current Order", str(input_data.current_order))

    console.print(table)
    console.print()


# --- Agents --- #
class Agents:
    salesagent = Agent(
        name="Sales Agent",
        instructions="""You are a specialized sales representative responsible for handling and processing sales transactions. You must maintain the conversation context and current order details at all times.

IMPORTANT: Always respond in the same language the customer uses. Match their language and style of communication.

When a customer starts a purchase:
1. Check the current_order in the context to see what they've ordered
2. If payment_method is set in conversation_state, use that information
3. If order_complete is True, proceed with finalizing the sale

Current Order Format:
- The order details are in context.current_order
- Each item has: producto (name), cantidad (quantity), precio_unitario (unit price)

Payment Process:
1. When payment_type is set in conversation_state:
   - "transferencia": Show bank details (ICBC, Account: 222322444555533, Owner: José M. Rodriguez M.)
   - "efectivo": Confirm the total amount
   - "tarjeta": Process card payment

2. After payment information is provided:
   - For transfers: Confirm the transaction was successfully recorded
   - If any error occurs: Inform that the transaction could not be processed

Your responsibilities:
1. Recording new sales using the crear_compra tool
2. Managing purchase types using obtener_tipos_compra tool
3. Generating sales reports using generar_reporte_ventas tool

Key Behaviors:
- ALWAYS respond in the customer's language
- ALWAYS check context.current_order before asking what they want to buy
- ALWAYS check conversation_state["payment_type"] before asking payment method
- If you have both order and payment method, proceed with the sale
- Keep track of the current order details
- Provide clear next steps
- Be concise and direct
- Never mention being an AI
- Remember this is a hypothetical case - simulate successful transactions

Example Flow:
1. Check current_order → Show order details
2. If no payment_type → Ask for payment method
3. If have payment_type → Process payment and confirm success
4. If order_complete → Finalize sale

Example Responses (adapt to customer's language):
Spanish:
- For successful transfers: "¡Excelente! La transferencia bancaria ha sido registrada exitosamente en nuestro sistema. ¡Tu pedido está confirmado!"
- For errors: "Lo siento, pero no pudimos procesar la transacción en este momento. Por favor, intenta nuevamente."

English:
- For successful transfers: "Great! The bank transfer has been successfully recorded in our system. Your order is now confirmed!"
- For errors: "I apologize, but we couldn't process the transaction at this moment. Please try again."
""",
        tools=[
            crear_compra,
            get_tipos_compra,
            get_reporte_ventas,
        ],
    )

    productsagent = Agent(
        name="Product Agent",
        instructions="""You are a specialized product management representative responsible for administering the product database.

IMPORTANT: Always respond in the same language the customer uses. Match their language and style of communication.

Your responsibilities:
1. Providing product information using obtener_producto and obtener_productos tools
2. Adding new products using crear_producto tool
3. Checking product availability
4. Providing pricing information

Key Behaviors:
- ALWAYS respond in the customer's language
- ALWAYS check context.current_order for existing products
- Be precise with product details
- Keep responses concise
- Never mention being an AI""",
        tools=[
            get_productos,
            get_producto,
            crear_producto,
        ],
    )

    sales_handoff = handoff(
        agent=salesagent,
        on_handoff=on_handoff,
        input_type=HandoffData,
        tool_name_override="transfer_to_sales_agent",
        tool_description_override="Transfer the conversation to the sales agent for handling sales-related tasks",
    )

    mainagent = Agent(
        name="Main Agent",
        instructions="""You are the primary representative coordinating customer interactions. Your main role is to understand requests and direct them appropriately.

IMPORTANT: Always respond in the same language the customer uses. Match their language and style of communication.

Key Responsibilities:
1. Check context.current_order for existing orders
2. Check conversation_state for current status
3. Direct sales-related queries to the Sales Agent
4. Direct product queries to the Product Agent

When to Transfer:
1. SALES AGENT if:
   - Customer wants to buy something
   - Customer mentions payment
   - Customer has items in current_order
   - Customer says "eso es todo" or similar phrases in any language
   - conversation_state has "intent" = "purchase"

2. PRODUCT AGENT if:
   - Customer asks about products
   - Customer needs product information
   - No items in current_order yet

Key Behaviors:
- ALWAYS respond in the customer's language
- ALWAYS check context before asking questions
- Be concise and direct
- Never mention being an AI
- Maintain conversation flow""",
        handoffs=[sales_handoff],
    )

    async def run(self, prompt: str, context: ChatContext) -> str:
        try:
            # Add the user's prompt to the context
            context.add_message("user", prompt)

            # Preparar el mensaje con el contexto actual
            context_message = f"Current order: {context.get_current_order()}\nConversation state: {context.conversation_state}\nUser message: {prompt}"

            # Determine which agent should handle the request based on context
            if context.current_agent == "sales":
                result = await Runner.run(
                    starting_agent=self.salesagent,
                    input=context_message,
                    context=context,
                )
            elif context.current_agent == "products":
                result = await Runner.run(
                    starting_agent=self.productsagent,
                    input=context_message,
                    context=context,
                )
            else:
                result = await Runner.run(
                    starting_agent=self.mainagent,
                    input=context_message,
                    context=context,
                )

            # Add the assistant's response to the context
            context.add_message("assistant", result.final_output)

            return result.final_output
        except Exception as e:
            error_message = f"Error to call OpenAI: {str(e)}"
            context.add_message("system", error_message)
            return error_message
