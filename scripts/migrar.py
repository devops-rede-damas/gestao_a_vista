"""Aplica as migrations SQL (cria/atualiza as tabelas) no banco configurado.

Lê todos os arquivos .sql de migrations/ em ordem alfabética e executa cada um.
Idempotente: os scripts usam CREATE TABLE IF NOT EXISTS, então rodar de novo não
quebra nem apaga dados. Use logo após clonar o projeto (ou no deploy) para
preparar o banco.

Uso (a partir da raiz do projeto, com o banco acessível):
  ./venv/Scripts/python.exe -m scripts.migrar
"""
import glob
import os

from dotenv import load_dotenv

load_dotenv(".env")

from core.db import get_connection

_MIGRATIONS_DIR = "migrations"


def _statements(sql):
    """Divide o arquivo em comandos individuais (separados por ';')."""
    for trecho in sql.split(";"):
        comando = trecho.strip()
        if comando:
            yield comando


def main():
    arquivos = sorted(glob.glob(os.path.join(_MIGRATIONS_DIR, "*.sql")))
    if not arquivos:
        raise SystemExit(f"Nenhuma migration encontrada em {_MIGRATIONS_DIR}/")
    con = get_connection()
    try:
        with con.cursor() as cursor:
            for caminho in arquivos:
                with open(caminho, encoding="utf-8") as arquivo:
                    for comando in _statements(arquivo.read()):
                        cursor.execute(comando)
                print(f"[OK] {os.path.basename(caminho)}")
    finally:
        con.close()
    print("Migrations aplicadas.")


if __name__ == "__main__":
    main()
