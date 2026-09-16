"""Teste e2e da feature "modo de exibição por setor" (agregado x por_equipe).

Valida, de ponta a ponta, as 4 camadas: banco (core.setores_config), overlay
(app._exibicao_efetiva), rotas do admin (toggle + botão) e injeção no painel, além
da descoberta de equipes (services.descoberta_equipes) e do fallback resiliente.

NÃO destrói dados: faz snapshot das tabelas setor_config/setor_equipes antes e
restaura ao final (mesmo se um teste falhar). Sai com código 1 se algo falhar.

Uso (raiz do projeto, com o banco acessível; testes de API exigem MOVIDESK_TOKEN):
  ./venv/Scripts/python.exe -m scripts.testar_exibicao_setor
"""
import os
import sys
import traceback

from dotenv import load_dotenv

load_dotenv(".env")

from core.db import get_connection
from core import setores_config as sc
import app as appmod

app = appmod.app

_FALHAS = []


def checar(nome, cond, detalhe=""):
    """Registra um PASS/FAIL. Nunca levanta — acumula falhas para o resumo final."""
    if cond:
        print(f"  [PASS] {nome}")
    else:
        print(f"  [FAIL] {nome} {('-> ' + str(detalhe)) if detalhe else ''}")
        _FALHAS.append(nome)


# ── Snapshot / restore (não corromper o teste_db) ───────────────────────────────
def _snapshot():
    con = get_connection()
    with con.cursor() as cur:
        cur.execute("SELECT setor, exibicao, atualizado_por FROM setor_config")
        cfg = cur.fetchall()
        cur.execute("SELECT setor, equipe, origem FROM setor_equipes")
        eq = cur.fetchall()
    con.close()
    return cfg, eq


def _restore(snap):
    cfg, eq = snap
    con = get_connection()
    con.begin()
    try:
        with con.cursor() as cur:
            cur.execute("DELETE FROM setor_config")
            for r in cfg:
                cur.execute(
                    "INSERT INTO setor_config (setor, exibicao, atualizado_por) VALUES (%s, %s, %s)",
                    (r["setor"], r["exibicao"], r["atualizado_por"]),
                )
            cur.execute("DELETE FROM setor_equipes")
            for r in eq:
                cur.execute(
                    "INSERT INTO setor_equipes (setor, equipe, origem) VALUES (%s, %s, %s)",
                    (r["setor"], r["equipe"], r["origem"]),
                )
        con.commit()
    finally:
        con.close()


def _origens(setor):
    con = get_connection()
    with con.cursor() as cur:
        cur.execute("SELECT DISTINCT origem FROM setor_equipes WHERE setor=%s ORDER BY origem", (setor,))
        vals = [r["origem"] for r in cur.fetchall()]
    con.close()
    return vals


def _config_row(setor):
    con = get_connection()
    with con.cursor() as cur:
        cur.execute("SELECT exibicao, atualizado_por FROM setor_config WHERE setor=%s", (setor,))
        row = cur.fetchone()
    con.close()
    return row


def _adm(c):
    with c.session_transaction() as s:
        s["usuario"] = {"email": "adm@rededamas.com.br", "nome": "ADM", "papel": "ADM", "setores": []}


def _gestor(c, setor):
    with c.session_transaction() as s:
        s["usuario"] = {"email": f"{setor}@rededamas.com.br", "nome": "G", "papel": "gestor", "setores": [setor]}


# ── Testes ──────────────────────────────────────────────────────────────────────
def teste_camada_dados():
    print("[1] Camada de dados (core.setores_config)")
    sc.definir_modo("fiscal", "por_equipe")
    checar("definir_modo grava override", sc.carregar_modos().get("fiscal") == "por_equipe", sc.carregar_modos())
    sc.definir_modo("fiscal", "agregado", padrao="agregado")
    checar("modo == padrão remove a linha", "fiscal" not in sc.carregar_modos(), sc.carregar_modos())
    try:
        sc.definir_modo("fiscal", "invalido")
        checar("modo inválido recusado", False, "não levantou")
    except sc.SetorConfigError:
        checar("modo inválido recusado", True)

    gravadas = sc.substituir_equipes("fiscal", ["  B ", "A", "A", ""], origem="admin")
    checar("substituir_equipes dedup/limpa", gravadas == ["B", "A"], gravadas)
    checar("equipes_de lê ordenado", sc.equipes_de("fiscal") == ["A", "B"], sc.equipes_de("fiscal"))
    checar("origem gravada (admin)", _origens("fiscal") == ["admin"], _origens("fiscal"))
    sc.substituir_equipes("fiscal", ["Unica"])
    checar("substituir faz replace", sc.equipes_de("fiscal") == ["Unica"], sc.equipes_de("fiscal"))


def teste_overlay():
    print("[2] Overlay (app._exibicao_efetiva)")
    sc.substituir_equipes("fiscal", ["Equipe X", "Equipe Y"])
    sc.definir_modo("fiscal", "por_equipe")
    ef = appmod._exibicao_efetiva("fiscal")
    checar("modo do banco vence o JSON", ef["modo"] == "por_equipe", ef)
    checar("equipes do banco substituem o JSON", ef["equipes"] == ["Equipe X", "Equipe Y"], ef)

    sc.substituir_equipes("juridico", [])
    jf = appmod._exibicao_efetiva("juridico")
    checar("fallback: Jurídico usa modo do JSON", jf["modo"] == "por_equipe", jf)
    checar("fallback: Jurídico usa equipes do JSON", len(jf["equipes"]) == 2, jf)


def teste_rotas_admin():
    print("[3] Rotas do admin (toggle + subtela + auditoria)")
    with app.test_client() as c:
        _adm(c)
        r = c.put("/admin/api/setores/fiscal/exibicao", json={"exibicao": "por_equipe"})
        checar("PUT modo válido -> 200", r.status_code == 200, r.status_code)
        row = _config_row("fiscal")
        checar("auditoria atualizado_por gravada", row and row["atualizado_por"] == "adm@rededamas.com.br", row)
        checar("PUT modo inválido -> 400", c.put("/admin/api/setores/fiscal/exibicao", json={"exibicao": "x"}).status_code == 400)
        checar("PUT setor inexistente -> 404", c.put("/admin/api/setores/nada/exibicao", json={"exibicao": "agregado"}).status_code == 404)

        html = c.get("/admin/setores/exibicao").get_data(as_text=True)
        checar("subtela tem toggle", "exib-toggle" in html, "")
        checar("subtela tem botão atualizar", "btn-atualizar-equipes" in html, "")
        checar("subtela tem rótulo 'Modo de exibição'", "Modo de exibição" in html, "")


def teste_painel():
    print("[4] Injeção no painel (window.exibicao)")
    sc.definir_modo("fiscal", "por_equipe")
    sc.substituir_equipes("fiscal", ["Atendimento Fiscal", "Atendimento Central de Notas"])
    with app.test_client() as c:
        _gestor(c, "fiscal")
        html = c.get("/painel/fiscal").get_data(as_text=True)
    tem_modo = '"modo": "por_equipe"' in html or '"modo":"por_equipe"' in html
    checar("painel injeta modo por_equipe", tem_modo, "")
    checar("painel injeta equipes do banco", "Atendimento Central de Notas" in html, "")


def teste_descoberta_api():
    print("[5] Descoberta via API (services.descoberta_equipes)")
    if not os.getenv("MOVIDESK_TOKEN"):
        print("  [SKIP] MOVIDESK_TOKEN ausente — testes de API pulados")
        return
    from services.descoberta_equipes import descobrir_setor
    try:
        eq = descobrir_setor("comercial", origem="robo")
    except Exception as exc:  # rede/API — não trava o teste, só sinaliza
        checar("descobrir_setor(comercial) sem erro", False, exc)
        return
    checar("descoberta retorna equipes", isinstance(eq, list) and len(eq) >= 1, eq)
    checar("descoberta grava origem=robo", _origens("comercial") == ["robo"], _origens("comercial"))
    checar("overlay usa equipes descobertas", appmod._exibicao_efetiva("comercial")["equipes"] == eq, "")

    with app.test_client() as c:
        _adm(c)
        r = c.post("/admin/api/setores/comercial/equipes/atualizar")
        d = r.get_json() or {}
        checar("botão atualizar -> 200", r.status_code == 200, r.status_code)
        checar("botão retorna qtd coerente", d.get("qtd") == len(d.get("equipes", [])), d)
        checar("botão grava origem=admin", _origens("comercial") == ["admin"], _origens("comercial"))
        checar("botão setor inexistente -> 404", c.post("/admin/api/setores/nada/equipes/atualizar").status_code == 404)


def main():
    if not os.getenv("DB_NAME"):
        raise SystemExit("Config de banco ausente no .env (DB_NAME).")
    print("=" * 72)
    print("TESTE E2E — modo de exibição por setor")
    print("=" * 72)
    snap = _snapshot()
    try:
        teste_camada_dados()
        teste_overlay()
        teste_rotas_admin()
        teste_painel()
        teste_descoberta_api()
    except Exception:
        print("\n[ERRO INESPERADO]")
        traceback.print_exc()
        _FALHAS.append("exceção inesperada")
    finally:
        _restore(snap)
        print("  (tabelas restauradas ao estado inicial)")
    print("=" * 72)
    if _FALHAS:
        print(f"RESULTADO: {len(_FALHAS)} FALHA(S) -> {', '.join(_FALHAS)}")
        sys.exit(1)
    print("RESULTADO: TODOS OS TESTES PASSARAM ✓")


if __name__ == "__main__":
    main()
