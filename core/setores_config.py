"""Configuração de exibição dos setores (backend MariaDB).

Espelha core/colaboradores.py: usa core/db.get_connection() e guarda SÓ o que foge do
padrão. Duas responsabilidades, ambas com LEITURA TOLERANTE (banco fora -> vazio, e o
painel cai no padrão do config/setores.json, sem quebrar as TVs):

1. setor_config: override do MODO de exibição por setor ('agregado' | 'por_equipe').
   Sem linha = usa o modo padrão do setores.json.
2. setor_equipes: lista de equipes (ownerTeam) descobertas por setor, mantida pelo robô
   mensal. Alimenta o rodízio 'por_equipe' junto com as equipes vivas dos tickets.

A ESCRITA propaga erro (SetorConfigError), pois quem grava (admin/robô) precisa saber.
"""
import pymysql

from core.db import DbConfigError, get_connection

_TABELA_CONFIG = "setor_config"
_TABELA_EQUIPES = "setor_equipes"
MODOS_VALIDOS = ("agregado", "por_equipe")


class SetorConfigError(RuntimeError):
    """Erro ao gravar a config de setores no banco."""


# ── Modo de exibição (override) ────────────────────────────────────────────────
def carregar_modos():
    """Overrides de modo como { setor: 'agregado'|'por_equipe' } (só as exceções).

    Tolerante: banco fora -> {} (o painel assume o padrão do setores.json).
    """
    try:
        con = get_connection()
    except DbConfigError:
        return {}
    try:
        with con.cursor() as cursor:
            cursor.execute(f"SELECT setor, exibicao FROM {_TABELA_CONFIG}")
            rows = cursor.fetchall()
    except pymysql.MySQLError:
        return {}
    finally:
        con.close()
    return {r["setor"]: r["exibicao"] for r in rows if r["exibicao"] in MODOS_VALIDOS}


def definir_modo(setor, modo, padrao=None):
    """Grava o modo de exibição do setor.

    Se <modo> for igual ao <padrao> do setores.json, REMOVE a linha (a tabela guarda só
    exceções). Retorna o modo gravado. Erros de banco viram SetorConfigError.
    """
    if modo not in MODOS_VALIDOS:
        raise SetorConfigError(f"Modo inválido: {modo!r}. Use um de {MODOS_VALIDOS}.")
    try:
        con = get_connection()
    except DbConfigError as exc:
        raise SetorConfigError(str(exc)) from exc
    try:
        with con.cursor() as cursor:
            if padrao is not None and modo == padrao:
                cursor.execute(f"DELETE FROM {_TABELA_CONFIG} WHERE setor = %s", (setor,))
            else:
                cursor.execute(
                    f"INSERT INTO {_TABELA_CONFIG} (setor, exibicao) VALUES (%s, %s) "
                    "ON DUPLICATE KEY UPDATE exibicao = VALUES(exibicao)",
                    (setor, modo),
                )
    except pymysql.MySQLError as exc:
        raise SetorConfigError(f"Falha ao gravar no banco: {exc}") from exc
    finally:
        con.close()
    return modo


# ── Equipes descobertas ────────────────────────────────────────────────────────
def carregar_equipes():
    """Equipes descobertas como { setor: [equipe, ...] } (ordenadas). Tolerante -> {}."""
    try:
        con = get_connection()
    except DbConfigError:
        return {}
    try:
        with con.cursor() as cursor:
            cursor.execute(f"SELECT setor, equipe FROM {_TABELA_EQUIPES} ORDER BY setor, equipe")
            rows = cursor.fetchall()
    except pymysql.MySQLError:
        return {}
    finally:
        con.close()
    mapa = {}
    for r in rows:
        mapa.setdefault(r["setor"], []).append(r["equipe"])
    return mapa


def equipes_de(setor, mapa=None):
    """Equipes descobertas de UM setor (lista, possivelmente vazia)."""
    mapa = carregar_equipes() if mapa is None else mapa
    return list(mapa.get(setor, []))


def substituir_equipes(setor, equipes):
    """Substitui (atômico) as equipes descobertas de um setor. Usado pelo robô/admin.

    Remove as antigas e insere a lista nova numa transação. Retorna a lista gravada
    (sem vazios/duplicatas). Erros de banco viram SetorConfigError.
    """
    novas = list(dict.fromkeys(e.strip() for e in equipes if e and e.strip()))
    try:
        con = get_connection()
    except DbConfigError as exc:
        raise SetorConfigError(str(exc)) from exc
    try:
        con.begin()
        with con.cursor() as cursor:
            cursor.execute(f"DELETE FROM {_TABELA_EQUIPES} WHERE setor = %s", (setor,))
            if novas:
                cursor.executemany(
                    f"INSERT INTO {_TABELA_EQUIPES} (setor, equipe) VALUES (%s, %s)",
                    [(setor, e) for e in novas],
                )
        con.commit()
    except pymysql.MySQLError as exc:
        con.rollback()
        raise SetorConfigError(f"Falha ao gravar equipes no banco: {exc}") from exc
    finally:
        con.close()
    return novas
