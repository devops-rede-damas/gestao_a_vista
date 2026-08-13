"""Metricas de gestao/performance do Dashboard 2 (modulo PURO, sem IO).

Recebe listas de tickets crus do Movidesk e devolve numeros. Nao conhece Flask,
HTTP nem requests — assim permanece desacoplado e facil de testar. A coleta (que
alimenta estas funcoes) e responsabilidade de outra camada (fase posterior).

Convencoes:
- "abertos": fila em aberto agora -> usado so para o backlog (foto do momento).
- "janela":  tickets com atividade no periodo (inclui encerrados) -> base das metricas.
- Todos os tempos sao de RELOGIO (corridos), nao de expediente: o Movidesk nao
  fornece o tempo util de forma confiavel nesta conta (lifetimeWorkingTime vem vazio).
- Datas do Movidesk sao naive-UTC; comparacoes entre elas sao diretas.

Este modulo e intencionalmente SELF-CONTAINED (nao importa core.metrics) para manter
o painel do dia e o Dashboard 2 totalmente independentes. A pequena duplicacao do
parser de data e deliberada, como ja ocorre em core/metrics.py.
"""
from datetime import datetime, timedelta, timezone

# Fuso do negocio: dia civil de Brasilia (UTC-3, fixo; Brasil sem horario de verao
# desde 2019). Evita depender da base de fusos do SO, simplificando o deploy.
_FUSO_BRASILIA = timezone(timedelta(hours=-3))


def _dt(value):
    """Converte a data naive do Movidesk em datetime; ignora a fracao de segundo."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).split(".")[0])
    except (ValueError, TypeError):
        return None


def _fim_conclusao(ticket):
    """Datetime de conclusao do ticket: resolvedIn ou, na falta, closedIn."""
    return _dt(ticket.get("resolvedIn")) or _dt(ticket.get("closedIn"))


def _no_intervalo(dt, inicio, fim):
    """True se <dt> existe e esta em [inicio, fim) (fim=None => sem limite superior)."""
    return dt is not None and dt >= inicio and (fim is None or dt < fim)


# Campos de data que marcam "atividade" de um ticket (mesma nocao usada na janela do dia).
_CAMPOS_ATIVIDADE = ("createdDate", "resolvedIn", "closedIn", "canceledIn")


def filtrar_periodo(tickets, inicio, fim=None):
    """Subconjunto dos tickets com QUALQUER atividade em [inicio, fim).

    Usado para recortar uma janela ampla (ex.: 60 dias) em periodos menores (atual e
    anterior) sem precisar de uma nova consulta ao Movidesk.
    """
    return [
        t for t in tickets
        if any(_no_intervalo(_dt(t.get(campo)), inicio, fim) for campo in _CAMPOS_ATIVIDADE)
    ]


def _pct(parte, total):
    """Percentual (0..100) de parte/total, arredondado a 1 casa; None se total=0."""
    return round(parte / total * 100, 1) if total else None


def _media_minutos(pares):
    """Media em minutos de uma lista de (inicio, fim) datetimes; ignora invalidos/negativos."""
    duracoes = [
        (fim - ini).total_seconds() / 60.0
        for ini, fim in pares
        if ini and fim and fim >= ini
    ]
    if not duracoes:
        return None
    return round(sum(duracoes) / len(duracoes), 1)


def sla_primeira_resposta(tickets):
    """SLA da 1a resposta: compara slaRealResponseDate com o prazo slaResponseDate.

    So considera tickets COM prazo (slaResponseDate). 'aguardando' = tem prazo mas
    ainda nao houve 1a resposta (slaRealResponseDate vazio).
    """
    cumprido = estourado = aguardando = 0
    for t in tickets:
        prazo = _dt(t.get("slaResponseDate"))
        if prazo is None:
            continue
        real = _dt(t.get("slaRealResponseDate"))
        if real is None:
            aguardando += 1
        elif real <= prazo:
            cumprido += 1
        else:
            estourado += 1
    com_prazo = cumprido + estourado + aguardando
    return {
        "cumprido": cumprido,
        "estourado": estourado,
        "aguardando": aguardando,
        "com_prazo": com_prazo,
        "pct_cumprido": _pct(cumprido, com_prazo),
    }


def sla_solucao(tickets):
    """SLA de solucao: compara a conclusao (resolvedIn|closedIn) com o prazo slaSolutionDate.

    Expoe tambem quantos tiveram o prazo alterado a mao (slaSolutionChangedByUser) ou
    pausado (slaSolutionDateIsPaused), para o rodape de transparencia do dashboard.
    """
    cumprido = estourado = em_aberto = 0
    alterados = pausados = 0
    for t in tickets:
        prazo = _dt(t.get("slaSolutionDate"))
        if prazo is None:
            continue
        if t.get("slaSolutionChangedByUser"):
            alterados += 1
        if t.get("slaSolutionDateIsPaused"):
            pausados += 1
        fim = _fim_conclusao(t)
        if fim is None:
            em_aberto += 1
        elif fim <= prazo:
            cumprido += 1
        else:
            estourado += 1
    com_prazo = cumprido + estourado + em_aberto
    return {
        "cumprido": cumprido,
        "estourado": estourado,
        "em_aberto": em_aberto,
        "com_prazo": com_prazo,
        "pct_cumprido": _pct(cumprido, com_prazo),
        "alterados_manualmente": alterados,
        "pausados": pausados,
    }


def taxa_resolucao(tickets, inicio, fim=None):
    """Fluxo do periodo [inicio, fim): entraram (createdDate) x concluidos x saldo.

    'concluidos' conta cada ticket UMA vez se resolvedIn OU closedIn cair no periodo.
    Saldo = concluidos - entraram (negativo = resolveu mais do que entrou).
    """
    entraram = sum(1 for t in tickets if _no_intervalo(_dt(t.get("createdDate")), inicio, fim))
    concluidos = sum(1 for t in tickets if _no_intervalo(_fim_conclusao(t), inicio, fim))
    return {"entraram": entraram, "concluidos": concluidos, "saldo": concluidos - entraram}


def tempos_medios(tickets, minutos_uteis=None):
    """Tempos medios em minutos: 1a resposta e resolucao.

    'primeira_resposta' e 'resolucao' sao de RELOGIO corrido. Se <minutos_uteis> (uma
    funcao (inicio, fim)->minutos) for fornecida, calcula tambem 'primeira_resposta_util'
    em HORARIO UTIL de expediente (espelha o calculo do Movidesk); senao vem None.
    """
    primeira = _media_minutos(
        (_dt(t.get("createdDate")), _dt(t.get("slaRealResponseDate"))) for t in tickets
    )
    resolucao = _media_minutos(
        (_dt(t.get("createdDate")), _fim_conclusao(t)) for t in tickets
    )
    primeira_util = None
    if minutos_uteis is not None:
        vals = []
        for t in tickets:
            ini = _dt(t.get("createdDate"))
            fim = _dt(t.get("slaRealResponseDate"))
            if ini and fim and fim >= ini:
                m = minutos_uteis(ini, fim)
                if m is not None:
                    vals.append(m)
        primeira_util = round(sum(vals) / len(vals), 1) if vals else None
    return {
        "primeira_resposta": primeira,
        "primeira_resposta_util": primeira_util,
        "resolucao": resolucao,
    }


def fcr(tickets, inicio, fim=None):
    """FCR (First Contact Resolution): % de resolvedInFirstCall entre os concluidos no periodo."""
    concluidos = [t for t in tickets if _no_intervalo(_fim_conclusao(t), inicio, fim)]
    no_primeiro = sum(1 for t in concluidos if t.get("resolvedInFirstCall"))
    return {"concluidos": len(concluidos), "no_primeiro_contato": no_primeiro,
            "pct": _pct(no_primeiro, len(concluidos))}


def _data_local(value, fuso):
    """Data civil local (no <fuso>) de uma data naive-UTC do Movidesk; None se vazia."""
    dt = _dt(value)
    if dt is None:
        return None
    return dt.replace(tzinfo=timezone.utc).astimezone(fuso).date()


def evolucao_diaria(tickets, dias, ref_utc=None, fuso=_FUSO_BRASILIA):
    """Serie dos ultimos <dias> dias civis locais: entradas x concluidos por dia.

    Devolve lista do mais antigo ao mais recente. <ref_utc> (aware) permite injecao
    nos testes; por padrao usa agora.
    """
    if ref_utc is None:
        ref_utc = datetime.now(timezone.utc)
    hoje = ref_utc.astimezone(fuso).date()
    ordem = [hoje - timedelta(days=i) for i in range(dias - 1, -1, -1)]
    balde = {d: {"data": d.isoformat(), "entradas": 0, "concluidos": 0} for d in ordem}
    for t in tickets:
        de = _data_local(t.get("createdDate"), fuso)
        if de in balde:
            balde[de]["entradas"] += 1
        df = _data_local(t.get("resolvedIn") or t.get("closedIn"), fuso)
        if df in balde:
            balde[df]["concluidos"] += 1
    return [balde[d] for d in ordem]


def montar_performance(abertos, janela, inicio, fim=None, dias_evolucao=14, ref_utc=None,
                       minutos_uteis=None):
    """Monta o dicionario de metricas do Dashboard 2 para UMA janela (puro, sem IO).

    - abertos: fila em aberto agora -> backlog (foto do momento).
    - janela:  tickets com atividade no periodo [inicio, fim) -> base das metricas.
    - minutos_uteis: funcao (inicio, fim)->minutos de expediente (opcional; habilita o
      tempo medio de 1a resposta em horario util).
    """
    return {
        "backlog_atual": len(abertos),
        "sla_primeira_resposta": sla_primeira_resposta(janela),
        "sla_solucao": sla_solucao(janela),
        "fluxo": taxa_resolucao(janela, inicio, fim),
        "tempos_medios_min": tempos_medios(janela, minutos_uteis),
        "fcr": fcr(janela, inicio, fim),
        "evolucao_diaria": evolucao_diaria(janela, dias_evolucao, ref_utc),
    }


def _delta(atual, anterior):
    """Diferenca atual-anterior; None se qualquer lado for None."""
    if atual is None or anterior is None:
        return None
    return round(atual - anterior, 1)


def comparar_periodos(atual, anterior):
    """Deltas dos numeros-chave entre dois resultados de montar_performance (as setinhas)."""
    return {
        "sla_primeira_resposta_pct": _delta(
            atual["sla_primeira_resposta"]["pct_cumprido"],
            anterior["sla_primeira_resposta"]["pct_cumprido"],
        ),
        "sla_solucao_pct": _delta(
            atual["sla_solucao"]["pct_cumprido"], anterior["sla_solucao"]["pct_cumprido"]
        ),
        "fluxo_saldo": _delta(atual["fluxo"]["saldo"], anterior["fluxo"]["saldo"]),
        "tempo_primeira_resposta": _delta(
            atual["tempos_medios_min"]["primeira_resposta"],
            anterior["tempos_medios_min"]["primeira_resposta"],
        ),
        "tempo_primeira_resposta_util": _delta(
            atual["tempos_medios_min"].get("primeira_resposta_util"),
            anterior["tempos_medios_min"].get("primeira_resposta_util"),
        ),
        "tempo_resolucao": _delta(
            atual["tempos_medios_min"]["resolucao"], anterior["tempos_medios_min"]["resolucao"]
        ),
        "fcr_pct": _delta(atual["fcr"]["pct"], anterior["fcr"]["pct"]),
    }
