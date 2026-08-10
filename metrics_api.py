"""Endpoint /api/metrics — painel do dia (raio-X do setor).

Blueprint desacoplado: registra-se em app.py via app.register_blueprint, sem alterar
as rotas existentes. Tem cache próprio por setor (isolado do cache da fila) e é
somente leitura sobre o Movidesk.
"""
import logging
import os
import threading
import time
from datetime import timedelta

import requests
from flask import Blueprint, abort, jsonify, request

from core import metrics
from core.tokens import resolve_sector
from services.movidesk_api import get_day_tickets, get_tickets

logger = logging.getLogger(__name__)

metrics_bp = Blueprint("metrics", __name__)

# Cache próprio (não compartilha estado com o cache da fila em app.py).
_METRICS_TTL_SECONDS = int(os.getenv("METRICS_CACHE_TTL_SECONDS", os.getenv("CACHE_TTL_SECONDS", "30")))
_metrics_cache = {}  # setor -> {"data": ..., "timestamp": ...}
_metrics_lock = threading.Lock()

# Janela usada para as médias (dias). O fluxo do dia é recortado dentro dela.
_JANELA_DIAS = 7

# Teto prático de itens por requisição do Movidesk; acima disso a janela pode truncar.
_LIMITE_MOVIDESK = 1000


def _redact(text):
    """Remove o token do Movidesk de qualquer texto antes de registrar em log."""
    token = os.getenv("MOVIDESK_TOKEN")
    return text.replace(token, "***") if token else text


def _calcular_metricas(setor):
    """Consulta o Movidesk (fila + janela) e monta o dicionário de métricas do setor."""
    inicio_dia = metrics.janela_dia_utc()
    desde_janela = metrics.para_odata(inicio_dia - timedelta(days=_JANELA_DIAS))
    abertos = get_tickets(setor)
    do_dia = get_day_tickets(setor, desde_janela)
    if len(do_dia) >= _LIMITE_MOVIDESK:
        logger.warning(
            "Janela de %s dias do setor '%s' atingiu o teto de %s itens; métricas podem truncar.",
            _JANELA_DIAS, setor, _LIMITE_MOVIDESK,
        )
    return metrics.montar_metricas(abertos, do_dia, inicio_dia)


def _metricas_cacheadas(setor):
    """Métricas do setor com cache TTL; só armazena resultados bem-sucedidos."""
    now = time.monotonic()
    with _metrics_lock:
        entry = _metrics_cache.get(setor)
        if entry and (now - entry["timestamp"]) < _METRICS_TTL_SECONDS:
            return entry["data"]
        data = _calcular_metricas(setor)
        _metrics_cache[setor] = {"data": data, "timestamp": now}
        return data


@metrics_bp.route("/api/metrics")
def api_metrics():
    setor = resolve_sector(request.args.get("token"))
    if setor is None:
        abort(404)
    try:
        data = _metricas_cacheadas(setor)
    except (requests.RequestException, ValueError) as exc:
        logger.warning("Falha ao calcular métricas (setor=%s): %s", setor, _redact(str(exc)))
        return jsonify({"error": "Não foi possível consultar o Movidesk."}), 503
    return jsonify(data)
