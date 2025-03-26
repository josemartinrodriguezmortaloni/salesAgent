from agents import Agent, Runner, handoff, RunContextWrapper, OpenAIChatCompletionsModel, AsyncOpenAI
from dotenv import load_dotenv
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from rich.console import Console
from rich.table import Table
from ..db.database import (
    get_productos,
    get_producto,
    crear_producto,
    crear_compra,
    get_tipos_compra,
    get_reporte_ventas,
)
from ..payments.mp import create_mercadopago_link

load_dotenv()
console = Console()

MAX_MESSAGES = 10
MAX_TURNS = 15

@dataclass
class OrderItem:
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
        self.messages.append({"role": role, "content": content})
        self.turn_count += 1

        if self.turn_count >= MAX_TURNS:
            self._cleanup_context()

        self._update_conversation_state(role, content)

    def add_to_order(
        self, producto: str, cantidad: int, precio_unitario: Optional[float] = None
    ) -> None:
        if producto in self.current_order:
            self.current_order[producto].cantidad += cantidad
        else:
            self.current_order[producto] = OrderItem(
                producto=producto, cantidad=cantidad, precio_unitario=precio_unitario
            )

        self.conversation_state["has_items"] = True
        self.current_agent = "sales"

    def get_current_order(self) -> Dict[str, OrderItem]:
        return self.current_order

    def clear_order(self) -> None:
        self.current_order = {}
        self.conversation_state["has_items"] = False

    def get_messages(self) -> List[Dict[str, Any]]:
        return self.messages

    def get_recent_messages(self, n: int = MAX_MESSAGES) -> List[Dict[str, Any]]:
        return self.messages[-n:]

    def clear_messages(self) -> None:
        self.messages = []
        self.current_order = {}
        self.conversation_state = {}
        self.current_agent = "main"
        self.turn_count = 0
        console.clear()

    def _cleanup_context(self) -> None:
        self.messages = self.messages[-MAX_MESSAGES:]

        current_state = {
            "intent": self.conversation_state.get("intent"),
            "order_complete": self.conversation_state.get("order_complete"),
            "payment_method": self.conversation_state.get("payment_method"),
            "delivery_info": self.conversation_state.get("delivery_info"),
            "has_items": bool(self.current_order),
        }

        self.conversation_state = {
            k: v for k, v in current_state.items() if v is not None
        }

        self.turn_count = 0

    def _update_conversation_state(self, role: str, content: str) -> None:
        if role == "user":
            content_lower = content.lower()

            words = content_lower.split()
            for i, word in enumerate(words):
                if word.isdigit() and i + 1 < len(words):
                    cantidad = int(word)
                    producto = words[i + 1]
                    if "pizza" in producto or "pizzas" in producto:
                        self.add_to_order("pizza muzzarella", cantidad)
                        break

            if any(
                word in content_lower
                for word in ["comprar", "quiero", "necesito", "busco"]
            ):
                self.conversation_state["intent"] = "purchase"
                self.current_agent = "sales"

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

            if "eso es todo" in content_lower or "finalizar" in content_lower:
                self.conversation_state["order_complete"] = True

            if any(
                word in content_lower for word in ["entregar", "dirección", "domicilio"]
            ):
                self.conversation_state["delivery_info"] = content

class HandoffData(BaseModel):
    prompt: str
    task: Optional[str] = None
    instructions: Optional[str] = None
    messages: Optional[List[str]] = None
    context: Optional[Dict[str, Any]] = None
    current_order: Optional[Dict[str, Any]] = None

async def on_handoff(
    ctx: RunContextWrapper[ChatContext], input_data: HandoffData
) -> None:
    # Inicializar campos si son None
    if input_data.context is None:
        input_data.context = {}
    
    # Incluir la orden actual en el handoff
    input_data.current_order = {
        k: {
            "producto": v.producto,
            "cantidad": v.cantidad,
            "precio_unitario": v.precio_unitario,
        }
        for k, v in ctx.context.current_order.items()
    }

    console.print("\n[bold yellow]Transferring to Agent...[/bold yellow]")
    agent_type = ctx.context.current_agent
    if agent_type == "products":
        # Al terminar, establecer el agente actual a ventas para continuar el flujo
        ctx.context.current_agent = "sales"
        
        # Si hay productos en la orden actual sin precio, establece el precio por defecto
        for product_name, order_item in ctx.context.current_order.items():
            if order_item.precio_unitario is None:
                order_item.precio_unitario = 10.0  # Precio por defecto en USD
                console.print(f"[bold green]Updating price for {product_name} to $10.00[/bold green]")


    # Create a table for handoff information
    table = Table(title="[bold yellow]Handoff Information[/bold yellow]")
    table.add_column("Field", style="cyan")
    table.add_column("Value", style="green")

    # Solo añadir filas para campos que no son None
    if input_data.task:
        table.add_row("Task", input_data.task)
    if input_data.instructions:
        table.add_row("Instructions", input_data.instructions)
    table.add_row("Current State", str(ctx.context.conversation_state))
    if input_data.current_order:
        table.add_row("Current Order", str(input_data.current_order))

    console.print(table)
    console.print()

class Agents:
    productsagent = Agent(
        name="Product Agent",
        instructions="""You are a specialized product management representative responsible for administering the product database.

IMPORTANT: Always respond in the same language the request was made. Match language and style of communication.

## CORE RESPONSIBILITIES
1. Providing detailed product information including:
   - Prices
   - Availability
   - Product descriptions
   - Product specifications
2. Managing product data using:
   - obtener_producto and obtener_productos tools for retrieving information
   - crear_producto tool for adding new products

## HANDLING INTER-AGENT REQUESTS
- When another agent requests product information, focus on providing complete data
- ALWAYS include price information when describing products
- If you don't have a specific product in the database, provide the closest match AND update the product with the recommended price
- Format responses in a structured way that's easy for other agents to parse
- For pizza products, if not found in database, automatically set a default price of $10.00 USD per pizza

## KEY BEHAVIORS
- Be precise with product details
- Keep responses concise and data-focused
- Prioritize providing complete information to other agents
- When responding to the Sales Agent, focus on providing actionable data rather than conversational elements

## EXAMPLE RESPONSES
### When providing product info to Sales Agent:
"Product information for 'pizza muzzarella':
- Price: $10.00 USD per unit
- In stock: Yes
- Description: Traditional cheese pizza with mozzarella topping"

### When product is not found:
"The requested product 'pizza muzzarella' is not found in the database. Based on similar products, the recommended price is $10.00 USD per unit."
""",
        tools=[
            get_productos,
            get_producto,
            crear_producto,
        ],
        model = OpenAIChatCompletionsModel( 
            model="o3-mini",
            openai_client=AsyncOpenAI()
        ),
    )
    
    products_handoff = handoff(
        agent=productsagent,
        on_handoff=on_handoff, 
        input_type=HandoffData,
        tool_name_override="transfer_to_product_agent",
        tool_description_override="Transfer the conversation to the product agent to get product information",
    )

    salesagent = Agent(
        name="Sales Agent",
        instructions="""You are a specialized sales representative responsible for handling and processing sales transactions exclusively through Mercado Pago payment links. You must maintain the conversation context and current order details at all times.

## CORE PRINCIPLES
- ALWAYS respond in English regardless of the language the customer uses
- Maintain a professional but friendly tone
- Be concise and action-oriented

## INTER-AGENT COMMUNICATION
- CONSULT the Product Agent whenever you need information about products (prices, availability, details)
- When a customer mentions a product without price information, DO NOT ask the customer for the price
- INSTEAD, use the transfer_to_product_agent tool to get product information automatically
- After getting product information, resume the sales process with the updated information

## ORDER MANAGEMENT
- Always check context.current_order first before asking what they want to buy
- Order details structure: context.current_order contains items with producto (name), cantidad (quantity), precio_unitario (unit price)
- If price information is missing, get it from the Product Agent rather than asking the customer
- Calculate and confirm the total amount before proceeding to payment

## PAYMENT PROCESS - MERCADO PAGO ONLY
1. CHECK ORDER INFORMATION:
   - Verify context.current_order exists and has all necessary details
   - If price information is missing, get it from the Product Agent
   - Confirm the total amount with the customer

2. GENERATE MERCADO PAGO LINK:
   - Use create_mercadopago_link tool with these parameters:
     * id: Generate a unique ID for this transaction
     * price: Total amount from current_order
     * title: Brief description of the purchase (e.g., "Purchase at [Store Name]")
     * quantity: Usually 1 (representing the whole order)
   - Provide the payment link clearly to the customer
   - Explain that they will receive confirmation once payment is processed

3. PAYMENT CONFIRMATION:
   - Inform the customer that they'll receive automatic confirmation once the payment is completed
   - Explain that our system will process their order immediately after payment confirmation
   - After payment confirmation, use crear_compra tool to record the sale in the database

4. ERROR HANDLING:
   - If there are any issues generating the payment link, inform the customer and try again
   - If payment fails, offer to generate a new payment link

## DATABASE MANAGEMENT
- Use obtener_tipos_compra to retrieve available purchase categories when needed
- Use generar_reporte_ventas for creating sales reports when requested
- Always confirm database operations have completed successfully

## EXAMPLE RESPONSES
### When you need product information:
"Let me verify the price and availability of that product."
[Use transfer_to_product_agent here]

### When generating Mercado Pago link:
"I've generated your secure payment link: [LINK]. Click, complete your information and finalize the transaction. Once payment is confirmed, we'll process your order immediately and you'll receive a confirmation notification."

### For successful transactions:
"Excellent! Your payment has been processed successfully. Your order number is #[ORDER_ID]. We have registered all the details in our database and your order is confirmed."

### For transaction errors:
"I'm sorry, there seems to be a problem processing your payment. Would you like me to generate a new payment link to try again?"

Remember that payment confirmations via Mercado Pago will be processed through webhooks, so inform customers they'll receive confirmation once payment is completed.
""",
        tools=[
            crear_compra,
            get_tipos_compra,
            get_reporte_ventas,
            create_mercadopago_link,
        ],
        handoffs=[products_handoff], 
        model = OpenAIChatCompletionsModel( 
            model="o3-mini",
            openai_client=AsyncOpenAI()
        ),  
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

## KEY RESPONSIBILITIES
1. Check context.current_order for existing orders
2. Check conversation_state for current status
3. Direct sales-related queries to the Sales Agent
4. Direct product queries to the Product Agent
5. Facilitate smooth transitions between agents

## WHEN TO TRANSFER
1. SALES AGENT if:
   - Customer wants to buy something
   - Customer mentions payment
   - Customer has items in current_order
   - Customer says "eso es todo" or similar phrases in any language
   - conversation_state has "intent" = "purchase"

2. PRODUCT AGENT if:
   - Customer asks about products specifically
   - Customer needs product information, price, or availability
   - Customer asks "how much is..."

## KEY BEHAVIORS
- ALWAYS respond in the customer's language
- ALWAYS check context before asking questions
- Be concise and direct
- Maintain conversation flow
- Facilitate smooth transitions between specialized agents
""",
        handoffs=[sales_handoff, products_handoff],
        model = OpenAIChatCompletionsModel( 
            model="o3-mini",
            openai_client=AsyncOpenAI()
        ),        
    )

    async def run(self, prompt: str, context: ChatContext) -> str:
        try:
            context.add_message("user", prompt)
            context_message = f"Current order: {context.get_current_order()}\nConversation state: {context.conversation_state}\nUser message: {prompt}"

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

            context.add_message("assistant", result.final_output)
            return result.final_output
        except Exception as e:
            error_message = f"Error to call OpenAI: {str(e)}"
            context.add_message("system", error_message)
            return error_message
