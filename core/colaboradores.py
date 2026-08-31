"""Configuração por colaborador: visibilidade no painel e nome de exibição (backend MariaDB).

Espelha o padrão de core/usuarios_mysql.py: usa core/db.get_connection() e a tabela
`colaboradores_config` (chave = owner.id do Movidesk). Guarda SÓ as exceções — um
colaborador no padrão (exibir=True, sem nome) não tem linha. Os DEFAULTS são aplicados
aqui, então, enquanto ninguém configura nada, os painéis funcionam como antes.

Robustez das TVs: a LEITURA (carregar_config/config_de) é tolerante — se o banco estiver
indisponível, devolve vazio e o painel assume o padrão (todos visíveis), sem quebrar. A
ESCRITA (definir_*) propaga o erro, pois o admin precisa saber que não salvou.
"""
import pymysql

from core.db import DbConfigError, get_connection

_TABELA = "colaboradores_config"
_PADRAO = {"exibir": True, "nome_exibicao": None}


class ColaboradorConfigError(RuntimeError):
    """Erro ao gravar a config de colaboradores no banco."""


def _normalizar_nome(valor):
    """Nome de exibição normalizado: string não vazia (aparada) ou None."""
    if not valor:
        return None
    texto = str(valor).strip()
    return texto or None


def carregar_config():
    """Todas as exceções como { owner_id: {"exibir": bool, "nome_exibicao": str|None} }.

    Tolerante a falhas (para as TVs nunca quebrarem): banco fora -> {} (assume padrão).
    """
    try:
        con = get_connection()
    except DbConfigError:
        return {}
    try:
        with con.cursor() as cursor:
            cursor.execute(f"SELECT owner_id, exibir, nome_exibicao FROM {_TABELA}")
            rows = cursor.fetchall()
    except pymysql.MySQLError:
        return {}
    finally:
        con.close()
    return {
        str(r["owner_id"]): {
            "exibir": bool(r["exibir"]),
            "nome_exibicao": _normalizar_nome(r.get("nome_exibicao")),
        }
        for r in rows
    }


def config_de(owner_id, config=None):
    """Config de UM colaborador, já com os defaults aplicados (exibir=True, nome=None)."""
    config = carregar_config() if config is None else config
    return dict(config.get(str(owner_id), _PADRAO))


def _gravar_campo(owner_id, campo, valor):
    """Aplica um campo (merge com a linha atual) e ENXUGA quem voltou ao default.

    Registro no padrão (exibir=True e sem nome) é REMOVIDO — a tabela guarda só exceções.
    Retorna a config final do colaborador. Erros de banco viram ColaboradorConfigError.
    """
    oid = str(owner_id)
    try:
        con = get_connection()
    except DbConfigError as exc:
        raise ColaboradorConfigError(str(exc)) from exc
    try:
        with con.cursor() as cursor:
            cursor.execute(f"SELECT exibir, nome_exibicao FROM {_TABELA} WHERE owner_id = %s", (oid,))
            row = cursor.fetchone()
            registro = {
                "exibir": bool(row["exibir"]) if row else True,
                "nome_exibicao": _normalizar_nome(row.get("nome_exibicao")) if row else None,
            }
            registro[campo] = valor
            if registro["exibir"] is True and not registro["nome_exibicao"]:
                cursor.execute(f"DELETE FROM {_TABELA} WHERE owner_id = %s", (oid,))
            else:
                cursor.execute(
                    f"INSERT INTO {_TABELA} (owner_id, exibir, nome_exibicao) VALUES (%s, %s, %s) "
                    "ON DUPLICATE KEY UPDATE exibir = VALUES(exibir), nome_exibicao = VALUES(nome_exibicao)",
                    (oid, 1 if registro["exibir"] else 0, registro["nome_exibicao"]),
                )
    except pymysql.MySQLError as exc:
        raise ColaboradorConfigError(f"Falha ao gravar no banco: {exc}") from exc
    finally:
        con.close()
    return {"exibir": registro["exibir"], "nome_exibicao": registro["nome_exibicao"]}


def definir_exibir(owner_id, exibir):
    """Define se o colaborador aparece nos painéis (True/False). Retorna a config dele."""
    return _gravar_campo(owner_id, "exibir", bool(exibir))


def definir_nome_exibicao(owner_id, nome):
    """Define o nome de exibição (string) ou o remove (None/''). Retorna a config dele."""
    return _gravar_campo(owner_id, "nome_exibicao", _normalizar_nome(nome))
