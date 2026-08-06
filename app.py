import logging
import os
import threading
import time
from datetime import datetime

import requests
from dotenv import load_dotenv
from flask import Flask, abort, jsonify, render_template, request

from services.movidesk_api import get_tickets
from core.tokens import resolve_sector, ensure_token

load_dotenv()

logger = logging.getLogger(__name__)

app = Flask(__name__)

# Cache em memória com TTL, por setor, para reduzir chamadas ao Movidesk (várias telas/refreshes).
_CACHE_TTL_SECONDS = int(os.getenv("CACHE_TTL_SECONDS", "30"))
_tickets_cache = {}  # setor -> {"data": ..., "timestamp": ...}
_cache_lock = threading.Lock()


def _parse_movidesk_datetime(value):
    """Converte a data naive do Movidesk em datetime; ignora a fração de segundo."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.split(".")[0])
    except (ValueError, TypeError):
        return None


def _format_br_datetime(value):
    """Formata a data naive do Movidesk como dd/mm/aaaa HH:MM, sem deslocar o fuso."""
    dt = _parse_movidesk_datetime(value)
    return dt.strftime("%d/%m/%Y %H:%M") if dt else None


def _sla_status(ticket, now):
    """Classifica o SLA da 1a resposta (semantica do piloto, sem o bug de -3h)."""
    respondido = bool(ticket.get("slaRealResponseDate"))
    prazo = _parse_movidesk_datetime(ticket.get("slaResponseDate"))
    if not respondido and prazo is not None:
        return "SLA a Vencer" if prazo > now else "SLA Vencido"
    if (ticket.get("baseStatus") or "").lower() == "new":
        return "Ticket Novo"
    return ""


def _enrich_tickets(tickets):
    now = datetime.now()
    for ticket in tickets:
        ticket["slaResponseDateFmt"] = _format_br_datetime(ticket.get("slaResponseDate"))
        ticket["slaStatus"] = _sla_status(ticket, now)


def _get_tickets_cached(setor="ti"):
    """Retorna os tickets do setor usando cache com TTL; só armazena respostas bem-sucedidas."""
    now = time.monotonic()
    with _cache_lock:
        entry = _tickets_cache.get(setor)
        if entry and entry["data"] is not None and (now - entry["timestamp"]) < _CACHE_TTL_SECONDS:
            return entry["data"]
        data = get_tickets(setor)
        _enrich_tickets(data)
        _tickets_cache[setor] = {"data": data, "timestamp": now}
        return data


def _redact(text):
    """Remove o token do Movidesk de qualquer texto antes de registrar em log."""
    token = os.getenv("MOVIDESK_TOKEN")
    return text.replace(token, "***") if token else text


def _fetch_tickets(setor="ti"):
    """Consulta o Movidesk isolando a camada web de falhas de rede/HTTP."""
    try:
        return _get_tickets_cached(setor)
    except (requests.RequestException, ValueError) as exc:
        logger.warning("Falha ao consultar tickets no Movidesk (setor=%s): %s", setor, _redact(str(exc)))
        return None


@app.route("/gv_movidesk")
def gv_movidesk():
    tickets = _fetch_tickets("ti")
    return render_template("gta.html", tickets=tickets or [], token=ensure_token("ti"))


@app.route("/painel/<token>")
def painel(token):
    setor = resolve_sector(token)
    if setor is None:
        abort(404)
    tickets = _fetch_tickets(setor)
    return render_template("gta.html", tickets=tickets or [], token=token)


@app.route("/api/tickets")
def api_tickets():
    setor = resolve_sector(request.args.get("token"))
    if setor is None:
        abort(404)
    tickets = _fetch_tickets(setor)
    if tickets is None:
        return jsonify({"error": "Não foi possível consultar o Movidesk."}), 503
    return jsonify(tickets)


if __name__ == "__main__":
    app.run(
        host=os.getenv("FLASK_HOST", "0.0.0.0"),
        port=int(os.getenv("FLASK_PORT", 7001)),
        debug=os.getenv("FLASK_DEBUG", "False").lower() == "true",
    )
