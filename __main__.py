#!/usr/bin/env python
import logging

from src.whatsapp import create_app

app = create_app()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    logging.info("Flask app started")
    app.run(host="0.0.0.0", port=8000)
