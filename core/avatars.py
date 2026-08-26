"""Catálogo de fotos (avatares) dos responsáveis pelos tickets.

Módulo PURO (sem Flask/HTTP): a fonte única de "qual arquivo é a foto de cada responsável"fica em config/avatars.json, no formato { "<owner.id>": "arquivo.jpg" }.
As imagens em si moram em static/avatars/ (arquivos), nunca no banco.
Segue o padrão de core/sectors.py e core/tokens.py: leitura tolerante a falhas (nunca derruba quem chama),
gravação atômica e classe de erro própria.
Não monta URLs nem conhece a web — devolve apenas o NOME do arquivo (ou None); a camada web decide como servir
(/static/avatars/<arquivo>). """
import json
import os
import re
import time

_BASE_DIR = os.path.dirname(os.path.dirname(__file__))
_CATALOGO_PATH = os.path.join(_BASE_DIR, "config", "avatars.json")
# Pasta física das imagens (servidas como estáticos pelo Flask).
AVATARS_DIR = os.path.join(_BASE_DIR, "static", "avatars")

# Regras de upload (Fase 1, sem reprocessamento de imagem).
EXTENSOES_PERMITIDAS = ("jpg", "jpeg", "png", "webp")
TAMANHO_MAX_BYTES = 2 * 1024 * 1024  # 2 MB


class AvatarConfigError(ValueError):
    """Erro ao gravar o catálogo de avatares (falha de escrita/serialização)."""


class AvatarInvalido(ValueError):
    """Upload rejeitado por validação (id inválido, formato/tamanho não permitidos)."""


def carregar_catalogo(path=_CATALOGO_PATH):
    """Lê config/avatars.json como { owner_id: nome_do_arquivo }.

    Tolerante a falhas: arquivo ausente ou inválido -> {} (nunca levanta), para o
    painel seguir funcionando com o comportamento legado (mapa antigo + iniciais).
    """
    try:
        with open(path, encoding="utf-8") as file:
            dados = json.load(file)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}
    if not isinstance(dados, dict):
        return {}
    # Normaliza para {str: str}, descartando entradas malformadas.
    return {str(k): str(v) for k, v in dados.items() if k and v}


def salvar_catalogo(catalogo, path=_CATALOGO_PATH):
    """Grava o catálogo de forma ATÔMICA (escreve em .tmp e os.replace).

    A escrita atômica evita deixar o arquivo pela metade caso algo falhe no meio.
    """
    if not isinstance(catalogo, dict):
        raise AvatarConfigError("Catálogo de avatares deve ser um dicionário.")
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = f"{path}.tmp"
        with open(tmp, "w", encoding="utf-8") as file:
            json.dump(catalogo, file, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    except OSError as exc:
        raise AvatarConfigError(f"Falha ao gravar {path}: {exc}") from exc


def listar_responsaveis(tickets, catalogo=None):
    """Deduplica os donos dos tickets e junta com o catálogo de fotos.

    <tickets>: lista de services.movidesk_api.get_open_tickets_owners (cada item tem
    'owner' com id + businessName, e 'ownerTeam' com a equipe). Retorna uma lista
    ORDENADA por nome, com as equipes agregadas (uma pessoa pode ter tickets em
    várias equipes):
        [{ "id": "123", "nome": "Fulano", "arquivo": "123.jpg" | None, "equipes": ["Equipe A"] }]
    Ignora tickets sem dono (owner ausente/sem id).
    """
    catalogo = carregar_catalogo() if catalogo is None else catalogo
    por_id = {}
    for ticket in tickets or []:
        owner = ticket.get("owner") or {}
        oid = owner.get("id")
        if not oid:
            continue
        oid = str(oid)
        registro = por_id.setdefault(oid, {"nome": owner.get("businessName") or "", "equipes": set()})
        equipe = ticket.get("ownerTeam")
        if equipe:
            registro["equipes"].add(equipe)
    responsaveis = [
        {"id": oid, "nome": dados["nome"], "arquivo": catalogo.get(oid), "equipes": sorted(dados["equipes"])}
        for oid, dados in por_id.items()
    ]
    responsaveis.sort(key=lambda r: (r["nome"] or "").lower())
    return responsaveis


def _id_seguro(owner_id):
    """Valida o ID do responsável (só dígitos) e devolve-o como string.

    O nome do arquivo salvo é derivado deste ID — jamais de texto do usuário —,
    por isso a restrição a dígitos elimina qualquer risco de path traversal.
    """
    oid = str(owner_id or "").strip()
    if not re.fullmatch(r"[0-9]+", oid):
        raise AvatarInvalido("ID de responsável inválido.")
    return oid


def _detectar_formato(dados):
    """Detecta o formato pela assinatura (magic bytes). Retorna a extensão ou None.

    Não confia na extensão/nome enviados: olha o conteúdo real do arquivo.
    """
    if dados[:3] == b"\xff\xd8\xff":
        return "jpg"
    if dados[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if dados[:4] == b"RIFF" and dados[8:12] == b"WEBP":
        return "webp"
    return None


def salvar_foto(owner_id, dados, catalogo_path=_CATALOGO_PATH, avatars_dir=AVATARS_DIR):
    """Valida e grava a foto do responsável; atualiza o catálogo. Retorna o nome do arquivo.

    Validações: ID só-dígitos, tamanho <= TAMANHO_MAX_BYTES e formato real (magic
    bytes). O nome inclui um timestamp (<id>_<ts>.<ext>) para cache-busting — a URL
    muda a cada troca, evitando o navegador/TV exibir a foto antiga em cache. As
    versões anteriores do mesmo ID são apagadas e o catálogo é atualizado.
    """
    oid = _id_seguro(owner_id)
    if not dados:
        raise AvatarInvalido("Arquivo vazio.")
    if len(dados) > TAMANHO_MAX_BYTES:
        raise AvatarInvalido(f"Imagem maior que {TAMANHO_MAX_BYTES // (1024 * 1024)} MB.")
    ext = _detectar_formato(dados)
    if not ext:
        raise AvatarInvalido("Formato não suportado. Use JPG, PNG ou WEBP.")

    os.makedirs(avatars_dir, exist_ok=True)
    nome = f"{oid}_{int(time.time() * 1000)}.{ext}"
    destino = os.path.join(avatars_dir, nome)
    tmp = f"{destino}.tmp"
    try:
        with open(tmp, "wb") as file:
            file.write(dados)
        os.replace(tmp, destino)
    except OSError as exc:
        raise AvatarConfigError(f"Falha ao gravar a imagem: {exc}") from exc

    _remover_arquivos_do_id(avatars_dir, oid, manter=nome)  # apaga versões antigas do mesmo ID

    catalogo = carregar_catalogo(catalogo_path)
    catalogo[oid] = nome
    salvar_catalogo(catalogo, catalogo_path)
    return nome


def _remover_arquivos_do_id(avatars_dir, oid, manter=None):
    """Apaga arquivos de avatar deste ID (<id>.ext e <id>_<ts>.ext), exceto <manter>.

    As 19 fotos legadas têm nome de apelido (não numérico), então o padrão numérico
    nunca as atinge — a limpeza fica restrita a este ID.
    """
    padrao = re.compile(rf"^{re.escape(oid)}(_[0-9]+)?\.(?:jpg|jpeg|png|webp)$", re.IGNORECASE)
    try:
        arquivos = os.listdir(avatars_dir)
    except OSError:
        return
    for nome in arquivos:
        if nome != manter and padrao.match(nome):
            try:
                os.remove(os.path.join(avatars_dir, nome))
            except OSError:
                pass


def remover_foto(owner_id, catalogo_path=_CATALOGO_PATH, avatars_dir=AVATARS_DIR):
    """Remove a foto do responsável (arquivo + entrada no catálogo). True se havia foto."""
    oid = _id_seguro(owner_id)
    catalogo = carregar_catalogo(catalogo_path)
    tinha = catalogo.pop(oid, None) is not None
    if tinha:
        salvar_catalogo(catalogo, catalogo_path)
    _remover_arquivos_do_id(avatars_dir, oid)  # varre qualquer arquivo remanescente do ID
    return tinha
