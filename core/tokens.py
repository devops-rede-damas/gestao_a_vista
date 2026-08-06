"""Tokens de acesso por setor (capability URLs).

Cada setor tem um token opaco e imprevisivel. A URL da TV vira /painel/<token>
e o servidor resolve token -> setor. O mapa setor->token fica em
config/tokens.json, que NAO e versionado (contem segredos; ver .gitignore).
"""
import json
import os
import secrets

from core.sectors import available_sectors

_TOKENS_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "tokens.json")


def _load(path=_TOKENS_PATH):
    """Carrega o mapa setor->token (dict vazio se o arquivo ainda nao existe)."""
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as file:
        return json.load(file)


def _save(mapping, path=_TOKENS_PATH):
    with open(path, "w", encoding="utf-8") as file:
        json.dump(mapping, file, indent=2, ensure_ascii=False)


def generate_token():
    """Gera um token opaco de 256 bits, seguro para URL."""
    return secrets.token_urlsafe(32)


def get_token(setor, path=_TOKENS_PATH):
    """Retorna o token do setor, ou None se ainda nao houver."""
    return _load(path).get(setor)


def ensure_token(setor, path=_TOKENS_PATH):
    """Garante um token para o setor (gera e salva se faltar); retorna o token."""
    mapping = _load(path)
    if setor not in mapping:
        mapping[setor] = generate_token()
        _save(mapping, path)
    return mapping[setor]


def rotate_token(setor, path=_TOKENS_PATH):
    """Gera um novo token para o setor (invalida o anterior); retorna o novo."""
    mapping = _load(path)
    mapping[setor] = generate_token()
    _save(mapping, path)
    return mapping[setor]


def resolve_sector(token, path=_TOKENS_PATH):
    """Resolve token -> setor com comparacao timing-safe; None se nao existir."""
    if not token:
        return None
    for setor, tok in _load(path).items():
        if secrets.compare_digest(str(tok), str(token)):
            return setor
    return None


if __name__ == "__main__":
    import sys

    base = os.getenv("PUBLIC_BASE_URL", "http://192.168.90.124").rstrip("/")
    args = sys.argv[1:]
    cmd = args[0] if args else "list"

    if cmd in ("gen", "rotate") and len(args) >= 2:
        setor = args[1]
        if setor not in available_sectors():
            raise SystemExit(
                f"Setor '{setor}' nao existe em setores.json. Disponiveis: {', '.join(available_sectors())}"
            )
        tok = rotate_token(setor) if cmd == "rotate" else ensure_token(setor)
        rotulo = " (novo token)" if cmd == "rotate" else ""
        print(f"{setor}{rotulo}: {base}/painel/{tok}")
    elif cmd == "list":
        mapping = _load()
        if not mapping:
            print("(nenhum token gerado ainda)")
        for setor, tok in mapping.items():
            print(f"{setor}: {base}/painel/{tok}")
    else:
        print("Uso: python -m core.tokens [list | gen <setor> | rotate <setor>]")
