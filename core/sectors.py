"""Configuração de setores: lê config/setores.json e monta o $filter OData por setor.

Fonte única da verdade dos setores está em config/setores.json. Este módulo é
puro: transforma a configuração em uma string de filtro OData, sem conhecer
Flask, HTTP ou o Movidesk. Assim permanece desacoplado e fácil de testar.
"""
import json
import os

_CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "setores.json")


class SectorConfigError(ValueError):
    """Erro de configuração de setores (arquivo ausente/inválido, setor inexistente, etc.)."""


def load_config(path=_CONFIG_PATH):
    """Carrega e valida minimamente o setores.json."""
    try:
        with open(path, encoding="utf-8") as file:
            cfg = json.load(file)
    except FileNotFoundError as exc:
        raise SectorConfigError(f"Arquivo de setores não encontrado: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SectorConfigError(f"config/setores.json inválido: {exc}") from exc

    if not isinstance(cfg.get("setores"), dict) or not _sector_keys(cfg):
        raise SectorConfigError("config/setores.json: chave 'setores' ausente ou vazia.")
    return cfg


def _sector_keys(cfg):
    """Chaves de setores reais (ignora chaves de documentação iniciadas por '_')."""
    return [key for key in cfg.get("setores", {}) if not key.startswith("_")]


def available_sectors(cfg=None):
    """Lista os setores disponíveis."""
    return _sector_keys(cfg or load_config())


def sector_display(setor, cfg=None):
    """Metadados de exibição de um setor: modo ('agregado'|'por_equipe') e as equipes a exibir.

    'agregado' (padrão) preserva o comportamento clássico (tudo numa tela). Em
    'por_equipe' a tela alterna cada equipe do setor; as equipes vêm dos nomes
    exatos em 'regras' (itens 'equipe'), na ordem em que aparecem.
    """
    cfg = cfg or load_config()
    dados = cfg["setores"].get(setor, {}) if not setor.startswith("_") else {}
    modo = dados.get("exibicao", "agregado")
    equipes = [r["equipe"] for r in (dados.get("regras") or []) if r.get("equipe")]
    return {"modo": modo, "equipes": equipes}


def _escape(value):
    """Escapa aspas simples para literais OData (' -> '')."""
    return str(value).replace("'", "''")


def _rule_clause(rule):
    """Clausula de UMA regra: equipe exata ('equipe') ou padrao de nome ('contem'), opcionalmente restrita a responsaveis."""
    if rule.get("equipe"):
        team = f"ownerTeam eq '{_escape(rule['equipe'])}'"
    elif rule.get("contem"):
        team = f"contains(ownerTeam, '{_escape(rule['contem'])}')"
    else:
        raise SectorConfigError("Cada item de 'regras' precisa de 'equipe' ou 'contem'.")
    responsaveis = rule.get("responsaveis") or []
    if not responsaveis:
        return f"({team})"
    pessoas = " or ".join(f"owner/businessName eq '{_escape(p)}'" for p in responsaveis)
    return f"({team} and ({pessoas}))"


def build_filter(setor, cfg=None):
    """Monta o $filter OData de um setor a partir da configuração."""
    cfg = cfg or load_config()
    if setor.startswith("_") or setor not in cfg["setores"]:
        disponiveis = ", ".join(available_sectors(cfg)) or "(nenhum)"
        raise SectorConfigError(f"Setor '{setor}' não existe. Disponíveis: {disponiveis}")

    dados = cfg["setores"][setor]
    regras = dados.get("regras") or []
    if not regras:
        raise SectorConfigError(f"Setor '{setor}' não tem 'regras'.")

    partes = [f"(baseStatus ne '{_escape(s)}')" for s in cfg.get("_comum", {}).get("excluir_base_status", [])]

    inclusao = " or ".join(_rule_clause(r) for r in regras)
    partes.append(f"({inclusao})")

    for cid in dados.get("excluir_clientes", []):
        partes.append(f"clients/any(clients: clients/id ne '{_escape(cid)}')")

    return " and ".join(partes)
