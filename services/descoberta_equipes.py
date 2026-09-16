"""Descoberta de equipes por setor (camada de aplicação).

Orquestra services/movidesk_api (leitura da API) e core/setores_config (escrita no
banco): consulta a API numa janela ampla, coleta os ownerTeam distintos de cada setor
e grava o catálogo em setor_equipes. Usada pelo robô agendado
(scripts/descobrir_equipes.py, origem='robo') e pelo botão "Atualizar equipes" do admin
(origem='admin').
"""
from datetime import datetime, timedelta, timezone

import requests

from core.sectors import available_sectors
from core.setores_config import substituir_equipes
from services.movidesk_api import get_setor_team_names

# Janela de descoberta: fundo suficiente para revelar equipes hoje zeradas na fila.
_JANELA_DIAS = 90


def _desde(dias):
    """Literal OData da data de <dias> atrás (meia-noite UTC)."""
    ref = datetime.now(timezone.utc) - timedelta(days=dias)
    return ref.strftime("%Y-%m-%dT00:00:00.00z")


def descobrir_setor(setor, dias=_JANELA_DIAS, origem="robo", session=None):
    """Descobre as equipes de UM setor na API e grava em setor_equipes. Retorna a lista."""
    nomes = get_setor_team_names(setor, _desde(dias), session=session)
    return substituir_equipes(setor, nomes, origem=origem)


def descobrir_todos(dias=_JANELA_DIAS, origem="robo"):
    """Descobre as equipes de TODOS os setores. Retorna { setor: [equipes] }."""
    sessao = requests.Session()
    return {setor: descobrir_setor(setor, dias, origem, sessao) for setor in available_sectors()}
