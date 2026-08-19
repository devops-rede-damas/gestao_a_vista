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


def _backend():
    """Origem dos usuários: 'mysql' (banco) ou 'json' (arquivo, padrão)."""
    return (os.getenv("USUARIOS_BACKEND") or "json").strip().lower()


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
    if _backend() == "mysql":
        from core import usuarios_mysql
        return usuarios_mysql.carregar_usuarios()
    return _load(path)["usuarios"]


def buscar_por_email(email, path=_USUARIOS_PATH):
    """Retorna o dict do usuário pelo e-mail (normalizado), ou None se não existir."""
    if _backend() == "mysql":
        from core import usuarios_mysql
        return usuarios_mysql.buscar_por_email(email)
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
    if _backend() == "mysql":
        from core import usuarios_mysql
        return usuarios_mysql.salvar_usuario(usuario)
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


# ── Operações do painel de administração (papel ADM) ───────────────────────────
# Gerenciam a tabela usuarios_gestor pela chave primária `id` (edição de e-mail,
# ativar/inativar, trocar senha). São específicas do backend MySQL — o backend
# JSON (arquivo, sem `id`) não as suporta e sinaliza isso de forma explícita.

def _somente_mysql(nome):
    raise UsuarioConfigError(
        f"{nome}: o painel de administração requer USUARIOS_BACKEND=mysql."
    )


def listar_para_admin():
    """Todos os usuários (ativos e inativos) para a tela de gestão."""
    if _backend() == "mysql":
        from core import usuarios_mysql
        return usuarios_mysql.listar_para_admin()
    _somente_mysql("listar_para_admin")


def buscar_por_id(uid):
    """Retorna o usuário (formato do painel) pela chave primária, ou None."""
    if _backend() == "mysql":
        from core import usuarios_mysql
        return usuarios_mysql.buscar_por_id(uid)
    _somente_mysql("buscar_por_id")


def criar_usuario(dados):
    """Insere um novo usuário e retorna o registro criado."""
    if _backend() == "mysql":
        from core import usuarios_mysql
        return usuarios_mysql.criar_usuario(dados)
    _somente_mysql("criar_usuario")


def atualizar_usuario(uid, campos):
    """Atualiza as colunas informadas de um usuário por id; retorna o registro."""
    if _backend() == "mysql":
        from core import usuarios_mysql
        return usuarios_mysql.atualizar_usuario(uid, campos)
    _somente_mysql("atualizar_usuario")


def definir_senha(uid, senha_hash):
    """Grava um novo hash de senha para o usuário (por id)."""
    if _backend() == "mysql":
        from core import usuarios_mysql
        return usuarios_mysql.definir_senha(uid, senha_hash)
    _somente_mysql("definir_senha")


def definir_ativo(uid, ativo):
    """Ativa/inativa o usuário por id (inativar substitui a exclusão)."""
    if _backend() == "mysql":
        from core import usuarios_mysql
        return usuarios_mysql.definir_ativo(uid, ativo)
    _somente_mysql("definir_ativo")
