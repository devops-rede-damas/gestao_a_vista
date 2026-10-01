"""Etapa 3 do cadastro de colaboradores: migra a config legada para a tabela nova.

Backfill UNICO e idempotente. Copia para as colunas "suas" da tabela `colaboradores`
(foto_arquivo, nome_exibicao, exibir) o que ja existe hoje nas fontes legadas:
  * fotos        -> config/avatars.json      (core.avatars.carregar_catalogo)
  * exibir/nome  -> tabela colaboradores_config (core.colaboradores.carregar_config)

As fontes legadas NAO sao tocadas (rede de seguranca). So migra ids que ja existem no
cadastro; ids sem linha viram "orfaos" (seguem preservados nas fontes legadas) e sao
apenas reportados. Ao final, revalida lendo o cadastro de novo e confirma que nenhuma
config foi perdida (sai com codigo 1 se divergir).

Uso (raiz do projeto, com o banco acessivel):
  ./venv/Scripts/python.exe -m scripts.migrar_config_colaboradores
"""
from dotenv import load_dotenv

load_dotenv(".env")

from core.avatars import carregar_catalogo
from core.colaboradores import carregar_config
from core.colaboradores_movidesk import (
    aplicar_migracao_config,
    carregar_cadastro,
    planejar_migracao_config,
)


def _validar(cadastro, fotos, config):
    """Reconfere, no cadastro ja gravado, que cada config legada de id existente foi
    aplicada corretamente. Retorna a lista de divergencias (vazia = tudo certo)."""
    por_id = {c["id"]: c for c in cadastro}
    falhas = []
    for i, arquivo in fotos.items():
        if i in por_id and por_id[i].get("foto_arquivo") != arquivo:
            falhas.append(f"foto {i}: esperado {arquivo!r}, achou {por_id[i].get('foto_arquivo')!r}")
    for i, conf in config.items():
        if i not in por_id:
            continue
        alvo = por_id[i]
        if bool(alvo.get("exibir")) != bool(conf.get("exibir")):
            falhas.append(f"exibir {i}: esperado {conf.get('exibir')}, achou {alvo.get('exibir')}")
        if (alvo.get("nome_exibicao") or None) != (conf.get("nome_exibicao") or None):
            falhas.append(f"nome {i}: esperado {conf.get('nome_exibicao')!r}, achou {alvo.get('nome_exibicao')!r}")
    return falhas


def main():
    fotos = carregar_catalogo()
    config = carregar_config()
    cadastro = carregar_cadastro()

    plano = planejar_migracao_config(cadastro, fotos, config)
    r = plano["resumo"]
    print(f"Fontes legadas: {r['fotos_legadas']} foto(s), {r['config_legadas']} config.")
    print(f"A migrar (ids no cadastro): {r['fotos_a_migrar']} foto(s), {r['config_a_migrar']} config.")
    if plano["orfaos_foto"]:
        print(f"Orfaos de FOTO (sem linha no cadastro, preservados no avatars.json): {plano['orfaos_foto']}")
    if plano["orfaos_config"]:
        print(f"Orfaos de CONFIG (sem linha no cadastro, preservados na colaboradores_config): {plano['orfaos_config']}")

    aplicado = aplicar_migracao_config(plano)
    print(f"Aplicado no banco: {aplicado['fotos']} foto(s), {aplicado['config']} config.")

    falhas = _validar(carregar_cadastro(), plano["fotos"], plano["config"])
    if falhas:
        print("FALHA - divergencias encontradas:")
        for f in falhas:
            print("  -", f)
        raise SystemExit(1)
    print("OK - nenhuma config perdida (fontes legadas intactas).")


if __name__ == "__main__":
    main()
