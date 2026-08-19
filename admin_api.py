"""Painel de administração de usuários (papel ADM) — blueprint isolado.

Registrado em app.py sem alterar as rotas existentes. Segue o padrão do projeto
(ver performance_api.py): o blueprint só cabeia HTTP — valida a requisição,
formata a resposta e delega TODA a regra para core/. Refactor-ready: é nomeado
"admin" (url_for estável) e não carrega lógica de negócio, para poder migrar
para um pacote web/ no futuro sem quebrar URLs nem imports.

Identidade dos usuários aqui é a chave primária `id` (estável mesmo quando o
e-mail é editado), diferente do caminho de login (indexado por e-mail).
Exclusão não existe: usuários são apenas ativados/inativados (ativo=0).
"""
import logging
import secrets

from flask import Blueprint, abort, jsonify, render_template, request

from core.auth import hash_senha
from core.sectors import available_sectors, sector_display
from core.usuarios import (
    atualizar_usuario,
    buscar_por_email,
    buscar_por_id,
    criar_usuario,
    definir_ativo,
    definir_senha,
    listar_para_admin,
)
from core.webauth import papel_obrigatorio

logger = logging.getLogger(__name__)

admin_bp = Blueprint("admin", __name__)

_PAPEIS_VALIDOS = {"gestor", "tv", "ADM"}
_SENHA_MIN = 8


def _email_valido(email):
    """Normaliza e valida minimamente um e-mail; retorna o e-mail normalizado ou None."""
    email = (email or "").strip().lower()
    if not email or "@" not in email or " " in email:
        return None
    return email


def _setor_valido(setor):
    """Valida o setor. Retorna (setor_normalizado_ou_None, ok).

    Vazio/None é permitido (ex.: ADM não tem setor). Preenchido precisa existir
    na configuração de setores.
    """
    if setor is None or str(setor).strip() == "":
        return None, True
    setor = str(setor).strip()
    if setor not in available_sectors():
        return None, False
    return setor, True


# ── Página (HTML) ──────────────────────────────────────────────────────────────
@admin_bp.route("/admin/usuarios")
@papel_obrigatorio("ADM")
def usuarios():
    """Tela de gestão de usuários (destino do redirect pós-login do ADM)."""
    setores = [{"chave": s, "nome": sector_display(s)["nome"]} for s in available_sectors()]
    return render_template(
        "admin/usuarios.html",
        setores=setores,
        papeis=sorted(_PAPEIS_VALIDOS),
    )


# ── API (JSON) ─────────────────────────────────────────────────────────────────
@admin_bp.route("/admin/api/usuarios", methods=["GET"])
@papel_obrigatorio("ADM")
def api_listar():
    """Lista os usuários. Filtros opcionais ?q= (nome/chapa) e ?setor= (o DataTable
    também filtra no cliente; aqui é conveniência/robustez)."""
    usuarios = listar_para_admin()
    termo = (request.args.get("q") or "").strip().lower()
    setor = (request.args.get("setor") or "").strip()
    if termo:
        usuarios = [
            u for u in usuarios
            if termo in (u.get("nome") or "").lower()
            or termo in (u.get("chapa") or "").lower()
        ]
    if setor:
        usuarios = [u for u in usuarios if (u.get("setor") or "") == setor]
    return jsonify(usuarios)


@admin_bp.route("/admin/api/usuarios/<int:uid>", methods=["GET"])
@papel_obrigatorio("ADM")
def api_obter(uid):
    usuario = buscar_por_id(uid)
    if not usuario:
        abort(404)
    return jsonify(usuario)


@admin_bp.route("/admin/api/usuarios", methods=["POST"])
@papel_obrigatorio("ADM")
def api_criar():
    dados = request.get_json(silent=True) or {}

    email = _email_valido(dados.get("email"))
    if not email:
        return jsonify({"erro": "E-mail inválido."}), 400
    nome = (dados.get("nome") or "").strip()
    if not nome:
        return jsonify({"erro": "Nome é obrigatório."}), 400
    papel = (dados.get("papel") or "gestor").strip()
    if papel not in _PAPEIS_VALIDOS:
        return jsonify({"erro": f"Papel inválido. Use: {', '.join(sorted(_PAPEIS_VALIDOS))}."}), 400
    setor, ok = _setor_valido(dados.get("setor"))
    if not ok:
        return jsonify({"erro": "Setor inexistente."}), 400
    if buscar_por_email(email):
        return jsonify({"erro": "Já existe um usuário com esse e-mail."}), 409

    senha = dados.get("senha")
    senha_temporaria = None
    if not senha:
        senha = senha_temporaria = secrets.token_urlsafe(9)
    elif len(senha) < _SENHA_MIN:
        return jsonify({"erro": f"A senha deve ter ao menos {_SENHA_MIN} caracteres."}), 400

    novo = criar_usuario({
        "email": email,
        "nome": nome,
        "papel": papel,
        "setor": setor,
        "senha_hash": hash_senha(senha),
        "chapa": (dados.get("chapa") or None),
        "perfil": (dados.get("perfil") or papel),
        "ativo": 1,
    })
    logger.info("ADM criou usuário %s (id=%s)", email, novo.get("id"))
    resposta = {"usuario": novo}
    if senha_temporaria:
        resposta["senha_temporaria"] = senha_temporaria
    return jsonify(resposta), 201


@admin_bp.route("/admin/api/usuarios/<int:uid>", methods=["PUT"])
@papel_obrigatorio("ADM")
def api_atualizar(uid):
    atual = buscar_por_id(uid)
    if not atual:
        abort(404)
    dados = request.get_json(silent=True) or {}
    campos = {}

    if "email" in dados:
        email = _email_valido(dados.get("email"))
        if not email:
            return jsonify({"erro": "E-mail inválido."}), 400
        # E-mail diferente que já pertence a outra conta -> conflito.
        if email != atual["email"] and buscar_por_email(email):
            return jsonify({"erro": "Já existe um usuário com esse e-mail."}), 409
        campos["email"] = email
    if "nome" in dados:
        nome = (dados.get("nome") or "").strip()
        if not nome:
            return jsonify({"erro": "Nome é obrigatório."}), 400
        campos["nome"] = nome
    if "papel" in dados:
        papel = (dados.get("papel") or "").strip()
        if papel not in _PAPEIS_VALIDOS:
            return jsonify({"erro": f"Papel inválido. Use: {', '.join(sorted(_PAPEIS_VALIDOS))}."}), 400
        campos["papel"] = papel
    if "setor" in dados:
        setor, ok = _setor_valido(dados.get("setor"))
        if not ok:
            return jsonify({"erro": "Setor inexistente."}), 400
        campos["setor"] = setor
    if "chapa" in dados:
        campos["chapa"] = (dados.get("chapa") or None)
    if "perfil" in dados:
        campos["perfil"] = (dados.get("perfil") or None)

    if not campos:
        return jsonify({"erro": "Nada para atualizar."}), 400
    atualizado = atualizar_usuario(uid, campos)
    logger.info("ADM atualizou usuário id=%s (%s)", uid, ", ".join(campos))
    return jsonify(atualizado)


@admin_bp.route("/admin/api/usuarios/<int:uid>/senha", methods=["PUT"])
@papel_obrigatorio("ADM")
def api_senha(uid):
    if not buscar_por_id(uid):
        abort(404)
    dados = request.get_json(silent=True) or {}
    senha = dados.get("senha") or ""
    if len(senha) < _SENHA_MIN:
        return jsonify({"erro": f"A senha deve ter ao menos {_SENHA_MIN} caracteres."}), 400
    definir_senha(uid, hash_senha(senha))
    logger.info("ADM alterou a senha do usuário id=%s", uid)
    return jsonify({"ok": True})


@admin_bp.route("/admin/api/usuarios/<int:uid>/ativo", methods=["PUT"])
@papel_obrigatorio("ADM")
def api_ativo(uid):
    if not buscar_por_id(uid):
        abort(404)
    dados = request.get_json(silent=True) or {}
    ativo = bool(dados.get("ativo"))
    definir_ativo(uid, ativo)
    logger.info("ADM %s o usuário id=%s", "ativou" if ativo else "inativou", uid)
    return jsonify({"id": uid, "ativo": ativo})
