"""Cálculo das métricas do painel do dia.

Módulo puro: recebe listas de tickets (dicionários crus do Movidesk) e devolve números.
Não conhece Flask, HTTP nem fuso horário — assim permanece desacoplado e fácil de testar.
O recorte temporal (o que é "hoje") é decidido por quem chama, que passa datas já resolvidas; aqui só comparamos.

Convenção de vocabulário:
- "abertos": tickets da fila (em aberto agora)  -> métricas de SITUAÇÃO ATUAL.
- "do dia":  tickets com atividade no período   -> métricas de FLUXO.

Observação: os tempos médios são de RELÓGIO (corridos), não "tempo útil" de
expediente — o Movidesk não fornece o tempo útil de forma confiável nesta conta.
"""
from datetime import datetime, timedelta, timezone

# Fuso do negócio: o "dia" do painel é o dia civil de Brasília (UTC-3). O Brasil não
# observa horário de verão desde 2019, então um deslocamento fixo é suficiente e evita
# depender da base de fusos do SO (tzdata), simplificando o deploy no Windows.
_FUSO_BRASILIA = timezone(timedelta(hours=-3))


def _parse_dt(value):
    """Converte a data naive do Movidesk em datetime; ignora a fração de segundo.

    Réplica intencional e mínima do parser da camada web: a camada pura (core) não
    deve importar de app.py, para não inverter a dependência entre camadas.
    """
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).split(".")[0])
    except (ValueError, TypeError):
        return None


def _base_status(ticket):
    return (ticket.get("baseStatus") or "").lower()


def contar_por_status(tickets, status):
    """Quantos tickets estão em determinado baseStatus (ex.: 'New', 'InAttendance', 'Stopped')."""
    alvo = status.lower()
    return sum(1 for t in tickets if _base_status(t) == alvo)


def contar_sem_primeira_resposta(tickets):
    """Quantos tickets ainda não tiveram a primeira resposta (slaRealResponseDate vazio)."""
    return sum(1 for t in tickets if not t.get("slaRealResponseDate"))


def contar_atividade(tickets, campo, desde):
    """Conta tickets cujo <campo> de data é >= <desde> (datetime). Datas ausentes/inválidas não contam."""
    total = 0
    for t in tickets:
        dt = _parse_dt(t.get(campo))
        if dt is not None and dt >= desde:
            total += 1
    return total


def tempo_medio_minutos(tickets, campo_inicio, campo_fim):
    """Média, em minutos, de (<campo_fim> - <campo_inicio>) sobre os tickets que têm ambos.

    Devolve None quando não há amostra. Ignora durações negativas (dados inconsistentes).
    """
    duracoes = []
    for t in tickets:
        ini = _parse_dt(t.get(campo_inicio))
        fim = _parse_dt(t.get(campo_fim))
        if ini and fim and fim >= ini:
            duracoes.append((fim - ini).total_seconds() / 60.0)
    if not duracoes:
        return None
    return round(sum(duracoes) / len(duracoes), 1)


def janela_dia_utc(agora_utc=None, fuso=_FUSO_BRASILIA):
    """Início do dia civil local (meia-noite no <fuso>) convertido para UTC.

    Devolve um datetime NAIVE em UTC, compatível com as datas naive-UTC do Movidesk.
    <agora_utc> permite injeção nos testes (datetime timezone-aware); por padrão usa agora.
    """
    if agora_utc is None:
        agora_utc = datetime.now(timezone.utc)
    inicio_local = agora_utc.astimezone(fuso).replace(hour=0, minute=0, second=0, microsecond=0)
    return inicio_local.astimezone(timezone.utc).replace(tzinfo=None)


def para_odata(dt_utc_naive):
    """Formata um datetime naive-UTC como literal de data-hora do OData/Movidesk."""
    return dt_utc_naive.strftime("%Y-%m-%dT%H:%M:%S.00z")


def montar_metricas(abertos, do_dia, inicio_dia):
    """Monta o dicionário de métricas do painel do dia (puro, sem IO).

    - abertos: fila em aberto agora  -> situação atual (foto do momento).
    - do_dia:  tickets com atividade na janela (superset do dia; ex.: últimos 7 dias)
      -> fluxo do dia (recortado por <inicio_dia>) e tempos médios da janela.
    - inicio_dia: datetime naive-UTC do começo do dia civil local.
    """
    return {
        "situacao_atual": {
            "novos": contar_por_status(abertos, "New"),
            "em_atendimento": contar_por_status(abertos, "InAttendance"),
            "parados": contar_por_status(abertos, "Stopped"),
            "sem_primeira_resposta": contar_sem_primeira_resposta(abertos),
            "total_aberto": len(abertos),
        },
        "fluxo_dia": {
            "criados": contar_atividade(do_dia, "createdDate", inicio_dia),
            "resolvidos": contar_atividade(do_dia, "resolvedIn", inicio_dia),
            "fechados": contar_atividade(do_dia, "closedIn", inicio_dia),
            "cancelados": contar_atividade(do_dia, "canceledIn", inicio_dia),
        },
        "tempos_medios_janela_min": {
            "primeira_resposta": tempo_medio_minutos(do_dia, "createdDate", "slaRealResponseDate"),
            "atendimento": tempo_medio_minutos(do_dia, "createdDate", "resolvedIn"),
        },
    }
