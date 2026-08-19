"""Backend MySQL/MariaDB dos usuários (mesmo contrato de core.usuarios).

Espelha as funções públicas de core.usuarios lendo/gravando a tabela
usuarios_gestor. A coluna única `setor` é mapeada para a lista `setores` que o
resto do app espera (login e autorização por setor). Selecionado quando
USUARIOS_BACKEND=mysql; caso contrário o backend JSON continua sendo o padrão.
"""
from core.db import get_connection

_TABELA = "usuarios_gestor"
_COLUNAS = "email, nome, papel, setor, senha_hash, ativo, chapa, perfil, imagem"


def _normalizar_email(email):
    """E-mail é a chave do login: sempre comparado em minúsculas e sem espaços."""
    return (email or "").strip().lower()


def _row_para_usuario(row):
    """Converte uma linha do banco no dict que o app espera (setor -> setores[])."""
    if row is None:
        return None
    setor = row.get("setor")
    usuario = {
        "email": row.get("email"),
        "nome": row.get("nome"),
        "papel": row.get("papel"),
        "setores": [setor] if setor else [],
        "senha_hash": row.get("senha_hash"),
        "ativo": bool(row.get("ativo", 1)),
    }
    # Campos extras (uso futuro no painel admin): só incluídos quando preenchidos.
    for extra in ("chapa", "perfil", "imagem"):
        if row.get(extra) is not None:
            usuario[extra] = row.get(extra)
    return usuario


def carregar_usuarios():
    """Lista todos os usuários cadastrados."""
    con = get_connection()
    try:
        with con.cursor() as cursor:
            cursor.execute(f"SELECT {_COLUNAS} FROM {_TABELA} ORDER BY id")
            return [_row_para_usuario(row) for row in cursor.fetchall()]
    finally:
        con.close()


def buscar_por_email(email):
    """Retorna o dict do usuário pelo e-mail (normalizado), ou None se não existir."""
    alvo = _normalizar_email(email)
    if not alvo:
        return None
    con = get_connection()
    try:
        with con.cursor() as cursor:
            cursor.execute(
                f"SELECT {_COLUNAS} FROM {_TABELA} WHERE LOWER(email) = %s LIMIT 1",
                (alvo,),
            )
            return _row_para_usuario(cursor.fetchone())
    finally:
        con.close()


def salvar_usuario(usuario):
    """Insere ou atualiza um usuário (chave = e-mail); faz merge no update.

    Mantém a semântica do backend JSON: os campos informados sobrescrevem os
    antigos e os demais são preservados (permite, por exemplo, trocar só a
    senha_hash sem apagar o setor). `setores[0]` é gravado na coluna `setor`.
    """
    email = _normalizar_email(usuario.get("email"))
    if not email:
        raise ValueError("Usuário sem e-mail.")
    merged = {**(buscar_por_email(email) or {}), **usuario, "email": email}
    setores = merged.get("setores") or []
    campos = {
        "email": email,
        "nome": merged.get("nome"),
        "papel": merged.get("papel", "gestor"),
        "setor": setores[0] if setores else None,
        "senha_hash": merged.get("senha_hash"),
        "ativo": 1 if merged.get("ativo", True) else 0,
        "chapa": merged.get("chapa"),
        "perfil": merged.get("perfil", "gestor"),
        "imagem": merged.get("imagem"),
    }
    colunas = ", ".join(campos)
    marcadores = ", ".join(["%s"] * len(campos))
    updates = ", ".join(f"{c}=VALUES({c})" for c in campos if c != "email")
    con = get_connection()
    try:
        with con.cursor() as cursor:
            cursor.execute(
                f"INSERT INTO {_TABELA} ({colunas}) VALUES ({marcadores}) "
                f"ON DUPLICATE KEY UPDATE {updates}",
                tuple(campos.values()),
            )
        return merged
    finally:
        con.close()


# ── Operações do painel de administração (papel ADM) ───────────────────────────
# Diferente do caminho de login (indexado por e-mail), o painel opera pela chave
# primária `id` — estável mesmo quando o e-mail é editado — e expõe os campos de
# cadastro (chapa/perfil/imagem) sem o senha_hash.

_COLUNAS_ADMIN = "id, email, nome, papel, setor, ativo, chapa, perfil, imagem"
_COLUNAS_EDITAVEIS = ("email", "nome", "papel", "setor", "chapa", "perfil", "imagem")


def _row_para_admin(row):
    """Linha do banco -> dict do painel (com id, setor cru, sem senha_hash)."""
    if row is None:
        return None
    return {
        "id": row.get("id"),
        "email": row.get("email"),
        "nome": row.get("nome"),
        "papel": row.get("papel"),
        "setor": row.get("setor"),
        "ativo": bool(row.get("ativo", 1)),
        "chapa": row.get("chapa"),
        "perfil": row.get("perfil"),
        "imagem": row.get("imagem"),
    }


def listar_para_admin():
    """Todos os usuários (ativos e inativos) para a tela de gestão, ordenados por nome."""
    con = get_connection()
    try:
        with con.cursor() as cursor:
            cursor.execute(f"SELECT {_COLUNAS_ADMIN} FROM {_TABELA} ORDER BY nome")
            return [_row_para_admin(row) for row in cursor.fetchall()]
    finally:
        con.close()


def buscar_por_id(uid):
    """Retorna o usuário (formato do painel) pela chave primária, ou None."""
    con = get_connection()
    try:
        with con.cursor() as cursor:
            cursor.execute(
                f"SELECT {_COLUNAS_ADMIN} FROM {_TABELA} WHERE id = %s LIMIT 1", (uid,)
            )
            return _row_para_admin(cursor.fetchone())
    finally:
        con.close()


def criar_usuario(dados):
    """Insere um novo usuário e retorna o registro criado (formato do painel)."""
    campos = {
        "email": _normalizar_email(dados.get("email")),
        "nome": dados.get("nome"),
        "papel": dados.get("papel", "gestor"),
        "setor": dados.get("setor"),
        "senha_hash": dados.get("senha_hash"),
        "ativo": 1 if dados.get("ativo", True) else 0,
        "chapa": dados.get("chapa"),
        "perfil": dados.get("perfil", dados.get("papel", "gestor")),
        "imagem": dados.get("imagem"),
    }
    colunas = ", ".join(campos)
    marcadores = ", ".join(["%s"] * len(campos))
    con = get_connection()
    try:
        with con.cursor() as cursor:
            cursor.execute(
                f"INSERT INTO {_TABELA} ({colunas}) VALUES ({marcadores})",
                tuple(campos.values()),
            )
            novo_id = cursor.lastrowid
        return buscar_por_id(novo_id)
    finally:
        con.close()


def atualizar_usuario(uid, campos):
    """Atualiza só as colunas informadas (whitelist) de um usuário por id; retorna o registro."""
    permitidos = {c: v for c, v in campos.items() if c in _COLUNAS_EDITAVEIS}
    if not permitidos:
        return buscar_por_id(uid)
    if "email" in permitidos:
        permitidos["email"] = _normalizar_email(permitidos["email"])
    sets = ", ".join(f"{c} = %s" for c in permitidos)
    valores = list(permitidos.values()) + [uid]
    con = get_connection()
    try:
        with con.cursor() as cursor:
            cursor.execute(f"UPDATE {_TABELA} SET {sets} WHERE id = %s", valores)
        return buscar_por_id(uid)
    finally:
        con.close()


def definir_senha(uid, senha_hash):
    """Grava um novo hash de senha para o usuário (por id)."""
    con = get_connection()
    try:
        with con.cursor() as cursor:
            cursor.execute(
                f"UPDATE {_TABELA} SET senha_hash = %s WHERE id = %s", (senha_hash, uid)
            )
    finally:
        con.close()


def definir_ativo(uid, ativo):
    """Ativa (1) ou inativa (0) o usuário por id. Inativar substitui a exclusão."""
    con = get_connection()
    try:
        with con.cursor() as cursor:
            cursor.execute(
                f"UPDATE {_TABELA} SET ativo = %s WHERE id = %s",
                (1 if ativo else 0, uid),
            )
    finally:
        con.close()
