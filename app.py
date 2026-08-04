import logging
import os
import threading
import time

import requests
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template

from services.movidesk_api import get_tickets

load_dotenv()

logger = logging.getLogger(__name__)

app = Flask(__name__)

# Cache em memória com TTL para reduzir chamadas ao Movidesk (várias telas/refreshes).
_CACHE_TTL_SECONDS = int(os.getenv("CACHE_TTL_SECONDS", "30"))
_tickets_cache = {"data": None, "timestamp": 0.0}
_cache_lock = threading.Lock()


def _get_tickets_cached():
    """Retorna os tickets usando cache com TTL; só armazena respostas bem-sucedidas."""
    now = time.monotonic()
    with _cache_lock:
        age = now - _tickets_cache["timestamp"]
        if _tickets_cache["data"] is not None and age < _CACHE_TTL_SECONDS:
            return _tickets_cache["data"]
        data = get_tickets()
        _tickets_cache["data"] = data
        _tickets_cache["timestamp"] = now
        return data


def _fetch_tickets():
    """Consulta o Movidesk isolando a camada web de falhas de rede/HTTP."""
    try:
        return _get_tickets_cached()
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
        debug=os.getenv("FLASK_DEBUG", "False").lower() == "true",
    )
