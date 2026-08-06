import os

import requests
from dotenv import load_dotenv

from core.sectors import build_filter

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


if __name__ == "__main__":
    # Teste isolado da Etapa 1: busca os tickets e imprime um resumo.
    if not os.getenv("MOVIDESK_TOKEN"):
        raise SystemExit("MOVIDESK_TOKEN não definido. Crie o arquivo .env a partir do .env.example.")

    tickets = get_tickets()
    print(f"Tickets retornados: {len(tickets)}")
    for ticket in tickets[:5]:
        owner = (ticket.get("owner") or {}).get("businessName", "-")
        print(f"  #{ticket.get('id')} | {ticket.get('baseStatus')} | {owner} | {ticket.get('subject')}")
