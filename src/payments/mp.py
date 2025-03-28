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
    # Get webhook URL from .env file
    webhook_url = os.environ.get("MP_WEBHOOK_URL")

    # If not defined in .env, use default
    if not webhook_url:
        environment = os.environ.get("ENVIRONMENT", "development")

        if environment.lower() == "production":
            webhook_url = ""
        else:
            webhook_url = os.environ.get("MP_DEV_WEBHOOK_URL", "")

    return webhook_url


def auto_schema(name_override: str):
    """Decorador que genera automáticamente el esquema JSON para las funciones de la base de datos.

    Args:
        name_override: Nombre de la función para el agente
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
    amount: float,  # Cambiar a float para manejar correctamente el monto
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

    console.print(f"\n[bold cyan]💰 MERCADO PAGO[/]: Generando link de pago...")
    console.print(f"[dim cyan]  └─ Monto: ${amount}[/dim cyan]")
    console.print(f"[dim cyan]  └─ Título: {title}[/dim cyan]")
    console.print(
        f"[dim cyan]  └─ Modo desarrollo: {'Activado' if dev_mode else 'Desactivado'}[/dim cyan]"
    )

    if mp_token is None:
        console.print(
            "[bold red]❌ ERROR MP[/]: MP_ACCESS_TOKEN no configurado en variables de entorno"
        )
        # En modo desarrollo, generar un link ficticio para testing
        if dev_mode:
            order_id = int(datetime.now().timestamp())
            mock_link = f"https://link.mercadopago.com/error-no-token"
            console.print(
                f"[bold yellow]⚠️ MODO DESARROLLO[/]: Generando link ficticio: {mock_link}"
            )
            return mock_link
        return "https://link.mercadopago.com/error-no-token"

    try:
        # Crear ID único para la orden
        order_id = int(datetime.now().timestamp())

        # En modo desarrollo, generar un link ficticio para testing
        if dev_mode:
            mock_link = (
                f"https://link.mercadopago.com/test-payment-{order_id}?amount={amount}"
            )
            console.print(
                f"[bold green]✅ MODO DESARROLLO[/]: Link de prueba generado: {mock_link}"
            )
            return mock_link

        # Crear SDK de MercadoPago
        sdk = mercadopago.SDK(mp_token)
        console.print(f"[bold yellow]⏳ PROCESANDO[/]: Conectando con Mercado Pago...")

        # Configurar los datos del item
        item = {
            "title": title,
            "quantity": 1,
            "unit_price": float(amount),  # Asegurar que es float
            "currency_id": "ARS",  # Añadir moneda
        }

        if description:
            item["description"] = description

        # Configurar la preferencia
        preference_data = {
            "items": [item],
            "back_urls": {
                "success": "https://mitienda.com/success",
                "failure": "https://mitienda.com/failure",
                "pending": "https://mitienda.com/pending",
            },
            "auto_return": "approved",
            "statement_descriptor": "MiTienda Online",
            "external_reference": str(order_id),
            "expires": True,
            "expiration_date_from": datetime.now().isoformat(),
            "expiration_date_to": (datetime.now() + timedelta(hours=24)).isoformat(),
        }

        console.print(
            "[bold yellow]⏳ PROCESANDO[/]: Enviando solicitud a MercadoPago..."
        )

        # Crear la preferencia real
        preference_response = sdk.preference().create(preference_data)
        preference = preference_response["response"]

        if preference_response["status"] != 201:
            console.print(
                f"[bold red]❌ ERROR MP[/]: Error al crear preferencia: {preference_response['response']}"
            )
            return f"https://link.mercadopago.com/error-{order_id}"

        # Obtener el link de pago
        payment_link = preference["init_point"]
        console.print(f"[bold green]✅ ÉXITO[/]: Link generado: {payment_link}")
        return payment_link

    except Exception as e:
        console.print(f"[bold red]❌ ERROR MP[/]: {str(e)}")

        # En modo desarrollo, generar un link ficticio para testing
        if dev_mode:
            mock_link = f"https://link.mercadopago.com/error-exception-{int(datetime.now().timestamp())}"
            console.print(
                f"[bold yellow]⚠️ MODO DESARROLLO[/]: Generando link ficticio por error: {mock_link}"
            )
            return mock_link

        return f"https://link.mercadopago.com/error-exception-{int(datetime.now().timestamp())}"
