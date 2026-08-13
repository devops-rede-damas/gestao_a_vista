"""Autenticação e autorização do painel de gestão (**camada plugável**).

Ponto ÚNICO:
que decide "as credenciais conferem?"
e "quais setores este usuário acessa?".
Hoje a fonte é o arquivo (core.usuarios) + bcrypt; na Fase C basta trocar a implementação interna por Entra ID/SSO
mantendo estas assinaturas — o resto do app (blueprint, rotas) não muda. Módulo puro: não conhece Flask/HTTP.
"""
import bcrypt

from core.usuarios import buscar_por_email

# Hash descartável usado para equalizar o tempo de resposta quando o e-mail não
# existe, evitando enumeração de usuários por diferença de timing no login.
_DUMMY_HASH = bcrypt.hashpw(b"timing-equalizer", bcrypt.gensalt())


def hash_senha(senha):
    """Gera o hash bcrypt de uma senha (para cadastro/reset). Retorna str."""
    return bcrypt.hashpw(senha.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _senha_confere(senha, senha_hash):
    """Compara senha x hash de forma resistente a timing (bcrypt.checkpw)."""
    if not senha or not senha_hash:
        return False
    try:
        return bcrypt.checkpw(senha.encode("utf-8"), senha_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def verificar_credenciais(email, senha):
    """Retorna o usuário (sem o hash) se e-mail+senha conferem e a conta está ativa; senão None."""
    usuario = buscar_por_email(email)
    if not usuario or not usuario.get("ativo", True):
        # Roda um checkpw descartável para não vazar, pelo tempo, que o e-mail não existe.
        bcrypt.checkpw((senha or "").encode("utf-8"), _DUMMY_HASH)
        return None
    if not _senha_confere(senha, usuario.get("senha_hash")):
        return None
    return {chave: valor for chave, valor in usuario.items() if chave != "senha_hash"}


def setores_do_usuario(usuario):
    """Setores autorizados do usuário (lista; suporta 1..N setores)."""
    return [setor for setor in (usuario.get("setores") or []) if setor]
