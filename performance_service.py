"""Coletor do Dashboard 2: busca a fila + a janela histórica, calcula as métricas de
performance (via core.performance) e guarda o resultado em cache na RAM.

Camada de aplicação (coleta + cache) do Dashboard 2, consumida pelo blueprint
performance_api. A coleta é LENTA (fala com a API) e roda em background; a leitura
(ler()) é instantânea (só cache). Cache/lock próprios, isolados do cache da fila (D1).

Regra de ouro: a coleta é LENTA (fala com a API) e deve rodar FORA do caminho do request
(em background). A leitura do dashboard usa apenas `ler()`, que é instantânea (só cache).
"""
import logging
import os
import threading
import time
from datetime import datetime, timedelta, timezone

import requests

from core import performance
from services.movidesk_api import get_tickets, get_window_tickets

logger = logging.getLogger(__name__)

# Tamanho da janela dos números-âncora (dias). A comparação "vs período anterior" usa
# o dobro (busca 2x a janela e recorta em memória em atual e anterior).
_JANELA_DIAS = int(os.getenv("PERF_WINDOW_DAYS", "30"))
_EVOLUCAO_DIAS = int(os.getenv("PERF_EVOLUCAO_DIAS", "14"))
_TTL_SEGUNDOS = int(os.getenv("PERF_CACHE_TTL_SECONDS", "300"))

_cache = {}  # setor -> {"data": ..., "timestamp": ...}
_lock = threading.Lock()

# Setores com coleta em andamento (evita empilhar coletas lentas do mesmo setor).
_inflight = set()
_inflight_lock = threading.Lock()


def _redact(text):
    """Remove o token do Movidesk de qualquer texto antes de registrar em log."""
    token = os.getenv("MOVIDESK_TOKEN")
    return text.replace(token, "***") if token else text


def _para_odata(dt_naive_utc):
    """Formata um datetime naive-UTC como literal de data-hora do OData/Movidesk."""
    return dt_naive_utc.strftime("%Y-%m-%dT%H:%M:%S.00z")


def coletar(setor, ref_utc=None, session=None):
    """Coleta LENTA (fala com o Movidesk): fila + janela de 2x_JANELA_DIAS dias.

    Recorta a janela ampla em período atual e anterior e devolve as métricas dos dois
    mais os deltas (as setinhas). <ref_utc> (aware) permite injeção nos testes.
    """
    ref = ref_utc or datetime.now(timezone.utc)
    ref_naive = ref.astimezone(timezone.utc).replace(tzinfo=None)
    inicio_atual = ref_naive - timedelta(days=_JANELA_DIAS)
    inicio_anterior = ref_naive - timedelta(days=2 * _JANELA_DIAS)

    abertos = get_tickets(setor)
    janela = get_window_tickets(setor, _para_odata(inicio_anterior), session=session)

    atual = performance.filtrar_periodo(janela, inicio_atual, ref_naive)
    anterior = performance.filtrar_periodo(janela, inicio_anterior, inicio_atual)

    perf_atual = performance.montar_performance(
        abertos, atual, inicio_atual, ref_naive, _EVOLUCAO_DIAS, ref
    )
    perf_anterior = performance.montar_performance([], anterior, inicio_anterior, inicio_atual)
    return {
        "gerado_em": ref.isoformat(),
        "janela_dias": _JANELA_DIAS,
        "atual": perf_atual,
        "anterior": perf_anterior,
        "comparacao": performance.comparar_periodos(perf_atual, perf_anterior),
    }


def atualizar(setor, session=None):
    """Executa a coleta lenta e grava no cache. Alvo do coletor em background (fase futura)."""
    data = coletar(setor, session=session)
    with _lock:
        _cache[setor] = {"data": data, "timestamp": time.monotonic()}
    return data


def ler(setor):
    """Leitura INSTANTÂNEA do cache (nunca chama o Movidesk). None se ainda não coletado."""
    with _lock:
        entry = _cache.get(setor)
        return entry["data"] if entry else None


def esta_fresco(setor):
    """True se há dado em cache dentro do TTL (para o background decidir se recoleta)."""
    with _lock:
        entry = _cache.get(setor)
        return bool(entry) and (time.monotonic() - entry["timestamp"]) < _TTL_SEGUNDOS


def _coleta_bg(setor):
    """Executa a coleta lenta em background e libera o setor ao final."""
    try:
        with requests.Session() as sessao:
            atualizar(setor, session=sessao)
    except Exception as exc:  # a thread nao pode morrer silenciosamente; registra e segue
        logger.warning("Falha na coleta de performance (setor=%s): %s", setor, _redact(str(exc)))
    finally:
        with _inflight_lock:
            _inflight.discard(setor)


def garantir_coleta(setor):
    """Dispara UMA coleta em background se o cache estiver ausente/vencido e nenhuma
    coleta do setor estiver em andamento. Retorna imediatamente (nunca bloqueia o request).
    """
    if esta_fresco(setor):
        return
    with _inflight_lock:
        if setor in _inflight:
            return
        _inflight.add(setor)
    threading.Thread(target=_coleta_bg, args=(setor,), daemon=True, name=f"perf-{setor}").start()
