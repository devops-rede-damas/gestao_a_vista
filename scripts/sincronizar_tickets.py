"""Robô de sincronização do espelho de tickets (tabela tickets_espelho).

Modos de uso (a partir da raiz do projeto, com o banco acessível):

  ./venv/Scripts/python.exe -m scripts.sincronizar_tickets
      INCREMENTAL (padrão, rodar a cada 15 min): busca só os tickets com
      lastUpdate >= última marca gravada no espelho, menos uma sobreposição de
      segurança de 10 minutos (cobre clock skew e gravações no mesmo segundo).
      Se o espelho estiver vazio, cai no backfill automaticamente.

  ./venv/Scripts/python.exe -m scripts.sincronizar_tickets --reconciliar
      RECONCILIAÇÃO (rodar 1x ao dia): re-varre a janela dos últimos 90 dias,
      pegando o que o incremental eventualmente perdeu.

  ./venv/Scripts/python.exe -m scripts.sincronizar_tickets --backfill
      BACKFILL (rodar 1x na implantação): varre TUDO que a API enxerga, do mais
      antigo ao mais novo. Filas de alto volume só trazem o piso de retenção da
      API — o histórico profundo se constrói daqui pra frente, com o robô ligado.

Regras de ouro: NUNCA deleta linhas; se a API falhar, aborta sem gravar nada
(o próximo ciclo tenta de novo). Em prod, o agendamento é via systemd timer
(mesmo padrão do descobrir_equipes).
"""
import sys
from datetime import datetime, timedelta, timezone

import requests
from dotenv import load_dotenv

load_dotenv(".env")

from core.tickets_espelho import TicketsEspelhoError, ultima_marca, upsert_tickets
from services.movidesk_api import iter_tickets_espelho

_OVERLAP_MINUTOS = 10       # sobreposição de segurança do incremental
_RECONCILIACAO_DIAS = 90    # janela da reconciliação diária


def _ponto_de_partida(modo):
    """Resolve o 'desde' (datetime UTC) de cada modo; None = backfill completo."""
    agora_utc = datetime.now(timezone.utc).replace(tzinfo=None)  # UTC naive (padrão do app)
    if modo == "--backfill":
        return None
    if modo == "--reconciliar":
        return agora_utc - timedelta(days=_RECONCILIACAO_DIAS)
    marca = ultima_marca()
    if marca is None:
        return None  # espelho vazio: primeira execução vira backfill
    return marca - timedelta(minutes=_OVERLAP_MINUTOS)


def main():
    modo = sys.argv[1] if len(sys.argv) > 1 else ""
    if modo not in ("", "--reconciliar", "--backfill"):
        raise SystemExit(f"Modo desconhecido: {modo} (use --reconciliar ou --backfill)")
    desde = _ponto_de_partida(modo)
    if desde is None:
        rotulo = "backfill"  # pedido explicito ou espelho vazio (1a execucao)
    else:
        rotulo = modo.lstrip("-") or "incremental"
    print(f"[sync] modo={rotulo} desde={desde or 'inicio'}")
    # Grava PÁGINA A PÁGINA (não acumula tudo em memória): se a API falhar no meio,
    # o progresso parcial já está no banco e a próxima execução continua dali —
    # o UPSERT por id torna a reexecução idempotente.
    total = 0
    try:
        with requests.Session() as sessao:
            for pagina in iter_tickets_espelho(desde, session=sessao):
                total += upsert_tickets(pagina)["upsertados"]
                print(f"[sync] ... {total} tickets gravados/atualizados")
    except TicketsEspelhoError as exc:
        raise SystemExit(f"[sync] ERRO ao gravar no banco: {exc}")
    if not total:
        print("[sync] Nenhum ticket retornado pela API. Nada a gravar.")
        return
    print(f"[sync] Concluído: {total} tickets gravados/atualizados no espelho.")


if __name__ == "__main__":
    main()
