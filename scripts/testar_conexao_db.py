"""Testa a conexão com o MySQL e conta os usuários da tabela usuarios_gestor.

Uso (com o túnel SSH aberto num outro terminal):
    ./venv/Scripts/python.exe -m scripts.testar_conexao_db

Serve só para validar a ligação (Etapa 1) antes de o login passar a ler do banco.
"""
from dotenv import load_dotenv

from core.db import DbConfigError, get_connection


def main():
    load_dotenv(".env")
    try:
        conexao = get_connection()
    except DbConfigError as exc:
        print(f"[ERRO] {exc}")
        print("Confira o .env e se o túnel SSH está aberto (ssh -L 3307:127.0.0.1:3306 ...).")
        return 1

    try:
        with conexao.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) AS total FROM usuarios_gestor")
            total = cursor.fetchone()["total"]
            cursor.execute(
                "SELECT email, nome, papel, setor FROM usuarios_gestor ORDER BY id LIMIT 3"
            )
            amostra = cursor.fetchall()
    finally:
        conexao.close()

    print(f"[OK] Conexão bem-sucedida. usuarios_gestor tem {total} registro(s).")
    print("Amostra:")
    for linha in amostra:
        print(f"  - {linha['email']} | {linha['nome']} | {linha['papel']} | {linha['setor']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
