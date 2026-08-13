"""CLI de administração de usuários do painel de gestão (Fase B).

Cadastra usuários e (re)define senhas gravando o hash bcrypt em config/usuarios.json.
Enquanto não houver recuperação de senha self-service, o reset é feito por aqui
(reset manual pelo admin). NUNCA imprime nem armazena a senha em texto puro — a
senha é lida sem eco (getpass) e só o hash é persistido.

Uso (a partir da raiz do projeto):
  python -m scripts.gerar_hash add <email> <setor> [--papel gestor|coordenador] [--nome "Nome"]
  python -m scripts.gerar_hash senha <email>
  python -m scripts.gerar_hash list
"""
import argparse
import getpass

from core.auth import hash_senha
from core.sectors import available_sectors
from core.usuarios import buscar_por_email, carregar_usuarios, salvar_usuario

_MIN_SENHA = 8


def _pedir_senha():
    """Lê a senha duas vezes (sem eco) e valida tamanho mínimo e confirmação."""
    senha = getpass.getpass("Senha: ")
    if len(senha) < _MIN_SENHA:
        raise SystemExit(f"Senha muito curta (mínimo {_MIN_SENHA} caracteres).")
    if senha != getpass.getpass("Confirme a senha: "):
        raise SystemExit("As senhas não conferem.")
    return senha


def cmd_add(email, setor, papel, nome):
    if setor not in available_sectors():
        raise SystemExit(f"Setor '{setor}' não existe. Disponíveis: {', '.join(available_sectors())}")
    salvo = salvar_usuario({
        "email": email,
        "nome": nome or email,
        "papel": papel,
        "setores": [setor],
        "senha_hash": hash_senha(_pedir_senha()),
        "ativo": True,
    })
    print(f"Usuário salvo: {salvo['email']} | {salvo['papel']} | setores: {', '.join(salvo['setores'])}")


def cmd_senha(email):
    if not buscar_por_email(email):
        raise SystemExit(f"Usuário '{email}' não encontrado.")
    salvar_usuario({"email": email, "senha_hash": hash_senha(_pedir_senha())})
    print(f"Senha atualizada para {email}.")


def cmd_list():
    usuarios = carregar_usuarios()
    if not usuarios:
        print("(nenhum usuário cadastrado)")
        return
    for u in usuarios:
        estado = "ativo" if u.get("ativo", True) else "inativo"
        print(f"{u.get('email')} | {u.get('papel', '-')} | setores: {', '.join(u.get('setores') or [])} | {estado}")


def main():
    parser = argparse.ArgumentParser(prog="scripts.gerar_hash", description="Administração de usuários (Fase B).")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_add = sub.add_parser("add", help="Cadastra/atualiza um usuário e define a senha.")
    p_add.add_argument("email")
    p_add.add_argument("setor")
    p_add.add_argument("--papel", default="gestor", choices=["gestor", "coordenador", "tv"])
    p_add.add_argument("--nome", default=None)

    p_senha = sub.add_parser("senha", help="Redefine a senha de um usuário existente.")
    p_senha.add_argument("email")

    sub.add_parser("list", help="Lista os usuários (sem hash).")

    args = parser.parse_args()
    if args.cmd == "add":
        cmd_add(args.email, args.setor, args.papel, args.nome)
    elif args.cmd == "senha":
        cmd_senha(args.email)
    elif args.cmd == "list":
        cmd_list()


if __name__ == "__main__":
    main()
