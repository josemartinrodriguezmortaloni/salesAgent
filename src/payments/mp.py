import os
from dotenv import load_dotenv
from datetime import datetime, timedelta
import mercadopago
import logging as logger
from typing import Any, Callable, Optional
from datetime import datetime
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
def create_mercadopago_link(
    id: int,
    price: float,
    title: str,
    quantity: int = 1,
    description: Optional[str] = None,
    external_reference: Optional[str] = None,
    success_url: Optional[str] = None,
    failure_url: Optional[str] = None,
    pending_url: Optional[str] = None,
    expires: bool = False,
    binary_mode: bool = False
):
    mp_token = os.environ.get("MP_ACCESS_TOKEN")
    if (mp_token is None or price is None):
        raise Exception("Mercado Pago token or price not set")
    sdk = mercadopago.SDK(mp_token)
    logger.debug("Creating mercado pago link")

    item = {
        "title": title,
        "quantity": quantity,
        "unit_price": price,
    }
    if description:
        item["description"] = description
    
    preference_data = {
        "metadata": {
            "id": id,
        },
        "items": [item],
        "notification_url": get_apps_script_endpoint()
    }
    
    if external_reference:
        preference_data["external_reference"] = external_reference
    
    if success_url or failure_url or pending_url:
        preference_data["back_urls"] = {}
        if success_url:
            preference_data["back_urls"]["success"] = success_url
        if failure_url:
            preference_data["back_urls"]["failure"] = failure_url
        if pending_url:
            preference_data["back_urls"]["pending"] = pending_url
    
    if binary_mode:
        preference_data["binary_mode"] = True
    
    if expires:
        expiration_date = (datetime.now() + timedelta(hours=24)).isoformat()
        preference_data["expires"] = True
        preference_data["expiration_date_from"] = expiration_date
    
    logger.debug(preference_data)
    preference_response = sdk.preference().create(preference_data)
    preference = preference_response["response"]
    
    if (preference_response["status"] != 201):
        logger.debug(preference_response["response"])
        raise Exception("Mercado Pago error")
    
    logger.debug(preference["init_point"])
    return preference["init_point"]
