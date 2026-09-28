"""Colaboradores (agentes) vindos do Movidesk: recorte por setor + cadastro no banco.

Duas responsabilidades, sem acoplamento a HTTP (quem fala com o Movidesk e
services.movidesk_api):

1. DOMINIO (puro): agentes_dos_setores() recebe os agentes crus de
   services.movidesk_api.get_agentes e devolve apenas os que pertencem a algum setor
   nosso, reaproveitando core.sectors.setores_de \u2014 a MESMA regra do painel. Assim o
   recorte acompanha automaticamente mudancas em config/setores.json, sem lista duplicada.

2. CADASTRO (banco, tabela `colaboradores`): sincronizar() espelha a lista de dominio na
   tabela e carregar_cadastro() a le de volta. A tabela separa por RESPONSABILIDADE as
   colunas de ESPELHO (nome, ativo, equipes, ultima_sync \u2014 so o sync escreve) das de
   CONFIG (foto/nome/exibir \u2014 so o admin escreve). Duas regras de ouro:
     * o sync NUNCA toca nas colunas de config (UPSERT lista so as de espelho);
     * quem sai do escopo/incativa vira ativo=0, nunca e deletado (preserva a config).
   Leitura TOLERANTE (banco fora -> [] ), para nunca quebrar as TVs.
"""
import json
from datetime import datetime

import pymysql

from core.db import DbConfigError, get_connection
from core.sectors import load_config, setores_de

_TABELA = "colaboradores"


class ColaboradorMovideskError(RuntimeError):
    """Erro ao gravar o cadastro de colaboradores no banco."""


def _setores_do_agente(agente, cfg):
    """Chaves de setor de um agente, unindo o mapeamento de cada equipe dele."""
    setores = set()
    nome = agente.get("businessName")
    for equipe in agente.get("teams") or []:
        setores.update(setores_de(equipe, nome, cfg))
    return sorted(setores)


def agentes_dos_setores(agentes, cfg=None, apenas_ativos=True):
    """Filtra os agentes que servem a algum setor nosso e anexa as chaves de setor.

    <agentes>: saida de services.movidesk_api.get_agentes (id, businessName, isActive,
    teams). Descarta quem nao casa em nenhum setor e, por padrao, os inativos. Retorna
    lista ORDENADA por nome:
        [{"id", "nome", "ativo", "equipes": [...], "setores": [...]}]
    """
    cfg = cfg or load_config()
    colaboradores = []
    for agente in agentes or []:
        if apenas_ativos and not agente.get("isActive"):
            continue
        setores = _setores_do_agente(agente, cfg)
        if not setores:
            continue
        colaboradores.append({
            "id": str(agente.get("id")),
            "nome": agente.get("businessName") or "",
            "ativo": bool(agente.get("isActive")),
            "equipes": sorted(agente.get("teams") or []),
            "setores": setores,
        })
    colaboradores.sort(key=lambda c: (c["nome"] or "").lower())
    return colaboradores


# ── Cadastro no banco (espelho + config) ────────────────────────────────────────
def _lista_equipes(bruto):
    """Desserializa a coluna `equipes` (JSON array) em lista; tolerante a lixo -> []."""
    if not bruto:
        return []
    try:
        dados = json.loads(bruto)
    except (ValueError, TypeError):
        return []
    return [str(e) for e in dados] if isinstance(dados, list) else []


def carregar_cadastro():
    """Cadastro completo como lista de dicts (ordenada por nome). Tolerante -> [].

    Cada item: {id, nome, ativo, equipes[list], foto_arquivo, nome_exibicao, exibir,
    ultima_sync}. O `setores` NAO vem daqui: e derivado na leitura (via setores_de) por
    quem exibe, para acompanhar o config/setores.json sem re-sync.
    """
    try:
        con = get_connection()
    except DbConfigError:
        return []
    try:
        with con.cursor() as cursor:
            cursor.execute(
                f"SELECT id, nome, ativo, equipes, foto_arquivo, nome_exibicao, exibir, "
                f"ultima_sync FROM {_TABELA} ORDER BY nome"
            )
            rows = cursor.fetchall()
    except pymysql.MySQLError:
        return []
    finally:
        con.close()
    for r in rows:
        r["ativo"] = bool(r["ativo"])
        r["exibir"] = bool(r["exibir"])
        r["equipes"] = _lista_equipes(r["equipes"])
    return rows


def sincronizar(colaboradores):
    """Espelha a lista de colaboradores (dominio) na tabela e reconcilia ausentes.

    <colaboradores>: saida de agentes_dos_setores (id, nome, equipes, ...). Faz UPSERT das
    colunas de ESPELHO (nome, ativo=1, equipes, ultima_sync), preservando as de CONFIG.
    Depois marca ativo=0 em quem esta no banco mas NAO veio na lista (saiu do escopo ou
    incativou) \u2014 sem deletar. Tudo numa transacao. Retorna {"sincronizados", "inativados"}.

    Trava de seguranca: lista vazia NAO reconcilia (evita inativar todo mundo se a origem
    falhar). Erros de banco viram ColaboradorMovideskError.
    """
    itens = list(colaboradores or [])
    if not itens:
        return {"sincronizados": 0, "inativados": 0}

    agora = datetime.now()
    valores = [
        (str(c["id"]), c.get("nome") or "", json.dumps(c.get("equipes") or [], ensure_ascii=False), agora)
        for c in itens
    ]
    ids = [v[0] for v in valores]
    try:
        con = get_connection()
    except DbConfigError as exc:
        raise ColaboradorMovideskError(str(exc)) from exc
    try:
        con.begin()
        with con.cursor() as cursor:
            cursor.executemany(
                f"INSERT INTO {_TABELA} (id, nome, ativo, equipes, ultima_sync) "
                "VALUES (%s, %s, 1, %s, %s) "
                "ON DUPLICATE KEY UPDATE nome = VALUES(nome), ativo = VALUES(ativo), "
                "equipes = VALUES(equipes), ultima_sync = VALUES(ultima_sync)",
                valores,
            )
            marcadores = ", ".join(["%s"] * len(ids))
            cursor.execute(
                f"UPDATE {_TABELA} SET ativo = 0 WHERE ativo = 1 AND id NOT IN ({marcadores})",
                ids,
            )
            inativados = cursor.rowcount
        con.commit()
    except pymysql.MySQLError as exc:
        con.rollback()
        raise ColaboradorMovideskError(f"Falha ao sincronizar no banco: {exc}") from exc
    finally:
        con.close()
    return {"sincronizados": len(itens), "inativados": inativados}
