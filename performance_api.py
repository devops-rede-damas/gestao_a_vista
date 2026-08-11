"""Endpoint /api/metrics2 — Dashboard 2 (gestão / performance).

Blueprint desacoplado, registrado em app.py sem alterar as rotas existentes. NÃO consulta
o Movidesk no caminho do request: apenas LÊ o cache do performance_service e dispara, em
background, a coleta quando o cache está ausente/vencido. Assim o dashboard responde de
imediato e a latência da API nunca trava a tela.
"""
import logging

from flask import Blueprint, abort, jsonify, request

import performance_service
from core.tokens import resolve_sector

logger = logging.getLogger(__name__)

performance_bp = Blueprint("performance", __name__)


@performance_bp.route("/api/metrics2")
def api_metrics2():
    setor = resolve_sector(request.args.get("token"))
    if setor is None:
        abort(404)
    performance_service.garantir_coleta(setor)  # background; não bloqueia o request
    data = performance_service.ler(setor)
    if data is None:
        # Ainda não há dado em cache: a coleta acabou de ser disparada. O front reconsulta.
        return jsonify({"status": "carregando"}), 202
    return jsonify(data)
