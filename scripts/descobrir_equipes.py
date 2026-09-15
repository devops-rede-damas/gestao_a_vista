"""Robô de descoberta de equipes: varre a API do Movidesk e atualiza setor_equipes.

Uso (raiz do projeto, com o banco acessível):
  ./venv/Scripts/python.exe -m scripts.descobrir_equipes

Pensado para rodar por AGENDAMENTO (mensal) no servidor (systemd timer/cron). Grava com
origem='robo'. Idempotente: cada execução substitui a lista de cada setor pelas equipes
vistas na janela ampla — inclusive as hoje zeradas na fila em aberto.
"""
import os

from dotenv import load_dotenv

load_dotenv(".env")

from services.descoberta_equipes import descobrir_todos


def main():
    if not os.getenv("MOVIDESK_TOKEN"):
        raise SystemExit("MOVIDESK_TOKEN não definido no .env")
    resultado = descobrir_todos(origem="robo")
    total = 0
    for setor, equipes in resultado.items():
        total += len(equipes)
        print(f"[{setor}] {len(equipes)} equipe(s): {', '.join(equipes) or '(nenhuma)'}")
    print(f"Descoberta concluída: {total} equipe(s) em {len(resultado)} setor(es).")


if __name__ == "__main__":
    main()
