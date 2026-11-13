"""Generate the existing Brisa login format without recording the password."""
import getpass
import hashlib
import secrets


def main():
    password = getpass.getpass("Nova senha privada do Brisa: ")
    if len(password) < 12 or len(password) > 256:
        raise SystemExit("Use uma senha com 12 a 256 caracteres.")
    if password != getpass.getpass("Repita a senha: "):
        raise SystemExit("As senhas não coincidem.")
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1).hex()
    print("Cole somente a próxima linha em APP_PASSWORD_HASH no gerenciador da hospedagem:")
    print(salt.hex() + ":" + digest)


if __name__ == "__main__":
    main()
