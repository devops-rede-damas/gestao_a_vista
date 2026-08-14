"""Conexão com o banco MySQL (camada de I/O, análoga a services/movidesk_api.py).

O banco fica num servidor remoto acessível só via túnel SSH; em desenvolvimento
abre-se o túnel (ssh -L porta_local:127.0.0.1:3306 usuario@servidor) e o app
conecta em 127.0.0.1:porta_local como se fosse local. As credenciais vêm do
.env (fora do git). Este módulo só entrega uma conexão configurada — quem sabe
o SQL (ex.: core/usuarios.py no backend mysql) é responsável por usá-la.
"""
import os

import pymysql
from pymysql.cursors import DictCursor


class DbConfigError(RuntimeError):
    """Faltam variáveis de conexão no .env ou o banco está inacessível."""


def _config():
    """Lê os dados de conexão do ambiente (.env), validando o que é obrigatório."""
    faltando = [
        chave for chave in ("DB_USER", "DB_PASSWORD", "DB_NAME")
        if not os.getenv(chave)
    ]
    if faltando:
        raise DbConfigError(
            "Configuração de banco incompleta no .env: " + ", ".join(faltando)
        )
    return {
        "host": os.getenv("DB_HOST", "127.0.0.1"),
        "port": int(os.getenv("DB_PORT", "3307")),
        "user": os.getenv("DB_USER"),
        "password": os.getenv("DB_PASSWORD"),
        "database": os.getenv("DB_NAME"),
    }


def get_connection():
    """Abre uma conexão MySQL (utf8mb4, resultados como dict, autocommit ligado).

    autocommit=True porque as operações do painel são simples (uma por vez);
    quem precisar de transação explícita pode desligar via connection.begin().
    """
    cfg = _config()
    # PyMySQL codifica a senha em latin1 na autenticacao; se a senha tem caractere
    # nao-ASCII (ex.: gravada em UTF-8, como no .env do portal PHP), reenviamos os
    # bytes UTF-8 crus para bater com a senha registrada no servidor. Para senha
    # so-ASCII isto e no-op.
    senha = cfg["password"].encode("utf-8").decode("latin1")
    try:
        return pymysql.connect(
            host=cfg["host"],
            port=cfg["port"],
            user=cfg["user"],
            password=senha,
            database=cfg["database"],
            charset="utf8mb4",
            cursorclass=DictCursor,
            autocommit=True,
            connect_timeout=10,
        )
    except pymysql.MySQLError as exc:
        raise DbConfigError(f"Não foi possível conectar ao MySQL: {exc}") from exc
