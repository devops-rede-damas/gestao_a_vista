"""Usuários do painel de gestão: lê/grava config/usuarios.json (login por arquivo).

Fonte única da verdade dos usuários está em config/usuarios.json, que NÃO é
versionado (contém hashes de senha — ver .gitignore). Este módulo é puro: não
conhece Flask, HTTP nem bcrypt. ***Apenas carrega, valida, busca e persiste
usuários*** — assim permanece desacoplado e fácil de testar. A verificação de
senha (bcrypt) vive em core/auth.py; aqui só mora o I/O do arquivo.
"""
import json
import os

_USUARIOS_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "usuarios.json")


class UsuarioConfigError(ValueError):
    """Erro de configuração de usuários (arquivo inválido, estrutura inesperada, etc.)."""


def _load(path=_USUARIOS_PATH):
    """Carrega o usuarios.json (estrutura vazia se o arquivo ainda não existe)."""
    if not os.path.exists(path):
        return {"usuarios": []}
    try:
        with open(path, encoding="utf-8") as file:
            cfg = json.load(file)
    except json.JSONDecodeError as exc:
        raise UsuarioConfigError(f"config/usuarios.json inválido: {exc}") from exc
    if not isinstance(cfg.get("usuarios"), list):
        raise UsuarioConfigError("config/usuarios.json: chave 'usuarios' ausente ou inválida.")
    return cfg


def _save(cfg, path=_USUARIOS_PATH):
    with open(path, "w", encoding="utf-8") as file:
        json.dump(cfg, file, indent=2, ensure_ascii=False)


def _normalizar_email(email):
    """E-mail é a chave do login: sempre comparado/gravado em minúsculas e sem espaços."""
    return (email or "").strip().lower()


def carregar_usuarios(path=_USUARIOS_PATH):
    """Lista todos os usuários cadastrados."""
    return _load(path)["usuarios"]


def buscar_por_email(email, path=_USUARIOS_PATH):
    """Retorna o dict do usuário pelo e-mail (normalizado), ou None se não existir."""
    alvo = _normalizar_email(email)
    if not alvo:
        return None
    for usuario in _load(path)["usuarios"]:
        if _normalizar_email(usuario.get("email")) == alvo:
            return usuario
    return None


def salvar_usuario(usuario, path=_USUARIOS_PATH):
    """Insere ou atualiza um usuário (chave = e-mail normalizado); faz merge no update.

    No update, os campos informados sobrescrevem os antigos e os demais são
    preservados — permite, por exemplo, trocar só a senha_hash sem apagar setores.
    """
    cfg = _load(path)
    email = _normalizar_email(usuario.get("email"))
    if not email:
        raise UsuarioConfigError("Usuário sem e-mail.")
    novo = {**usuario, "email": email}
    for i, existente in enumerate(cfg["usuarios"]):
        if _normalizar_email(existente.get("email")) == email:
            cfg["usuarios"][i] = {**existente, **novo}
            _save(cfg, path)
            return cfg["usuarios"][i]
    cfg["usuarios"].append(novo)
    _save(cfg, path)
    return novo
