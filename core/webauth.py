"""Autenticação por sessão + acesso autenticado ao painel (Opção B).

Camada WEB do login. NÃO decide credenciais — delega para core.auth (plugável).
Aqui moram: o formulário/sessão, a guarda de autenticação (`login_obrigatorio`),
a autorização por setor (`setor_autorizado`) e o "remember-me" da TV — um cookie
assinado de longa duração que faz a TV re-logar sozinha após reiniciar, sem
mostrar a tela de login. Contas de TV têm papel "tv".
"""
import logging
import os
import time
from functools import wraps

from flask import (
    Blueprint, abort, current_app, flash, redirect, render_template, request, session, url_for
)
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from werkzeug.routing import BuildError

from core.auth import setores_do_usuario, verificar_credenciais
from core.sectors import available_sectors, sector_display
from core.usuarios import buscar_por_email

logger = logging.getLogger(__name__)

auth_bp = Blueprint("auth", __name__)

# Rate limiting simples (em memória, por processo): trava tentativas de login por
# chave (IP + e-mail) para dificultar força bruta. Suficiente para 1 worker; ao
# escalar para múltiplos processos, migrar para um armazenamento compartilhado.
_MAX_TENTATIVAS = 5
_JANELA_SEGUNDOS = 300
_tentativas = {}  # chave -> lista de timestamps (monotonic) das falhas recentes

# Cookie de lembrança da TV: permite a TV re-logar sozinha após reboot (papel "tv").
_REMEMBER_COOKIE = "tv_auth"


def _chave_rate(email):
    return f"{request.remote_addr}|{(email or '').strip().lower()}"


def _bloqueado(chave):
    """True se a chave excedeu o limite de falhas dentro da janela (e faz a limpeza)."""
    agora = time.monotonic()
    recentes = [t for t in _tentativas.get(chave, []) if agora - t < _JANELA_SEGUNDOS]
    _tentativas[chave] = recentes
    return len(recentes) >= _MAX_TENTATIVAS


def _registrar_falha(chave):
    _tentativas.setdefault(chave, []).append(time.monotonic())


# ── Remember-me da TV (cookie assinado de longa duração) ───────────────────────
def _remember_max_age():
    return int(os.getenv("TV_REMEMBER_DAYS", "3650")) * 86400


def _cookie_secure():
    return os.getenv("SESSION_COOKIE_SECURE", "false").lower() == "true"


def _serializer():
    return URLSafeTimedSerializer(current_app.secret_key, salt="tv-remember")


def _email_do_remember(token):
    try:
        return _serializer().loads(token, max_age=_remember_max_age())
    except (BadSignature, SignatureExpired):
        return None


def _dados_sessao(usuario):
    """Dict guardado na sessão a partir do usuário (sem o hash da senha)."""
    return {
        "email": usuario.get("email"),
        "nome": usuario.get("nome"),
        "papel": usuario.get("papel"),
        "setores": setores_do_usuario(usuario),
    }


def _autenticar_por_remember():
    """Cookie de lembrança de TV válido -> recria a sessão e retorna o usuário; senão None."""
    token = request.cookies.get(_REMEMBER_COOKIE)
    if not token:
        return None
    email = _email_do_remember(token)
    if not email:
        return None
    usuario = buscar_por_email(email)
    # Só contas de TV ativas podem re-logar por cookie (revogável: ativo=false).
    if not usuario or not usuario.get("ativo", True) or usuario.get("papel") != "tv":
        return None
    dados = _dados_sessao(usuario)
    session.clear()
    session["usuario"] = dados
    session.permanent = True
    return dados


def resolver_usuario():
    """Usuário autenticado: da sessão, ou via cookie de lembrança (recria a sessão). None se anônimo."""
    return session.get("usuario") or _autenticar_por_remember()


def login_obrigatorio(view):
    """Exige autenticação (sessão ou cookie de TV); sem ela, redireciona para /login."""
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not resolver_usuario():
            return redirect(url_for("auth.login"))
        return view(*args, **kwargs)
    return wrapper


def papel_obrigatorio(papel):
    """Exige autenticação E que o usuário tenha o `papel` informado.

    Sem sessão -> redireciona para /login; autenticado mas com papel diferente -> 403.
    Comparação sem distinção de maiúsculas/minúsculas (ex.: 'ADM'). Segue a mesma
    forma de `login_obrigatorio`, servindo de guarda para as rotas do painel admin.
    """
    def decorador(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            usuario = resolver_usuario()
            if not usuario:
                return redirect(url_for("auth.login"))
            if (usuario.get("papel") or "").upper() != papel.upper():
                abort(403)
            return view(*args, **kwargs)
        return wrapper
    return decorador


def setor_autorizado(setor):
    """True se o usuário autenticado tem acesso ao setor (cada um vê só o seu)."""
    usuario = session.get("usuario") or {}
    return setor in (usuario.get("setores") or [])


def _painel_do_usuario(usuario_sessao):
    """URL do painel do 1o setor VÁLIDO do usuário, ou None (setor ausente/inexistente)."""
    setores = (usuario_sessao or {}).get("setores") or []
    setor = next((s for s in setores if s in available_sectors()), None)
    return url_for("painel", setor=setor) if setor else None


def _destino_pos_login(usuario_sessao):
    """Para onde mandar o usuário após o login.

    ADM vai SEMPRE para o painel de gestão de usuários (independente de setor). Caso
    o blueprint admin ainda não esteja registrado (fase de implementação incremental),
    cai graciosamente no destino por setor — preservando o login dos ADMs atuais.
    Os demais papéis (gestor/TV) continuam indo para o painel do seu 1º setor válido.
    """
    if (usuario_sessao or {}).get("papel") == "ADM":
        try:
            return url_for("admin.usuarios")
        except BuildError:
            pass  # rota admin ainda não existe: usa o comportamento por setor
    return _painel_do_usuario(usuario_sessao)


def redirecionar_sem_acesso(setor_pedido):
    """403 amigável (só para rotas de PÁGINA): avisa e leva o usuário para o painel dele.

    Troca a tela crua "Forbidden" por um redirect para onde o usuário PODE ir. O
    destino é sempre autorizado, então não há loop. O aviso é de uso único (flash)
    e o template do painel só o exibe para logados — a TV nunca o renderiza. As
    rotas de API NÃO usam isto: mantêm abort(403/401) por serem consumidas via fetch.
    """
    usuario = session.get("usuario") or {}
    destino = _destino_pos_login(usuario)
    if not destino:
        session.clear()  # sem setor válido: recomeça o login (evita redirect em círculo)
        return redirect(url_for("auth.login"))
    # ADM vai para a área de gestão (que não exibe toast); não enfileira aviso órfão.
    if usuario.get("papel") != "ADM":
        nome = sector_display(setor_pedido).get("nome") or setor_pedido
        flash(f"Você não tem acesso ao setor {nome}. Exibindo o seu painel.", "aviso")
    return redirect(destino)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if session.get("usuario"):
        destino = _destino_pos_login(session["usuario"])
        if destino:
            return redirect(destino)
        session.clear()  # sessão sem setor: recomeça o login

    if request.method == "POST":
        email = request.form.get("email", "")
        senha = request.form.get("senha", "")
        chave = _chave_rate(email)

        if _bloqueado(chave):
            return render_template("login.html", erro="Muitas tentativas. Aguarde alguns minutos e tente novamente."), 429

        usuario = verificar_credenciais(email, senha)
        if not usuario:
            _registrar_falha(chave)
            logger.info("Falha de login para %s", (email or "").strip().lower())
            # Mensagem genérica: não revela se o e-mail existe.
            return render_template("login.html", erro="Credenciais inválidas."), 401

        _tentativas.pop(chave, None)
        session.clear()  # evita fixação de sessão: começa uma sessão limpa no login
        session["usuario"] = _dados_sessao(usuario)
        # TV: sessão longa (+ cookie remember).
        # Gestor: sessão de navegador — ao fechar o navegador precisa logar de novo (pede login+senha sempre).
        session.permanent = usuario.get("papel") == "tv"

        destino = _destino_pos_login(session["usuario"])
        if not destino:
            session.clear()
            logger.warning("Usuário sem setor configurado: %s", usuario.get("email"))
            return render_template("login.html", erro="Usuário sem setor configurado. Contate o administrador."), 403

        resp = redirect(destino)
        # Conta de TV: emite o cookie de lembrança (re-login automático após reboot).
        if usuario.get("papel") == "tv":
            resp.set_cookie(
                _REMEMBER_COOKIE, _serializer().dumps(session["usuario"]["email"]),
                max_age=_remember_max_age(), httponly=True, samesite="Lax", secure=_cookie_secure(),
            )
        return resp

    return render_template("login.html")


@auth_bp.route("/logout")
def logout():
    session.clear()
    resp = redirect(url_for("auth.login"))
    resp.delete_cookie(_REMEMBER_COOKIE)
    return resp

