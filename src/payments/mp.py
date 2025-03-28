import os
from dotenv import load_dotenv
import mercadopago
from typing import Any, Callable, Optional
from agents import function_tool, RunContextWrapper
from functools import wraps
from datetime import datetime, timedelta
from rich.console import Console

console = Console()

load_dotenv()


def get_apps_script_endpoint():
    """
    Returns the webhook URL for Mercado Pago notifications
    using configuration from .env file.

    Returns:
        str: Webhook URL for Mercado Pago notifications
    """
    webhook_url = os.environ.get("MP_WEBHOOK_URL")

    if not webhook_url:
        environment = os.environ.get("ENVIRONMENT", "development")

        if environment.lower() == "production":
            webhook_url = ""
        else:
            webhook_url = os.environ.get("MP_DEV_WEBHOOK_URL", "")

    return webhook_url


def auto_schema(name_override: str):
    """Decorator that automatically generates the JSON schema for database functions.

    Args:
        name_override: Function name for the agent
    """

    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(ctx: RunContextWrapper[Any], *args, **kwargs):
            return await func(ctx, *args, **kwargs)

        return function_tool(name_override=name_override)(wrapper)

    return decorator


@auto_schema(name_override="create_mercadopago_link")
async def create_mercadopago_link(
    ctx: RunContextWrapper[Any],
    amount: float,
    title: str,
    description: str,
    external_reference: Optional[str] = None,
):
    """
    Creates a Mercado Pago payment link.

    Args:
        ctx: The context wrapper
        amount: Price of the item (as float)
        title: Title of the purchase
        description: Optional description
        external_reference: Optional external reference for tracking

    Returns:
        str: The payment link URL
    """
    mp_token = os.environ.get("MP_ACCESS_TOKEN")
    dev_mode = os.environ.get("MP_DEV_MODE", "false").lower() == "true"

    console.print(f"\n[bold cyan]💰 MERCADO PAGO[/]: Generating payment link...")
    console.print(f"[dim cyan]  └─ Amount: ${amount}[/dim cyan]")
    console.print(f"[dim cyan]  └─ Title: {title}[/dim cyan]")
    console.print(
        f"[dim cyan]  └─ Development mode: {'Enabled' if dev_mode else 'Disabled'}[/dim cyan]"
    )

    if mp_token is None:
        console.print(
            "[bold red]❌ MP ERROR[/]: MP_ACCESS_TOKEN not configured in environment variables"
        )
        if dev_mode:
            order_id = int(datetime.now().timestamp())
            mock_link = f"https://link.mercadopago.com/error-no-token"
            console.print(
                f"[bold yellow]⚠️ DEV MODE[/]: Generating mock link: {mock_link}"
            )
            return mock_link
        return "https://link.mercadopago.com/error-no-token"

    try:
        order_id = int(datetime.now().timestamp())

        if dev_mode:
            mock_link = (
                f"https://link.mercadopago.com/test-payment-{order_id}?amount={amount}"
            )
            console.print(
                f"[bold green]✅ DEV MODE[/]: Test link generated: {mock_link}"
            )
            return mock_link

        sdk = mercadopago.SDK(mp_token)
        console.print(f"[bold yellow]⏳ PROCESSING[/]: Connecting to Mercado Pago...")

        item = {
            "title": title,
            "quantity": 1,
            "unit_price": float(amount),
            "currency_id": "ARS",
        }

        if description:
            item["description"] = description

        preference_data = {
            "items": [item],
            "back_urls": {
                "success": "https://mystore.com/success",
                "failure": "https://mystore.com/failure",
                "pending": "https://mystore.com/pending",
            },
            "auto_return": "approved",
            "statement_descriptor": "MyOnlineStore",
            "external_reference": str(order_id),
            "expires": True,
            "expiration_date_from": datetime.now().isoformat(),
            "expiration_date_to": (datetime.now() + timedelta(hours=24)).isoformat(),
        }

        console.print(
            "[bold yellow]⏳ PROCESSING[/]: Sending request to MercadoPago..."
        )

        preference_response = sdk.preference().create(preference_data)
        preference = preference_response["response"]

        if preference_response["status"] != 201:
            console.print(
                f"[bold red]❌ MP ERROR[/]: Error creating preference: {preference_response['response']}"
            )
            return f"https://link.mercadopago.com/error-{order_id}"

        payment_link = preference["init_point"]
        console.print(f"[bold green]✅ SUCCESS[/]: Link generated: {payment_link}")
        return payment_link

    except Exception as e:
        console.print(f"[bold red]❌ MP ERROR[/]: {str(e)}")

        if dev_mode:
            mock_link = f"https://link.mercadopago.com/error-exception-{int(datetime.now().timestamp())}"
            console.print(
                f"[bold yellow]⚠️ DEV MODE[/]: Generating mock link due to error: {mock_link}"
            )
            return mock_link

        return f"https://link.mercadopago.com/error-exception-{int(datetime.now().timestamp())}"
