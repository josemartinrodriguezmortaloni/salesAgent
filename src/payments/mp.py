import os
from dotenv import load_dotenv
import mercadopago
import logging as logger
from typing import Any, Callable, Optional
from agents import function_tool, RunContextWrapper
from functools import wraps


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

        # Aplicar el decorador function_tool con el nombre personalizado
        return function_tool(name_override=name_override)(wrapper)

    return decorator


@auto_schema(name_override="create_mercadopago_link")
async def create_mercadopago_link(
    ctx: RunContextWrapper[Any],
    id: int,
    price: float,
    title: str,
    # Parámetros opcionales sin valores por defecto
    quantity: Optional[int] = None,
    description: Optional[str] = None,
    external_reference: Optional[str] = None
):
    """
    Creates a Mercado Pago payment link.
    
    Args:
        ctx: The context wrapper
        id: Transaction identifier
        price: Price of the item
        title: Title of the purchase
        quantity: Quantity of items (default 1 if not provided)
        description: Optional description
        external_reference: Optional external reference for tracking
    
    Returns:
        str: The payment link URL
    """
    mp_token = os.environ.get("MP_ACCESS_TOKEN")
    if (mp_token is None or price is None):
        raise Exception("Mercado Pago token or price not set")
    
    # Handle default values within the function
    if quantity is None:
        quantity = 1
        
    sdk = mercadopago.SDK(mp_token)
    logger.debug("Creating mercado pago link")
    
    # Build item with provided parameters
    item = {
        "title": title,
        "quantity": quantity,
        "unit_price": price,
    }
    
    if description:
        item["description"] = description
    
    # Construct preference_data
    preference_data = {
        "metadata": {
            "id": id,
        },
        "items": [item],
        "notification_url": get_apps_script_endpoint()
    }
    
    # Add external_reference if present
    if external_reference:
        preference_data["external_reference"] = external_reference
    
    logger.debug(preference_data)
    preference_response = sdk.preference().create(preference_data)
    preference = preference_response["response"]
    
    if (preference_response["status"] != 201):
        logger.debug(preference_response["response"])
        raise Exception("Mercado Pago error")
    
    logger.debug(preference["init_point"])
    return preference["init_point"]
