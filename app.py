import logging
import os

import requests
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template

from services.movidesk_api import get_tickets

load_dotenv()

logger = logging.getLogger(__name__)

app = Flask(__name__)


def _fetch_tickets():
    """Consulta o Movidesk isolando a camada web de falhas de rede/HTTP."""
    try:
        return get_tickets()
    except (requests.RequestException, ValueError) as exc:
        logger.warning("Falha ao consultar tickets no Movidesk: %s", exc)
        return None


@app.route("/gv_movidesk")
def gv_movidesk():
    tickets = _fetch_tickets()
    return render_template("gta.html", tickets=tickets or [])


@app.route("/api/tickets")
def api_tickets():
    tickets = _fetch_tickets()
    if tickets is None:
        return jsonify({"error": "Não foi possível consultar o Movidesk."}), 503
    return jsonify(tickets)


if __name__ == "__main__":
    app.run(
        host=os.getenv("FLASK_HOST", "0.0.0.0"),
        port=int(os.getenv("FLASK_PORT", 7001)),
        debug=os.getenv("FLASK_DEBUG", "True").lower() == "true",
    )
