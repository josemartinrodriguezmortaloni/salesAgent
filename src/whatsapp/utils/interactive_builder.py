from typing import List, Dict, Any, Optional

"""Utility helpers to build WhatsApp Cloud API payloads for the most common
interactive message types we use in this project.

Each function returns a **Python dict** ready to be serialised with
``json.dumps`` and POST-ed to the WhatsApp endpoint.  Keeping the payload as a
Python structure makes unit-testing easier and avoids double serialization
mistakes.

Only a subset of the full specification is covered — enough for our ordering
workflow (text, CTA URL, list, reply-buttons).  You can extend the helpers if
new use-cases appear.
"""

# ---------------------------------------------------------------------------
# Constants shared by all payloads
# ---------------------------------------------------------------------------

WHATSAPP_PRODUCT = "whatsapp"
RECIPIENT_TYPE = "individual"

# ---------------------------------------------------------------------------
# Text message
# ---------------------------------------------------------------------------


def build_text_message(recipient: str, body_text: str) -> Dict[str, Any]:
    """Return a simple text-only payload."""
    return {
        "messaging_product": WHATSAPP_PRODUCT,
        "recipient_type": RECIPIENT_TYPE,
        "to": recipient,
        "type": "text",
        "text": {
            "preview_url": False,
            "body": body_text,
        },
    }


# ---------------------------------------------------------------------------
# CTA-URL button message (single button)
# ---------------------------------------------------------------------------


def build_cta_url_message(
    recipient: str,
    body_text: str,
    button_text: str,
    url: str,
    *,
    header_text: Optional[str] = None,
    footer_text: Optional[str] = None,
) -> Dict[str, Any]:
    """Return a payload for an *interactive cta_url* message (one button)."""

    interactive: Dict[str, Any] = {
        "type": "cta_url",
        "body": {"text": body_text},
        "action": {
            "name": "cta_url",
            "parameters": {
                "display_text": button_text,  # text shown on button
                "url": url,
            },
        },
    }

    if header_text:
        interactive["header"] = {"type": "text", "text": header_text}
    if footer_text:
        interactive["footer"] = {"text": footer_text}

    return {
        "messaging_product": WHATSAPP_PRODUCT,
        "recipient_type": RECIPIENT_TYPE,
        "to": recipient,
        "type": "interactive",
        "interactive": interactive,
    }


# ---------------------------------------------------------------------------
# Interactive list message (menu)
# ---------------------------------------------------------------------------


def build_list_message(
    recipient: str,
    body_text: str,
    button_text: str,
    sections: List[Dict[str, Any]],
    *,
    header_text: Optional[str] = None,
    footer_text: Optional[str] = None,
) -> Dict[str, Any]:
    """Return a payload for an interactive list message.

    *sections* must follow the WhatsApp structure, e.g.::
        [
          {
            "title": "Our pizzas",
            "rows": [
              {"id": "pizza_muzza", "title": "Pizza muzzarella", "description": "$10"},
              ...
            ],
          }
        ]
    """

    interactive: Dict[str, Any] = {
        "type": "list",
        "body": {"text": body_text},
        "action": {
            "button": button_text,
            "sections": sections,
        },
    }

    if header_text:
        interactive["header"] = {"type": "text", "text": header_text}
    if footer_text:
        interactive["footer"] = {"text": footer_text}

    return {
        "messaging_product": WHATSAPP_PRODUCT,
        "recipient_type": RECIPIENT_TYPE,
        "to": recipient,
        "type": "interactive",
        "interactive": interactive,
    }


# ---------------------------------------------------------------------------
# Reply buttons (up to 3)
# ---------------------------------------------------------------------------


def build_reply_buttons_message(
    recipient: str,
    body_text: str,
    buttons: List[Dict[str, str]],  # each {"id": str, "title": str}
    *,
    header_text: Optional[str] = None,
    footer_text: Optional[str] = None,
) -> Dict[str, Any]:
    """Return a payload for an interactive *button* message."""
    if len(buttons) == 0 or len(buttons) > 3:
        raise ValueError("WhatsApp allows 1-3 reply buttons per message")

    interactive: Dict[str, Any] = {
        "type": "button",
        "body": {"text": body_text},
        "action": {
            "buttons": [
                {"type": "reply", "reply": {"id": b["id"], "title": b["title"]}}
                for b in buttons
            ]
        },
    }

    if header_text:
        interactive["header"] = {"type": "text", "text": header_text}
    if footer_text:
        interactive["footer"] = {"text": footer_text}

    return {
        "messaging_product": WHATSAPP_PRODUCT,
        "recipient_type": RECIPIENT_TYPE,
        "to": recipient,
        "type": "interactive",
        "interactive": interactive,
    }
