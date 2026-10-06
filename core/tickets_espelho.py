"""Espelho local de tickets do Movidesk (tabela `tickets_espelho`) — base das métricas.

Duas responsabilidades, sem acoplamento a HTTP (quem fala com o Movidesk é
services.movidesk_api):

1. DOMINIO (puro): ticket_para_linha() converte o ticket cru da API no dict de colunas
   da tabela (datas naive-UTC, como a API manda; o fuso é aplicado só na exibição).

2. BANCO: upsert_tickets() grava o lote (INSERT ... ON DUPLICATE KEY UPDATE por id) e
   ultima_marca() devolve o MAX(last_update) — a chave do sync incremental.
   Regras de ouro:
     * NUNCA deletamos linhas (ticket arquivado pelo Movidesk permanece no espelho —
       é justamente o que resolve o problema dos "fantasmas" daqui pra frente);
     * resposta vazia da API não apaga nem reconcilia nada (só não grava);
     * dados_json guarda a cópia crua do ticket, para aproveitar campos futuros sem
       re-coletar.
   Leitura TOLERANTE (banco fora -> None/[]), para nunca quebrar o app.
"""
import json
from datetime import datetime

import pymysql

from core.db import DbConfigError, get_connection

_TABELA = "tickets_espelho"


class TicketsEspelhoError(RuntimeError):
    """Erro ao gravar o espelho de tickets no banco."""


# Colunas gravadas pelo sync (sincronizado_em tem DEFAULT CURRENT_TIMESTAMP).
_COLUNAS = (
    "id", "type", "subject", "category", "urgency", "origin", "status", "base_status",
    "owner_id", "owner_nome", "owner_team", "created_by_nome", "cliente_org",
    "service_first_level", "service_second_level", "service_third_level",
    "created_date", "first_response_date", "resolved_in", "closed_in", "canceled_in",
    "reopened_in", "last_action_date", "last_update",
    "sla_response_date", "sla_response_time", "sla_solution_date", "sla_solution_time",
    "sla_solution_changed", "sla_solution_paused", "resolved_first_call",
    "dados_json",
)


def _dt(valor):
    """Converte data da API (ISO 8601, naive-UTC, com/sem 'Z' e milissegundos) -> datetime."""
    if not valor:
        return None
    texto = str(valor).strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(texto)
    except ValueError:
        return None
    return dt.replace(tzinfo=None)  # guarda naive-UTC


def _int(valor):
    """Converte para int; tolerante a None/lixo -> None."""
    try:
        return int(valor)
    except (TypeError, ValueError):
        return None


def _bool(valor):
    """Converte para 1/0; None permanece None."""
    if valor is None:
        return None
    return 1 if bool(valor) else 0


def ticket_para_linha(ticket):
    """Converte o ticket cru da API no dict de colunas da tabela (puro, sem banco)."""
    owner = ticket.get("owner") or {}
    created_by = ticket.get("createdBy") or {}
    clients = ticket.get("clients") or []
    primeiro_cliente = clients[0] if clients and isinstance(clients[0], dict) else {}
    return {
        "id": _int(ticket.get("id")),
        "type": _int(ticket.get("type")),
        "subject": ticket.get("subject"),
        "category": ticket.get("category"),
        "urgency": ticket.get("urgency"),
        "origin": _int(ticket.get("origin")),
        "status": ticket.get("status"),
        "base_status": ticket.get("baseStatus"),
        "owner_id": _int(owner.get("id")),
        "owner_nome": owner.get("businessName"),
        "owner_team": ticket.get("ownerTeam"),
        "created_by_nome": created_by.get("businessName"),
        "cliente_org": primeiro_cliente.get("businessName"),
        "service_first_level": ticket.get("serviceFirstLevel"),
        "service_second_level": ticket.get("serviceSecondLevel"),
        "service_third_level": ticket.get("serviceThirdLevel"),
        "created_date": _dt(ticket.get("createdDate")),
        "first_response_date": _dt(ticket.get("slaRealResponseDate")),
        "resolved_in": _dt(ticket.get("resolvedIn")),
        "closed_in": _dt(ticket.get("closedIn")),
        "canceled_in": _dt(ticket.get("canceledIn")),
        "reopened_in": _dt(ticket.get("reopenedIn")),
        "last_action_date": _dt(ticket.get("lastActionDate")),
        "last_update": _dt(ticket.get("lastUpdate")),
        "sla_response_date": _dt(ticket.get("slaResponseDate")),
        "sla_response_time": _int(ticket.get("slaResponseTime")),
        "sla_solution_date": _dt(ticket.get("slaSolutionDate")),
        "sla_solution_time": _int(ticket.get("slaSolutionTime")),
        "sla_solution_changed": _bool(ticket.get("slaSolutionChangedByUser")),
        "sla_solution_paused": _bool(ticket.get("slaSolutionDateIsPaused")),
        "resolved_first_call": _bool(ticket.get("resolvedInFirstCall")),
        "dados_json": json.dumps(ticket, ensure_ascii=False),
    }


def upsert_tickets(tickets):
    """Grava o lote de tickets crus da API no espelho (UPSERT por id). Transação única.

    <tickets>: lista de dicts crus da API (services.movidesk_api.get_tickets_espelho).
    Tickets sem id são descartados. Retorna {"upsertados": N}.
    Levanta TicketsEspelhoError se o banco falhar (quem chama decide: o robô loga e
    tenta de novo no próximo ciclo; nada é apagado).
    """
    linhas = [ticket_para_linha(t) for t in tickets or []]
    linhas = [l for l in linhas if l["id"] is not None]
    if not linhas:
        return {"upsertados": 0}
    colunas = ", ".join(_COLUNAS)
    placeholders = ", ".join(["%s"] * len(_COLUNAS))
    atualizacoes = ", ".join(
        f"{c}=VALUES({c})" for c in _COLUNAS if c != "id"
    )
    sql = (
        f"INSERT INTO {_TABELA} ({colunas}) VALUES ({placeholders}) "
        f"ON DUPLICATE KEY UPDATE {atualizacoes}, sincronizado_em=CURRENT_TIMESTAMP"
    )
    valores = [tuple(l[c] for c in _COLUNAS) for l in linhas]
    try:
        con = get_connection()
    except DbConfigError as exc:
        raise TicketsEspelhoError(str(exc)) from exc
    try:
        # autocommit vem ligado (core.db); begin() abre a transação explícita para
        # o lote ser atômico de verdade (tudo ou nada) — mesmo padrão de
        # core/colaboradores_movidesk.sincronizar e core/usuarios_mysql.
        con.begin()
        with con.cursor() as cursor:
            cursor.executemany(sql, valores)
        con.commit()
    except pymysql.MySQLError as exc:
        con.rollback()
        raise TicketsEspelhoError(str(exc)) from exc
    finally:
        con.close()
    return {"upsertados": len(linhas)}


def ultima_marca():
    """MAX(last_update) do espelho — ponto de partida do sync incremental.

    Tolerante: banco fora/tabela vazia -> None (o robô trata None como backfill).
    """
    try:
        con = get_connection()
    except DbConfigError:
        return None
    try:
        with con.cursor() as cursor:
            cursor.execute(f"SELECT MAX(last_update) AS marca FROM {_TABELA}")
            row = cursor.fetchone()
    except pymysql.MySQLError:
        return None
    finally:
        con.close()
    return row["marca"] if row else None
