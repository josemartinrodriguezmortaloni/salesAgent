import logging
import json
import asyncio
from typing import Optional, List, Dict, Any

import requests
from flask import current_app, jsonify
import re
from .interactive_builder import (
    build_text_message,
    build_cta_url_message,
    build_list_message,
)
from src.agents.agents import Agents, ChatContext
from src.db.supabase_client import supabase

# Instantiate the Agents system once so it can be reused across requests
_agents_instance: Optional[Agents] = None

# Store ChatContext per WhatsApp user (wa_id) so the conversation persists
_contexts: Dict[str, ChatContext] = {}


def _get_agents() -> Agents:
    global _agents_instance
    if _agents_instance is None:
        _agents_instance = Agents()
    return _agents_instance


def log_http_response(response):
    logging.info(f"Status: {response.status_code}")
    logging.info(f"Content-type: {response.headers.get('content-type')}")
    logging.info(f"Body: {response.text}")


def send_message(payload: Dict):
    access_token = current_app.config["ACCESS_TOKEN"]
    headers = {
        "Content-type": "application/json",
        "Authorization": f"Bearer {access_token}",
    }
    url = f"https://graph.facebook.com/{current_app.config['VERSION']}/{current_app.config['PHONE_NUMBER_ID']}/messages"
    # Prevent sending duplicates: fetch ChatContext by waid
    context = _contexts.get(payload.get("to"))
    payload_str = json.dumps(payload, sort_keys=True)
    if context and getattr(context, "last_sent_payload", None) == payload_str:
        print("Duplicate payload suppressed")
        return
    if context:
        context.last_sent_payload = payload_str
    try:
        response = requests.post(
            url, data=json.dumps(payload), headers=headers, timeout=10
        )
        response.raise_for_status()
    except requests.Timeout:
        logging.error("Timeout occurred while sending message")
        return jsonify({"status": "error", "message": "Request timed out"}), 408
    except requests.RequestException as e:
        logging.error(f"Request failed due to: {e}")
        return jsonify({"status": "error", "message": "Failed to send message"}), 500
    else:
        log_http_response(response)
        return response


def process_text_for_whatsapp(text):
    pattern = r"\【.*?\】"
    text = re.sub(pattern, "", text).strip()
    pattern = r"\*\*(.*?)\*\*"
    replacement = r"*\1*"
    whatsapp_style_text = re.sub(pattern, replacement, text)
    return whatsapp_style_text


def _build_catalog_rows(limit: int = 10) -> List[Dict[str, str]]:
    try:
        products_resp = supabase.table("productos").select("*").execute()
        products = products_resp.data or []
    except Exception as exc:
        logging.error(f"Error fetching products for catalog: {exc}")
        return []
    rows: List[Dict[str, str]] = []
    for p in products[:limit]:
        rows.append(
            {
                "id": p.get("id", p.get("nombre")),
                "title": p.get("nombre"),
                "description": f"${p.get('precio')}",
            }
        )
    return rows


def _send_initial_catalog(recipient_waid: str) -> None:
    welcome_text = (
        "¡Hola! 😊 Bienvenido/a. Aquí tienes nuestro catálogo actual de productos. "
        "Selecciona el que más te guste o dime si necesitas ayuda."
    )
    send_message(build_text_message(recipient_waid, welcome_text))
    rows = _build_catalog_rows()
    if not rows:
        return
    sections = [{"title": "Menú", "rows": rows}]
    list_payload = build_list_message(
        recipient_waid,
        body_text="Elige tu producto favorito:",
        button_text="Ver menú 🍕",
        sections=sections,
    )
    send_message(list_payload)


def process_whatsapp_message(body):
    value = body["entry"][0]["changes"][0]["value"]
    wa_id = value["contacts"][0]["wa_id"] if value.get("contacts") else None
    name = value["contacts"][0]["profile"]["name"] if value.get("contacts") else None
    message = value["messages"][0]
    # Determine user input depending on type (text / list_reply / button_reply)
    message_body: str
    if message["type"] == "text":
        message_body = message["text"]["body"]
    elif message["type"] == "interactive":
        interactive = message["interactive"]
        if interactive["type"] == "list_reply":
            list_reply = interactive["list_reply"]
            message_body = list_reply.get("title") or list_reply.get("id")
        elif interactive["type"] == "button_reply":
            button_reply = interactive["button_reply"]
            message_body = button_reply.get("title") or button_reply.get("id")
        else:
            message_body = ""
    else:
        logging.info(f"Unsupported message type: {message['type']}")
        return
    context = _contexts.get(wa_id)
    if context is None:
        context = ChatContext()
        _contexts[wa_id] = context
    # Add the user message to the context BEFORE checking is_first_message
    context.add_message("user", message_body)
    is_first_message = len(context.messages) == 1
    recipient_waid = (
        current_app.config["RECIPIENT_WAID"]
        .split()[0]
        .replace('"', "")
        .replace("'", "")
    )
    if is_first_message:
        _send_initial_catalog(recipient_waid)
        return

    async def _generate_response():
        agents = _get_agents()
        return await agents.run(message_body, context=context)

    try:
        response = asyncio.run(_generate_response())
    except RuntimeError:
        response = asyncio.get_event_loop().run_until_complete(_generate_response())
    if not response:
        return
    if isinstance(response, str) and "NO_MATCH:" in response:
        return
    # Decide message type: CTA / LIST / TEXT
    payload: Dict
    if isinstance(response, str) and "PAYMENT_INFO:" in response:
        parts = [p.strip() for p in response.split("|")]
        total = link = ""
        for p in parts:
            if p.startswith("PAYMENT_INFO: Total:"):
                total = p.replace("PAYMENT_INFO: Total:", "").strip()
            elif p.startswith("Link:"):
                link = p.replace("Link:", "").strip()
        body_text = f"Your order is ready! Total {total}. Tap the button to pay."
        payload = build_cta_url_message(
            recipient_waid,
            body_text=body_text,
            button_text="Pay now 💳",
            url=link,
        )
    elif isinstance(response, str) and "PRODUCT_INFO:" in response:
        first_line = response.split("\n")[0]
        parts = [p.strip() for p in first_line.split("|")]
        name = price = ""
        for p in parts:
            if p.startswith("PRODUCT_INFO:"):
                name = p.replace("PRODUCT_INFO:", "").strip()
            elif p.startswith("PRICE:"):
                price = p.replace("PRICE:", "").strip()
        confirm_text = (
            f"Excelente elección! 🍕 He agregado {name} por {price} a tu pedido. "
            "¿Te gustaría agregar algo más o proceder al pago?"
        )
        payload = build_text_message(recipient_waid, confirm_text)
    else:
        text_body = process_text_for_whatsapp(str(response))
        if text_body.startswith("¡Hola") and not is_first_message:
            return
        payload = build_text_message(recipient_waid, text_body)
    send_message(payload)


def is_valid_whatsapp_message(body):
    if not (
        body.get("object")
        and body.get("entry")
        and body["entry"][0].get("changes")
        and body["entry"][0]["changes"][0].get("value")
        and body["entry"][0]["changes"][0]["value"].get("messages")
        and body["entry"][0]["changes"][0]["value"]["messages"][0]
    ):
        return False
    from_id = body["entry"][0]["changes"][0]["value"]["messages"][0].get("from")
    if from_id in {
        current_app.config.get("RECIPIENT_WAID", ""),
        current_app.config.get("PHONE_NUMBER_ID", ""),
    }:
        return False
    return True
