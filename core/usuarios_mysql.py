"""Backend MySQL/MariaDB dos usuários (mesmo contrato de core.usuarios).

Espelha as funções públicas de core.usuarios lendo/gravando a tabela
usuarios_gestor. Os setores vivem na tabela de junção usuario_setores (1 usuário
-> N setores) e são lidos agregados na lista `setores` que o resto do app espera
(login e autorização por setor). Selecionado quando USUARIOS_BACKEND=mysql; caso
contrário o backend JSON continua sendo o padrão.
"""
from core.db import get_connection

_TABELA = "usuarios_gestor"

# Os setores agora vivem na tabela de junção usuario_setores (1 usuário -> N setores).
# As leituras trazem os setores agregados (principal primeiro) por um LEFT JOIN; a
# coluna antiga usuarios_gestor.setor ficou adormecida (removida numa migration futura).
_SETORES_JOIN = "LEFT JOIN usuario_setores us ON us.usuario_id = g.id"
_SETORES_SELECT = (
    "GROUP_CONCAT(us.setor ORDER BY us.primario DESC, us.setor SEPARATOR ',') AS setores, "
    "MAX(CASE WHEN us.primario = 1 THEN us.setor END) AS setor_primario"
)
_COLUNAS_LOGIN = "g.email, g.nome, g.papel, g.senha_hash, g.ativo, g.chapa, g.cargo, g.imagem"


def _normalizar_email(email):
    """E-mail é a chave do login: sempre comparado em minúsculas e sem espaços."""
    return (email or "").strip().lower()


def _lista_setores(valor):
    """Converte o GROUP_CONCAT ('ti,dp') na lista ['ti','dp']; vazio -> []."""
    return [s for s in (valor or "").split(",") if s]


def _row_para_usuario(row):
    """Converte uma linha do banco no dict que o app espera (setores agregados da junção)."""
    if row is None:
        return None
    usuario = {
        "email": row.get("email"),
        "nome": row.get("nome"),
        "papel": row.get("papel"),
        "setores": _lista_setores(row.get("setores")),
        "senha_hash": row.get("senha_hash"),
        "ativo": bool(row.get("ativo", 1)),
    }
    if row.get("setor_primario"):
        usuario["setor_primario"] = row.get("setor_primario")
    # Campos extras (uso futuro no painel admin): só incluídos quando preenchidos.
    for extra in ("chapa", "cargo", "imagem"):
        if row.get(extra) is not None:
            usuario[extra] = row.get(extra)
    return usuario


def _definir_setores(cursor, usuario_id, setores, primario=None):
    """Substitui os vínculos de setor do usuário (DELETE + INSERT) na junção.

    Deduplica preservando a ordem; o setor `primario` (ou o 1º, se não informado
    ou inválido) recebe a marca de principal. Deve rodar dentro de uma transação.
    """
    setores = [s for s in dict.fromkeys(setores) if s]
    cursor.execute("DELETE FROM usuario_setores WHERE usuario_id = %s", (usuario_id,))
    if not setores:
        return
    if primario not in setores:
        primario = setores[0]
    cursor.executemany(
        "INSERT INTO usuario_setores (usuario_id, setor, primario) VALUES (%s, %s, %s)",
        [(usuario_id, s, 1 if s == primario else 0) for s in setores],
    )


def carregar_usuarios():
    """Lista todos os usuários cadastrados (com os setores agregados da junção)."""
    con = get_connection()
    try:
        with con.cursor() as cursor:
            cursor.execute(
                f"SELECT {_COLUNAS_LOGIN}, {_SETORES_SELECT} "
                f"FROM {_TABELA} g {_SETORES_JOIN} GROUP BY g.id ORDER BY g.id"
            )
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
                f"SELECT {_COLUNAS_LOGIN}, {_SETORES_SELECT} "
                f"FROM {_TABELA} g {_SETORES_JOIN} "
                f"WHERE LOWER(g.email) = %s GROUP BY g.id LIMIT 1",
                (alvo,),
            )
            return _row_para_usuario(cursor.fetchone())
    finally:
        con.close()


def salvar_usuario(usuario):
    """Insere ou atualiza um usuário (chave = e-mail); faz merge no update.

    Mantém a semântica do backend JSON: os campos informados sobrescrevem os
    antigos e os demais são preservados (permite, por exemplo, trocar só a
    senha_hash sem apagar os setores). Os setores são gravados na junção
    usuario_setores (o 1º da lista, ou setor_primario, vira o principal).
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
        "senha_hash": merged.get("senha_hash"),
        "ativo": 1 if merged.get("ativo", True) else 0,
        "chapa": merged.get("chapa"),
        "cargo": merged.get("cargo", "gestor"),
        "imagem": merged.get("imagem"),
    }
    colunas = ", ".join(campos)
    marcadores = ", ".join(["%s"] * len(campos))
    updates = ", ".join(f"{c}=VALUES({c})" for c in campos if c != "email")
    con = get_connection()
    try:
        con.begin()
        with con.cursor() as cursor:
            cursor.execute(
                f"INSERT INTO {_TABELA} ({colunas}) VALUES ({marcadores}) "
                f"ON DUPLICATE KEY UPDATE {updates}",
                tuple(campos.values()),
            )
            cursor.execute(f"SELECT id FROM {_TABELA} WHERE email = %s", (email,))
            usuario_id = cursor.fetchone()["id"]
            _definir_setores(cursor, usuario_id, setores, merged.get("setor_primario"))
        con.commit()
        return merged
    finally:
        con.close()


# ── Operações do painel de administração (papel ADM) ───────────────────────────
# Diferente do caminho de login (indexado por e-mail), o painel opera pela chave
# primária `id` — estável mesmo quando o e-mail é editado — e expõe os campos de
# cadastro (chapa/cargo/imagem) sem o senha_hash.

_COLUNAS_ADMIN = "g.id, g.email, g.nome, g.papel, g.ativo, g.chapa, g.cargo, g.imagem"
_COLUNAS_EDITAVEIS = ("email", "nome", "papel", "chapa", "cargo", "imagem")


def _row_para_admin(row):
    """Linha do banco -> dict do painel (com id e setores da junção, sem senha_hash)."""
    if row is None:
        return None
    primario = row.get("setor_primario")
    return {
        "id": row.get("id"),
        "email": row.get("email"),
        "nome": row.get("nome"),
        "papel": row.get("papel"),
        "setores": _lista_setores(row.get("setores")),
        "setor_primario": primario,
        # Compat com a UI atual (um setor); a Etapa 3 passa a usar `setores`.
        "setor": primario,
        "ativo": bool(row.get("ativo", 1)),
        "chapa": row.get("chapa"),
        "cargo": row.get("cargo"),
        "imagem": row.get("imagem"),
    }


def listar_para_admin():
    """Todos os usuários (ativos e inativos) para a tela de gestão, ordenados por nome."""
    con = get_connection()
    try:
        with con.cursor() as cursor:
            cursor.execute(
                f"SELECT {_COLUNAS_ADMIN}, {_SETORES_SELECT} "
                f"FROM {_TABELA} g {_SETORES_JOIN} GROUP BY g.id ORDER BY g.nome"
            )
            return [_row_para_admin(row) for row in cursor.fetchall()]
    finally:
        con.close()


def buscar_por_id(uid):
    """Retorna o usuário (formato do painel) pela chave primária, ou None."""
    con = get_connection()
    try:
        with con.cursor() as cursor:
            cursor.execute(
                f"SELECT {_COLUNAS_ADMIN}, {_SETORES_SELECT} "
                f"FROM {_TABELA} g {_SETORES_JOIN} WHERE g.id = %s GROUP BY g.id LIMIT 1",
                (uid,),
            )
            return _row_para_admin(cursor.fetchone())
    finally:
        con.close()


def _setores_de_entrada(dados):
    """Extrai a lista de setores do payload aceitando `setores` (lista) ou `setor` (único)."""
    if dados.get("setores") is not None:
        return list(dados.get("setores") or [])
    setor = dados.get("setor")
    return [setor] if setor else []


def criar_usuario(dados):
    """Insere um novo usuário (+ seus setores na junção) e retorna o registro criado."""
    campos = {
        "email": _normalizar_email(dados.get("email")),
        "nome": dados.get("nome"),
        "papel": dados.get("papel", "gestor"),
        "senha_hash": dados.get("senha_hash"),
        "ativo": 1 if dados.get("ativo", True) else 0,
        "chapa": dados.get("chapa"),
        "cargo": dados.get("cargo", dados.get("papel", "gestor")),
        "imagem": dados.get("imagem"),
    }
    colunas = ", ".join(campos)
    marcadores = ", ".join(["%s"] * len(campos))
    con = get_connection()
    try:
        con.begin()
        with con.cursor() as cursor:
            cursor.execute(
                f"INSERT INTO {_TABELA} ({colunas}) VALUES ({marcadores})",
                tuple(campos.values()),
            )
            novo_id = cursor.lastrowid
            _definir_setores(cursor, novo_id, _setores_de_entrada(dados), dados.get("setor_primario"))
        con.commit()
        return buscar_por_id(novo_id)
    finally:
        con.close()


def atualizar_usuario(uid, campos):
    """Atualiza as colunas informadas (whitelist) e/ou os setores (junção) de um usuário."""
    campos = dict(campos)
    # Os setores vão para a junção, não para uma coluna: aceita `setores` ou `setor`.
    tem_setores = "setores" in campos or "setor" in campos
    setores = _setores_de_entrada(campos) if tem_setores else None
    primario = campos.pop("setor_primario", None)
    campos.pop("setores", None)
    campos.pop("setor", None)
    permitidos = {c: v for c, v in campos.items() if c in _COLUNAS_EDITAVEIS}
    if not permitidos and setores is None:
        return buscar_por_id(uid)
    if "email" in permitidos:
        permitidos["email"] = _normalizar_email(permitidos["email"])
    con = get_connection()
    try:
        con.begin()
        with con.cursor() as cursor:
            if permitidos:
                sets = ", ".join(f"{c} = %s" for c in permitidos)
                cursor.execute(
                    f"UPDATE {_TABELA} SET {sets} WHERE id = %s",
                    list(permitidos.values()) + [uid],
                )
            if setores is not None:
                _definir_setores(cursor, uid, setores, primario)
        con.commit()
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
