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

import requests
from flask import Blueprint, abort, jsonify, render_template, request, url_for

from core.auth import hash_senha
from core.avatars import AvatarConfigError, AvatarInvalido, listar_responsaveis, remover_foto, salvar_foto
from core.colaboradores import (
    ColaboradorConfigError,
    carregar_config as carregar_colaboradores,
    config_de,
    definir_exibir,
    definir_nome_exibicao,
)
from core.sectors import available_sectors, load_config, sector_display, setores_de
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
from services.movidesk_api import get_open_tickets_owners

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


def _setores_validos(setores):
    """Valida uma lista de setores. Retorna (lista_normalizada_sem_duplicatas, ok).

    Lista vazia é permitida (ex.: ADM não tem setor). Cada setor precisa existir.
    """
    if not isinstance(setores, list):
        return [], False
    normalizados = []
    for s in setores:
        s = str(s).strip()
        if not s:
            continue
        if s not in available_sectors():
            return [], False
        if s not in normalizados:
            normalizados.append(s)
    return normalizados, True


def _setores_e_primario(dados):
    """Extrai e valida os setores (lista) e o principal do payload.

    Aceita `setores` (lista) ou, por compatibilidade, `setor` (único). Retorna
    (setores, primario, erro); `erro` é None quando tudo é válido.
    """
    if "setores" in dados:
        setores, ok = _setores_validos(dados.get("setores"))
    else:
        setor, ok = _setor_valido(dados.get("setor"))
        setores = [setor] if setor else []
    if not ok:
        return [], None, "Setor inexistente."
    primario = (dados.get("setor_primario") or "").strip() or None
    if primario and primario not in setores:
        return [], None, "O setor principal precisa estar entre os setores do usuário."
    return setores, primario, None


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
        active="usuarios",
    )


@admin_bp.route("/admin/colaboradores")
@papel_obrigatorio("ADM")
def colaboradores():
    """Tela de gestão dos colaboradores (fotos dos responsáveis pelos tickets)."""
    setores = [{"chave": s, "nome": sector_display(s)["nome"]} for s in available_sectors()]
    return render_template("admin/colaboradores.html", setores=setores, active="colaboradores")


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
        usuarios = [u for u in usuarios if setor in (u.get("setores") or [])]
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
    setores, primario, erro = _setores_e_primario(dados)
    if erro:
        return jsonify({"erro": erro}), 400
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
        "setores": setores,
        "setor_primario": primario,
        "senha_hash": hash_senha(senha),
        "chapa": (dados.get("chapa") or None),
        "cargo": (dados.get("cargo") or None),
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
    if "setores" in dados or "setor" in dados:
        setores, primario, erro = _setores_e_primario(dados)
        if erro:
            return jsonify({"erro": erro}), 400
        campos["setores"] = setores
        campos["setor_primario"] = primario
    if "chapa" in dados:
        campos["chapa"] = (dados.get("chapa") or None)
    if "cargo" in dados:
        campos["cargo"] = (dados.get("cargo") or None)

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


# ── Fotos dos responsáveis (avatares) ──────────────────────────────────────────
def _foto_url(arquivo):
    """URL estática de uma foto (ou None). Isola a montagem de URL da camada de domínio."""
    return url_for("static", filename=f"avatars/{arquivo}") if arquivo else None


@admin_bp.route("/admin/api/responsaveis", methods=["GET"])
@papel_obrigatorio("ADM")
def api_responsaveis():
    """Lista os responsáveis com ticket aberto + a foto atual (ou None)."""
    try:
        tickets = get_open_tickets_owners()
    except (requests.RequestException, ValueError) as exc:
        logger.warning("Falha ao listar responsáveis: %s", exc)
        return jsonify({"erro": "Não foi possível consultar o Movidesk."}), 503
    itens = listar_responsaveis(tickets)
    cfg = load_config()
    colab = carregar_colaboradores()
    for item in itens:
        nome = item.get("nome")
        setores = set()
        for equipe in item.get("equipes") or []:
            setores.update(setores_de(equipe, nome, cfg))
        item["setores"] = sorted(setores)
        item["foto_url"] = _foto_url(item.get("arquivo"))
        conf = config_de(item.get("id"), colab)
        item["exibir"] = conf["exibir"]
        item["nome_exibicao"] = conf["nome_exibicao"]
    return jsonify(itens)


@admin_bp.route("/admin/api/responsaveis/<owner_id>/exibir", methods=["PUT"])
@papel_obrigatorio("ADM")
def api_exibir(owner_id):
    """Define se o colaborador aparece nos painéis (exibir=true/false)."""
    dados = request.get_json(silent=True) or {}
    try:
        conf = definir_exibir(owner_id, bool(dados.get("exibir")))
    except ColaboradorConfigError as exc:
        logger.warning("Falha ao definir exibir de %s: %s", owner_id, exc)
        return jsonify({"erro": "Não foi possível salvar."}), 503
    return jsonify(conf)


@admin_bp.route("/admin/api/responsaveis/<owner_id>/nome", methods=["PUT"])
@papel_obrigatorio("ADM")
def api_nome(owner_id):
    """Define o nome de exibição do colaborador nos painéis (vazio volta ao padrão)."""
    dados = request.get_json(silent=True) or {}
    try:
        conf = definir_nome_exibicao(owner_id, dados.get("nome"))
    except ColaboradorConfigError as exc:
        logger.warning("Falha ao definir nome de %s: %s", owner_id, exc)
        return jsonify({"erro": "Não foi possível salvar."}), 503
    return jsonify(conf)


@admin_bp.route("/admin/api/responsaveis/<owner_id>/foto", methods=["POST"])
@papel_obrigatorio("ADM")
def api_foto_upload(owner_id):
    arquivo = request.files.get("foto")
    if arquivo is None:
        return jsonify({"erro": "Envie o arquivo no campo 'foto'."}), 400
    try:
        nome = salvar_foto(owner_id, arquivo.read())
    except AvatarInvalido as exc:
        return jsonify({"erro": str(exc)}), 400
    except AvatarConfigError as exc:
        logger.warning("Falha ao salvar foto de %s: %s", owner_id, exc)
        return jsonify({"erro": "Não foi possível salvar a imagem."}), 500
    logger.info("ADM enviou foto do responsável %s (%s)", owner_id, nome)
    return jsonify({"id": str(owner_id), "arquivo": nome, "foto_url": _foto_url(nome)})


@admin_bp.route("/admin/api/responsaveis/<owner_id>/foto", methods=["DELETE"])
@papel_obrigatorio("ADM")
def api_foto_remover(owner_id):
    try:
        removido = remover_foto(owner_id)
    except AvatarInvalido as exc:
        return jsonify({"erro": str(exc)}), 400
    logger.info("ADM removeu a foto do responsável %s (havia=%s)", owner_id, removido)
    return jsonify({"id": str(owner_id), "removido": removido})
