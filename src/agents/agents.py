from dotenv import load_dotenv
import json
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
    get_products,
    create_purchase,
    get_purchase_types,
    generate_sales_report,
)
from ..payments.mp import create_mercadopago_link

# Configure logging to suppress specific messages
logging.basicConfig(level=logging.ERROR)
logging.getLogger("openai").setLevel(logging.ERROR)
logging.getLogger("agents").setLevel(logging.ERROR)

# Load environment variables
load_dotenv()

# Set environment variable to disable traces if no API key
if "OPENAI_API_KEY" not in os.environ or not os.environ["OPENAI_API_KEY"]:
    os.environ["OPENAI_API_TRACE_ENABLED"] = "false"

console = Console()

# Logging functions for operations and activity


def log_db_operation(operation_name, start_time, success=True, result=None, error=None):
    """Logs database operations with visual formatting"""
    elapsed = time.time() - start_time

    if success:
        console.print(
            f"[bold green]🗃️ DB OPERATION:[/] {operation_name} [dim]({elapsed:.3f}s)[/dim]"
        )
        if result:
            preview = str(result)[:100]
            if len(str(result)) > 100:
                preview += "..."
            console.print(f"[dim green]  └─ Result: {preview}[/dim]")
    else:
        console.print(
            f"[bold red]❌ DB ERROR:[/] {operation_name} [dim]({elapsed:.3f}s)[/dim]"
        )
        if error:
            console.print(f"[dim red]  └─ Error: {str(error)}[/dim]")


def log_agent_activity(context, agent_name, activity_type, details=None):
    """Logs and visualizes agent activity in the system"""
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]

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
        console.print(f"[bold {style['color']}]Starting processing[/]")
    elif activity_type == "thinking":
        console.print(f"[italic {style['color']}]Analyzing '{details}'[/]")
    elif activity_type == "action":
        console.print(f"[bold {style['color']}]Executing {details}[/]")
    elif activity_type == "completed":
        console.print(f"[bold {style['color']}]Processing completed[/]")
    elif activity_type == "error":
        console.print(f"[bold {style['color']}]Error: {details}[/]")
    else:
        console.print(f"{details}")

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

To transfer, use the appropriate transfer tool when the user's request requires specialized knowledge.
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
    """Information for transfers between agents"""

    prompt: str
    context_data: Optional[Dict[str, Any]] = None
    to_agent: Optional[str] = None  # Add target agent name

    class Config:
        arbitrary_types_allowed = True


async def on_handoff(
    ctx: RunContextWrapper[ChatContext], input_data: HandoffData
) -> None:
    """Function to log handoffs between agents with enhanced visualization"""
    from_agent = (
        getattr(ctx.agent, "name", "Unknown") if hasattr(ctx, "agent") else "Unknown"
    )
    to_agent = (
        getattr(input_data, "to_agent", "Unknown")
        if hasattr(input_data, "to_agent")
        else "Target Agent"
    )

    agent_styles = {
        "Main Agent": {"icon": "🧠", "color": "bold cyan"},
        "Product Agent": {"icon": "🔍", "color": "bold green"},
        "Sales Agent": {"icon": "💰", "color": "bold yellow"},
    }

    from_style = agent_styles.get(from_agent, {"icon": "👤", "color": "bold white"})
    to_style = agent_styles.get(to_agent, {"icon": "👤", "color": "bold white"})

    console.print("\n" + "─" * 80 + "\n")

    console.print(
        f"[{from_style['color']}]{from_style['icon']} {from_agent}[/] [bold magenta]→ TRANSFERRING TO →[/] [{to_style['color']}]{to_style['icon']} {to_agent}[/]"
    )

    if hasattr(input_data, "prompt") and input_data.prompt:
        console.print(
            Panel(
                input_data.prompt,
                title="💬 Message Sent",
                border_style="blue",
                expand=False,
            )
        )

    if hasattr(input_data, "context_data") and input_data.context_data:
        console.print(
            Panel(
                json.dumps(input_data.context_data, indent=2, ensure_ascii=False),
                title="📋 Context Data",
                border_style="green",
                expand=False,
            )
        )

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
                title="🛒 Current Order",
                border_style="yellow",
                expand=False,
            )
        )


class Agents:
    def __init__(self) -> None:
        self.productsagent = Agent(
            name="Product Agent",
            instructions="""You are an expert product finder who speaks with an enthusiastic and detail-oriented personality.

    ALWAYS COMMUNICATE WITH THIS PERSONALITY:
    - Enthusiastic about products ("Excellent choice!")
    - Detail-oriented with information ("I've found all the exact data")
    - Efficient and precise ("Search completed in the database")
    - Occasionally use relevant emojis like 🔍, 📊, 🏷️

    MAIN RESPONSIBILITIES:
    1. ALWAYS call get_products() FIRST for EACH request
    2. Find the best matching product from the database results
    3. Return EXACT information from the database in structured format
    4. NEVER invent or modify product information

    WORKFLOW:
    1. FIRST ACTION: Call get_products() to get all products
    2. Search for the best match using these rules:
       - Exact matches first (e.g., "pizza muzzarella" = "pizza muzzarella")
       - Then partial matches (e.g., "muzza" matches "pizza muzzarella")
       - Then variations (e.g., "pizza de muzza" matches "pizza muzzarella")
    3. When found, ALWAYS return in EXACT format:
       "PRODUCT_INFO: [exact_db_name] | PRICE: $[exact_db_price] | DESC: [exact_db_description] | ID: [exact_db_id] | DB_MATCH: true"
    4. If no match is found:
       "NO_MATCH: Could not find a product matching [query]"
    """,
            tools=[get_products],
            model="o3-mini",
        )
        self.products_handoff = handoff(
            agent=self.productsagent,
            on_handoff=on_handoff,
            input_type=HandoffData,
        )
        self.salesagent = Agent(
            name="Sales Agent",
            instructions="""You are a professional payment processor who speaks with a helpful and confident personality.

    ALWAYS COMMUNICATE WITH THIS PERSONALITY:
    - Helpful and attentive ("I'm processing your payment")
    - Precise with financial details ("The total of your order is exactly...")
    - Reassuring and trustworthy ("Your transaction is being processed securely")
    - Occasionally use relevant emojis like 💰, 💳, 🔒

    MAIN RESPONSIBILITIES:
    1. FIRST ACTION: Call create_mercadopago_link with the exact order amount
    2. Return payment information in structured format
    3. NEVER modify order totals
    4. ALWAYS include the payment link in the response
    5. ALWAYS register the purchase in the database

    WORKFLOW:
    1. Receive the total order amount from the Main Agent
    2. IMMEDIATELY call create_mercadopago_link with:
       - amount: Exact order amount
       - title: "Order #[timestamp]"
       - description: "Food order"
    3. Get the payment type ID for "Mercado Pago" using get_purchase_types()
       - Look for the ID where name is "Mercado Pago" or the closest match
    4. Register the purchase in the database by calling create_purchase with:
       - amount: Exact order amount
       - purchase_type_id: ID of the "Mercado Pago" payment type
       - products: List of product IDs with quantities
    5. ALWAYS return in EXACT format:
       "PAYMENT_INFO: Total: $[amount] | Link: [mercadopago_link] | Order_ID: [timestamp]"

    TECHNICAL DETAILS:
    1. The create_purchase function expects these EXACT fields:
       - amount: float (total amount)
       - purchase_type_id: string (UUID of payment type)
       - products: array of objects with:
         * product_id: string (UUID of product)
         * quantity: integer (quantity)
         * unit_price: float (unit price)
    2. When the payment type ID for "Mercado Pago" is not found, use any available ID
       OR return an error message but STILL include the payment link
    """,
            tools=[
                create_mercadopago_link,
                create_purchase,
                get_purchase_types,
                generate_sales_report,
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

            You are the main coordinator who handles all customer interactions with a friendly and attentive personality.

            ALWAYS COMMUNICATE WITH THIS PERSONALITY:
            - Friendly and approachable ("Hello! Delighted to assist you")
            - Patient and clear ("Let me explain the options")
            - Helpful and customer-oriented ("I'm here to help you")
            - Use relevant emojis like 🍕, 👋, 😊, ✅

            PROCEDURE FOR CALLING OTHER AGENTS:
            - When the customer mentions a product: "Let me check that product..." → call Product Agent
            - When they confirm the order: "I'll process your payment..." → call Sales Agent
            - Always communicate the process: "I'm verifying / processing / checking..."

            MAIN RESPONSIBILITIES:
            1. Understand customer food orders in natural language
            2. Consult the Product Agent for precise product details
            3. Maintain the current order state (products, prices, totals)
            4. Coordinate with the Sales Agent to generate payment links

            WORKFLOW WITH OTHER AGENTS:
            - When customers mention a food item (like "pizza"), ALWAYS delegate first to the Product Agent
            - When the customer confirms the order, delegate to the Sales Agent to create the payment link
            - You must follow the proper sequence: Product Agent → confirm order → Sales Agent

            PRODUCT SEARCH PROCESS:
            1. When the customer mentions food items, immediately call the Product Agent
            2. The Product Agent will search the database and respond in this format:
            "PRODUCT_INFO: [name] | PRICE: $[price] | DESC: [desc] | ID: [id] | DB_MATCH: true"
            OR "NO_MATCH: Could not find a product matching [query]"
            3. For successful matches, extract and store:
            - Exact name, price, ID from the database response
            - Mark as validated (db_match = true, price_confirmed = true)
            4. For NO_MATCH responses:
            - Inform the customer that the item was not found
            - Suggest alternatives or ask for clarification

            ORDER MANAGEMENT:
            1. Maintain a clear list of all validated items in the current order
            2. Allow customers to add multiple items before paying
            3. Support commands like "add another", "remove", "view my order"
            4. Before payment, verify that all products have confirmed prices and valid database IDs
            5. Calculate the total order amount using only confirmed prices

            PAYMENT PROCESS:
            1. When the customer confirms the order, calculate the total amount
            2. Delegate to the Sales Agent with the verified total amount
            3. The Sales Agent will respond with:
            "PAYMENT_INFO: Total: $[amount] | Link: [link] | Order_ID: [id]"
            4. Extract the payment link and present it to the customer
            5. After completing payment, thank the customer for their order

            CONVERSATION STYLE:
            - Use friendly and helpful English language appropriate for a food service
            - Be concise but clear in your communications
            - Use emojis occasionally to add a friendly touch (🍕, 👍, etc.)
            - Always maintain a professional but warm tone

            INTERACTION EXAMPLES:
            Customer: "I want a muzzarella pizza"
            You: → Call the Product Agent
            Product Agent: "PRODUCT_INFO: Pizza muzzarella | PRICE: $10.00 | DESC: Pizza with muzzarella cheese | ID: b301e81a-6d3e-4d4d-ab4e-28e88002c10e | DB_MATCH: true"
            You: "Perfect! 🍕 I've added a Pizza muzzarella to your order for $10.00. Would you like to order anything else or proceed with payment?"

            Customer: "I want to add a soda"
            You: → Call the Product Agent
            Product Agent: "PRODUCT_INFO: Coca-Cola 500ml | PRICE: $3.50 | DESC: Carbonated beverage | ID: d45e81a-9f3e-8d9d-cd4e-12e88042a45e | DB_MATCH: true"
            You: "Excellent! I've added a Coca-Cola 500ml for $3.50 to your order. Your current total is $13.50. Anything else or shall we proceed to payment?"

            Customer: "That's all, I want to pay"
            You: → Verify that all products have db_match=true and price_confirmed=true
            You: → Call the Sales Agent with total amount $13.50
            Sales Agent: "PAYMENT_INFO: Total: $13.50 | Link: https://mp.com/xyz123 | Order_ID: 456"
            You: "Great! 👍 Here's your payment link for $13.50: https://mp.com/xyz123
            Once payment is made, your order will be processed. Thank you for your order!"

            ERROR HANDLING:
            - If product not found: Ask the customer for alternative options or clarifications
            - If price not confirmed: Retry with the Product Agent, never proceed with unconfirmed prices
            - If payment link fails: Inform the customer and retry with the Sales Agent
            - Always show specific error details to help the customer understand the problem

            IMPORTANT TECHNICAL CHECKS:
            - ALWAYS validate db_match = true before confirming prices
            - NEVER proceed with unconfirmed prices
            - ALWAYS verify that database IDs exist for all products
            - ALWAYS extract and display the payment link exactly as provided by the Sales Agent
            """,
            model="o3-mini",
            handoffs=[self.salesagent, self.productsagent],
        )
        self.current_conversations = []
        self.conversation_history = []

    async def run(self, text, context=None):
        """Runs the agent with the provided text and returns its response"""
        if context is None:
            context = {"messages": []}
            is_dict_context = True
        else:
            is_dict_context = not hasattr(context, "add_message")

        if is_dict_context:
            context["messages"].append({"role": "user", "content": text})
            message_count = len(context["messages"])
        else:
            context.add_message("user", text)
            message_count = len(context.get_messages())

        if message_count == 1:
            result = await Runner.run(
                starting_agent=self.mainagent, input=text, context=context
            )
        else:
            if is_dict_context:
                agent_context = {"messages": context["messages"]}
            else:
                agent_context = context.get_messages()

            result = await Runner.run(
                starting_agent=self.mainagent, input=agent_context, context=context
            )

        response = (
            result.final_output if hasattr(result, "final_output") else str(result)
        )
        final_output = response
        humanized_output = ""

        if isinstance(response, str) and (
            "PRODUCT_INFO:" in response or "PAYMENT_INFO:" in response
        ):
            if "PRODUCT_INFO:" in response:
                try:
                    if "|" in response:
                        product_parts = response.split("|")
                        product_name = (
                            product_parts[0].replace("PRODUCT_INFO:", "").strip()
                        )
                        price = product_parts[1].replace("PRICE:", "").strip()
                        humanized_output = f"Excellent choice! 🍕 I've added {product_name} for {price} to your order. Would you like to add anything else or proceed to payment?"
                    else:
                        products_info = (
                            response.split("PRODUCT_INFO:")[1].split("\n")[0].strip()
                        )
                        products_data = json.loads(products_info)
                        humanized_output += "📋 Selected products:\n"
                        for product in products_data:
                            humanized_output += (
                                f"- {product['name']}: ${product['price']}\n"
                            )
                        humanized_output += "\n"
                except Exception:
                    pass

            if "PAYMENT_INFO:" in response:
                try:
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

                        error_message = ""
                        if "Error creating purchase:" in response:
                            error_message = "\n\n⚠️ Note: There was a small technical issue when registering your purchase in our database, but don't worry. Your payment and order will be processed correctly."

                        humanized_output = f"Your order is ready to pay! 👍\n\n💰 Total to pay: {total}\n\n🔗 Payment link: {link}\n\n🧾 Order number: {order_id}{error_message}\n\nIs there anything else I can help you with?"
                    else:
                        payment_info = response.split("PAYMENT_INFO:")[1].strip()
                        payment_data = json.loads(payment_info)
                        humanized_output += "💰 Payment information:\n"
                        humanized_output += (
                            f"- Total: ${payment_data.get('total', 'N/A')}\n"
                        )
                        humanized_output += f"- Payment link: {payment_data.get('payment_link', 'N/A')}\n"
                        humanized_output += (
                            f"- Order ID: {payment_data.get('order_id', 'N/A')}\n"
                        )
                except Exception:
                    pass

        if humanized_output:
            console.print("\n[bold green]FINAL RESPONSE:[/]")
            console.print(humanized_output)
        else:
            console.print("\n[bold green]FINAL RESPONSE:[/]")
            console.print(response)

        if is_dict_context:
            context["messages"].append({"role": "assistant", "content": response})
        else:
            context.add_message("assistant", response)

        return response

    def _trace_callback(self, event):
        """Callback to display events during execution"""
        if isinstance(event, dict):
            event_type = event.get("type")

            if event_type == "agent_started":
                agent_name = event.get("agent", {}).get("name", "Unknown")
                pass

            elif event_type == "agent_finished":
                agent_name = event.get("agent", {}).get("name", "Unknown")
                pass

            elif event_type == "tool_started":
                tool_name = event.get("tool_name", "Unknown")
                pass

            elif event_type == "tool_finished":
                tool_name = event.get("tool_name", "Unknown")
                pass

            elif event_type == "handoff_started":
                target_agent_name = event.get("target_agent", {}).get("name", "Unknown")
                pass
        else:
            # If not a dictionary, we try to handle it as an object
            try:
                if hasattr(event, "type"):
                    if event.type == "agent_started":
                        pass

                    elif event.type == "agent_finished":
                        pass

                    elif event.type == "tool_started":
                        pass

                    elif event.type == "tool_finished":
                        pass

                    elif event.type == "handoff_started":
                        pass
            except Exception as e:
                console.print(f"[dim red]Error processing event: {str(e)}[/dim red]")
