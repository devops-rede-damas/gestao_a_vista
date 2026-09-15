import logging
import os
import secrets
import threading
import time
from datetime import datetime, timedelta

import requests
from dotenv import load_dotenv
from flask import Flask, abort, jsonify, redirect, render_template, request, session, url_for

from services.movidesk_api import get_tickets
from core.sectors import available_sectors, sector_display
from core.avatars import carregar_catalogo
from core.colaboradores import carregar_config as carregar_colaboradores
from core.webauth import auth_bp, login_obrigatorio, redirecionar_sem_acesso, resolver_usuario, setor_autorizado
from performance_api import performance_bp
from admin_api import admin_bp

load_dotenv()

logger = logging.getLogger(__name__)

app = Flask(__name__)

# Sessão do login (área de gestão). Sem SECRET_KEY o app ainda sobe para as TVs,
# mas com chave efêmera as sessões não persistem entre reinícios — só avisamos.
app.secret_key = os.getenv("SECRET_KEY") or secrets.token_urlsafe(32)
if not os.getenv("SECRET_KEY"):
    logger.warning("SECRET_KEY ausente no .env: usando chave efêmera (sessões não persistem entre reinícios).")
app.config.update(
    PERMANENT_SESSION_LIFETIME=timedelta(days=int(os.getenv("SESSION_DAYS", "7"))),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    # Só liga em HTTPS (fase internet); em http:// na intranet, True impediria o cookie.
    SESSION_COOKIE_SECURE=os.getenv("SESSION_COOKIE_SECURE", "false").lower() == "true",
)

app.register_blueprint(performance_bp)
app.register_blueprint(auth_bp)
app.register_blueprint(admin_bp)


@app.route("/")
def index():
    """Raiz do site: aponta para a tela de login (única URL canônica do login)."""
    return redirect(url_for("auth.login"))



@app.context_processor
def _inject_flags():
    """Flags de feature para os templates (Dashboard 2 é opt-in; padrão desligado)."""
    return {"mostrar_perf": os.getenv("DASHBOARD2", "false").lower() == "true"}

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


def _avatars_urls():
    """Mapa owner.id -> URL estatica da foto enviada (catalogo). {} se vazio/inexistente."""
    return {oid: url_for("static", filename=f"avatars/{arquivo}") for oid, arquivo in carregar_catalogo().items()}


def _nomes_exibicao():
    """Mapa owner.id -> nome de exibicao personalizado (so quem tem). {} se banco fora."""
    return {
        oid: cfg["nome_exibicao"]
        for oid, cfg in carregar_colaboradores().items()
        if cfg.get("nome_exibicao")
    }


def _setores_do_logado():
    """Setores do usuario logado (para o seletor do painel); vazio p/ TV/anonimo.

    O 1o item e o setor principal (a leitura ja ordena o principal primeiro).
    """
    usuario = session.get("usuario") or {}
    if usuario.get("papel") == "tv":
        return []
    return [{"chave": s, "nome": sector_display(s)["nome"]} for s in (usuario.get("setores") or [])]


def _filtrar_visiveis(tickets):
    """Remove os tickets cujo dono foi marcado para NAO exibir no painel (admin).

    A visibilidade vem da config por colaborador (core.colaboradores). Leitura tolerante:
    banco fora -> sem ocultos -> todos aparecem (o painel nunca quebra por isto).
    """
    ocultos = {oid for oid, cfg in carregar_colaboradores().items() if not cfg.get("exibir", True)}
    if not ocultos:
        return tickets
    return [t for t in tickets if str((t.get("owner") or {}).get("id") or "") not in ocultos]


@app.route("/gv_movidesk")
@login_obrigatorio
def gv_movidesk():
    if not setor_autorizado("ti"):
        return redirecionar_sem_acesso("ti")
    tickets = _filtrar_visiveis(_fetch_tickets("ti") or [])
    logado = session["usuario"].get("papel") != "tv"
    return render_template("gav-painel.html", tickets=tickets, setor="ti", exibicao=sector_display("ti"), logado=logado, avatars=_avatars_urls(), nomes=_nomes_exibicao(), setores_usuario=_setores_do_logado())


@app.route("/painel/<setor>")
@login_obrigatorio
def painel(setor):
    if setor not in available_sectors():
        abort(404)
    if not setor_autorizado(setor):
        return redirecionar_sem_acesso(setor)
    tickets = _filtrar_visiveis(_fetch_tickets(setor) or [])
    logado = session["usuario"].get("papel") != "tv"
    return render_template("gav-painel.html", tickets=tickets, setor=setor, exibicao=sector_display(setor), logado=logado, avatars=_avatars_urls(), nomes=_nomes_exibicao(), setores_usuario=_setores_do_logado())


@app.route("/api/tickets")
def api_tickets():
    setor = request.args.get("setor")
    if setor not in available_sectors():
        abort(404)
    if not resolver_usuario():
        abort(401)
    if not setor_autorizado(setor):
        abort(403)
    tickets = _fetch_tickets(setor)
    if tickets is None:
        return jsonify({"error": "Não foi possível consultar o Movidesk."}), 503
    return jsonify(_filtrar_visiveis(tickets))


if __name__ == "__main__":
    app.run(
        host=os.getenv("FLASK_HOST", "0.0.0.0"),
        port=int(os.getenv("FLASK_PORT", 7001)),
        debug=os.getenv("FLASK_DEBUG", "False").lower() == "true",
    )
