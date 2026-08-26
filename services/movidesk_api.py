import os

import requests
from dotenv import load_dotenv

from core.sectors import build_filter, build_day_filter, build_open_filter

# Carrega as variáveis do arquivo .env automaticamente.
load_dotenv()

BASE_URL = os.getenv("MOVIDESK_BASE_URL", "https://api.movidesk.com/public/v1/tickets")


def get_tickets(setor="ti"):
    params = {
        "token": os.getenv("MOVIDESK_TOKEN"),
        "$select": "id,type,subject,category,urgency,status,baseStatus,ownerTeam,serviceFirstLevel,serviceSecondLevel,serviceThirdLevel,serviceFirstLevelId,createdDate,reopenedIn,lastActionDate,lifetimeWorkingTime,slaResponseDate,slaRealResponseDate,slaResponseTime,stoppedTimeWorkingTime,slaSolutionTime,slaSolutionDate",
        "$filter": build_filter(setor),
        "$expand": "owner($select=id,businessName)",
    }
    response = requests.get(BASE_URL, params=params, timeout=30)
    response.raise_for_status()
    return response.json()


# Campos necessários às métricas de gestão/performance (Dashboard 2). Sem $expand owner:
# o Dashboard 2 é agregado por setor, não por responsável, então dispensa o dado do dono.
_WINDOW_SELECT = (
    "id,baseStatus,ownerTeam,createdDate,resolvedIn,closedIn,canceledIn,"
    "slaResponseDate,slaRealResponseDate,slaSolutionDate,resolvedInFirstCall,"
    "slaSolutionChangedByUser,slaSolutionDateIsPaused"
)


def get_window_tickets(setor, desde, session=None, page_size=1000, max_pages=20):
    """Busca, com paginação, os tickets de um setor com atividade a partir de <desde>.

    Read-only, mesmo escopo de setor (via build_day_filter), porém com $select próprio do
    Dashboard 2 e paginação via $skip (o Movidesk não fornece contagem total; paramos
    quando uma página vem com menos itens que <page_size>). <session> opcional
    (requests.Session) reaproveita a conexão e reduz a latência entre páginas.
    """
    http = session or requests
    base = {
        "token": os.getenv("MOVIDESK_TOKEN"),
        "$select": _WINDOW_SELECT,
        "$filter": build_day_filter(setor, desde),
    }
    coletados = []
    for pagina in range(max_pages):
        params = {**base, "$top": page_size, "$skip": pagina * page_size}
        response = http.get(BASE_URL, params=params, timeout=60)
        response.raise_for_status()
        lote = response.json()
        coletados.extend(lote)
        if len(lote) < page_size:
            break
    return coletados


# $select do ticket: id + ownerTeam (a equipe); o dono vem no $expand. A equipe
# alimenta o filtro por equipe da tela de Fotos.
_OWNERS_SELECT = "id,ownerTeam"


def get_open_tickets_owners(session=None, page_size=1000, max_pages=20):
    """Busca, com paginação, os tickets EM ABERTO de QUALQUER equipe trazendo só o dono.

    Read-only. Base para a gestão de fotos de avatar: cobre todos os responsáveis com
    ticket aberto, sem recorte de setor (usa build_open_filter). Cada item traz `owner`
    (id + businessName); a deduplicação por responsável é feita na camada de domínio.
    Paginação via $skip (o Movidesk não fornece total; para quando a página vem com
    menos itens que page_size). <session> opcional reaproveita a conexão.
    """
    http = session or requests
    base = {
        "token": os.getenv("MOVIDESK_TOKEN"),
        "$select": _OWNERS_SELECT,
        "$filter": build_open_filter(),
        "$expand": "owner($select=id,businessName)",
    }
    coletados = []
    for pagina in range(max_pages):
        params = {**base, "$top": page_size, "$skip": pagina * page_size}
        response = http.get(BASE_URL, params=params, timeout=60)
        response.raise_for_status()
        lote = response.json()
        coletados.extend(lote)
        if len(lote) < page_size:
            break
    return coletados


if __name__ == "__main__":
    # Teste isolado da Etapa 1: busca os tickets e imprime um resumo.
    if not os.getenv("MOVIDESK_TOKEN"):
        raise SystemExit("MOVIDESK_TOKEN não definido. Crie o arquivo .env a partir do .env.example.")

    tickets = get_tickets()
    print(f"Tickets retornados: {len(tickets)}")
    for ticket in tickets[:5]:
        owner = (ticket.get("owner") or {}).get("businessName", "-")
        print(f"  #{ticket.get('id')} | {ticket.get('baseStatus')} | {owner} | {ticket.get('subject')}")
