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
