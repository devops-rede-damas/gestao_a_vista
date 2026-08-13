"""Horário útil (expediente): converte um intervalo em minutos de horário de trabalho.

Lê config/expediente.json (horário por dia da semana + feriados) e calcula quantos
minutos de expediente existem entre dois instantes. Espelha o cálculo de "horas úteis"
do Movidesk, validado contra os prazos reais (~94% exato ao segundo).

Módulo puro: não conhece Flask, HTTP nem o Movidesk. As datas recebidas são as que a
API do Movidesk entrega (naive, em UTC); a conversão para o fuso local é feita aqui.
"""
import json
import os
from datetime import datetime, timedelta

_CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "expediente.json")
_MAX_DIAS = 400  # trava de segurança para intervalos absurdos


class ExpedienteConfigError(ValueError):
    """Erro de configuração do expediente (arquivo ausente/inválido)."""


def load_expediente(path=_CONFIG_PATH):
    """Carrega e valida minimamente o expediente.json."""
    try:
        with open(path, encoding="utf-8") as file:
            cfg = json.load(file)
    except FileNotFoundError as exc:
        raise ExpedienteConfigError(f"Arquivo de expediente não encontrado: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ExpedienteConfigError(f"config/expediente.json inválido: {exc}") from exc
    if not isinstance(cfg.get("expediente_por_dia"), dict):
        raise ExpedienteConfigError("config/expediente.json: 'expediente_por_dia' ausente.")
    return cfg


def _hm(texto):
    """'08:00' -> (8, 0)."""
    h, m = texto.split(":")
    return int(h), int(m)


def _eh_feriado(dia, cfg):
    """True se a data (date local) é feriado fixo (MM-DD) ou móvel (YYYY-MM-DD)."""
    if dia.strftime("%m-%d") in cfg.get("feriados_fixos", []):
        return True
    return dia.strftime("%Y-%m-%d") in cfg.get("feriados_moveis", [])


def _segmentos_do_dia(dia_local, cfg):
    """Lista de (inicio_dt, fim_dt) do expediente naquele dia local (vazia se folga/feriado)."""
    if _eh_feriado(dia_local.date(), cfg):
        return []
    intervalos = cfg["expediente_por_dia"].get(str(dia_local.weekday()), [])
    segmentos = []
    for ini, fim in intervalos:
        sh, sm = _hm(ini)
        eh, em = _hm(fim)
        s = dia_local.replace(hour=sh, minute=sm, second=0, microsecond=0)
        e = dia_local.replace(hour=eh, minute=em, second=0, microsecond=0)
        segmentos.append((s, e))
    return segmentos


def minutos_uteis_entre(inicio_utc, fim_utc, cfg=None):
    """Minutos de expediente entre dois instantes (naive UTC, como a API do Movidesk entrega).

    Retorna float de minutos, ou None se as entradas forem inválidas ou fim < início.
    """
    if not isinstance(inicio_utc, datetime) or not isinstance(fim_utc, datetime):
        return None
    if fim_utc < inicio_utc:
        return None
    cfg = cfg or load_expediente()
    offset = timedelta(hours=cfg.get("fuso_utc_offset_horas", -3))
    inicio = inicio_utc + offset  # UTC -> local
    fim = fim_utc + offset

    total = timedelta(0)
    dia = inicio.replace(hour=0, minute=0, second=0, microsecond=0)
    for _ in range(_MAX_DIAS):
        if dia.date() > fim.date():
            break
        for s, e in _segmentos_do_dia(dia, cfg):
            ini_ov = max(inicio, s)
            fim_ov = min(fim, e)
            if fim_ov > ini_ov:
                total += fim_ov - ini_ov
        dia = dia + timedelta(days=1)
    return round(total.total_seconds() / 60.0, 1)
