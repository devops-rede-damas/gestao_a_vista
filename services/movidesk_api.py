import os

import requests
from dotenv import load_dotenv

from core.sectors import build_filter, build_day_filter, build_open_filter

# Carrega as variáveis do arquivo .env automaticamente.
load_dotenv()

BASE_URL = os.getenv("MOVIDESK_BASE_URL", "https://api.movidesk.com/public/v1/tickets")
# Raiz da API publica (ex.: https://api.movidesk.com/public/v1), derivada de BASE_URL
# (que aponta para .../tickets). O /persons compartilha a mesma raiz e o mesmo token.
PERSONS_URL = f"{BASE_URL.rsplit('/', 1)[0]}/persons"


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


# $select do agente: id + nome + situacao (ativo) + equipes. profileType 3 = Agente
# (1/2 sao clientes). O id e o mesmo owner.id dos tickets, entao casa com a config atual.
_AGENTES_SELECT = "id,businessName,isActive,teams"
_PROFILE_TYPE_AGENTE = 3


def get_agentes(session=None, page_size=1000, max_pages=10):
    """Busca, com paginacao, os AGENTES (colaboradores) cadastrados no Movidesk.

    Read-only. Consome /persons filtrando profileType eq 3 (agentes; clientes ficam de
    fora) e traz id, businessName, isActive e teams (lista de nomes de equipe). Devolve
    TODOS os agentes — ativos e inativos —; filtrar por situacao/equipe e responsabilidade
    da camada de dominio (core.colaboradores_movidesk). Paginacao via $skip, no mesmo
    padrao de get_open_tickets_owners. <session> opcional reaproveita a conexao.
    """
    http = session or requests
    base = {
        "token": os.getenv("MOVIDESK_TOKEN"),
        "$select": _AGENTES_SELECT,
        "$filter": f"profileType eq {_PROFILE_TYPE_AGENTE}",
    }
    coletados = []
    for pagina in range(max_pages):
        params = {**base, "$top": page_size, "$skip": pagina * page_size}
        response = http.get(PERSONS_URL, params=params, timeout=60)
        response.raise_for_status()
        lote = response.json()
        coletados.extend(lote)
        if len(lote) < page_size:
            break
    return coletados


# $select do espelho de tickets (tabela tickets_espelho): todos os campos que o sync
# grava, incluindo lastUpdate (chave do incremental). O dono/criador/cliente vêm no
# $expand. A cópia crua (dados_json) garante os demais campos sem custo extra.
_ESPELHO_SELECT = (
    "id,type,subject,category,urgency,origin,status,baseStatus,ownerTeam,"
    "serviceFirstLevel,serviceSecondLevel,serviceThirdLevel,"
    "createdDate,slaRealResponseDate,resolvedIn,closedIn,canceledIn,reopenedIn,"
    "lastActionDate,lastUpdate,"
    "slaResponseDate,slaResponseTime,slaSolutionDate,slaSolutionTime,"
    "slaSolutionChangedByUser,slaSolutionDateIsPaused,resolvedInFirstCall"
)
_ESPELHO_EXPAND = (
    "owner($select=id,businessName),"
    "createdBy($select=businessName),"
    "clients($select=businessName)"
)


def iter_tickets_espelho(desde=None, session=None, page_size=1000, max_paginas=500):
    """Gera, página a página, os tickets para o ESPELHO local (tabela tickets_espelho).

    Read-only, SEM recorte de setor (o espelho é de TODOS os setores; o recorte por
    setor é derivado na leitura, via setores_de). <desde> (datetime UTC) ativa o modo
    INCREMENTAL: só tickets com lastUpdate >= <desde> (quem chamou deve aplicar uma
    pequena sobreposição de segurança). <desde>=None é o BACKFILL: varre tudo que a
    API enxerga.

    É um GERADOR (yield de uma página por vez) para o consumidor gravar cada página
    assim que ela chega: se a API falhar no meio, o progresso parcial já está salvo
    e a memória fica constante. A paginação é POR CHAVE (id gt <último id da página
    anterior>, ordenado por id), NÃO por $skip — a API do Movidesk retorna 500 em
    $skip profundo (observado a partir de $skip=15000). <session> opcional
    reaproveita a conexão.
    """
    http = session or requests
    ultimo_id = 0
    filtro_desde = (
        f"lastUpdate ge {desde.strftime('%Y-%m-%dT%H:%M:%SZ')}" if desde else None
    )
    for _ in range(max_paginas):
        filtros = [f"id gt {ultimo_id}"]
        if filtro_desde:
            filtros.append(filtro_desde)
        params = {
            "token": os.getenv("MOVIDESK_TOKEN"),
            "$select": _ESPELHO_SELECT,
            "$expand": _ESPELHO_EXPAND,
            "$filter": " and ".join(filtros),
            "$orderby": "id asc",
            "$top": page_size,
        }
        response = http.get(BASE_URL, params=params, timeout=60)
        response.raise_for_status()
        lote = response.json()
        if not lote:
            break
        yield lote
        ultimo_id = max(int(t["id"]) for t in lote)
        if len(lote) < page_size:
            break


def get_setor_team_names(setor, desde, session=None, page_size=1000, max_pages=30):
    """Nomes de equipe (ownerTeam) DISTINTOS de um setor numa janela histórica.

    Read-only. Usa o mesmo escopo do setor (build_day_filter) e traz só ownerTeam,
    paginando via $skip. Base da descoberta de equipes (setor_equipes): a janela ampla
    (qualquer status) revela até equipes hoje zeradas na fila. Devolve lista ordenada,
    sem repetição.
    """
    http = session or requests
    base = {
        "token": os.getenv("MOVIDESK_TOKEN"),
        "$select": "ownerTeam",
        "$filter": build_day_filter(setor, desde),
    }
    nomes = set()
    for pagina in range(max_pages):
        params = {**base, "$top": page_size, "$skip": pagina * page_size}
        response = http.get(BASE_URL, params=params, timeout=60)
        response.raise_for_status()
        lote = response.json()
        for ticket in lote:
            equipe = ticket.get("ownerTeam")
            if equipe:
                nomes.add(equipe)
        if len(lote) < page_size:
            break
    return sorted(nomes)


if __name__ == "__main__":
    # Teste isolado da Etapa 1: busca os tickets e imprime um resumo.
    if not os.getenv("MOVIDESK_TOKEN"):
        raise SystemExit("MOVIDESK_TOKEN não definido. Crie o arquivo .env a partir do .env.example.")

    tickets = get_tickets()
    print(f"Tickets retornados: {len(tickets)}")
    for ticket in tickets[:5]:
        owner = (ticket.get("owner") or {}).get("businessName", "-")
        print(f"  #{ticket.get('id')} | {ticket.get('baseStatus')} | {owner} | {ticket.get('subject')}")
