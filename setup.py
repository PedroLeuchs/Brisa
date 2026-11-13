"""Configuração interativa: segredos digitados ocultos, somente no computador."""
import getpass
import hashlib
import ipaddress
import json
import secrets
from pathlib import Path
from dotenv import dotenv_values, set_key

root = Path(__file__).resolve().parent
env = root / '.env'
if not env.exists():
    env.touch(mode=0o600)
config = dotenv_values(env)
found = []
if (root / 'discovery.json').exists():
    found = json.loads((root / 'discovery.json').read_text(encoding='utf-8'))
default = found[0] if len(found) == 1 else {}
ip = input(f"IP do ar [{config.get('TUYA_IP') or default.get('ip', '')}]: ").strip() or config.get('TUYA_IP') or default.get('ip', '')
ipaddress.IPv4Address(ip)
version = input(f"Protocolo [{config.get('TUYA_VERSION') or default.get('version', '')}]: ").strip() or config.get('TUYA_VERSION') or str(default.get('version', ''))
if version not in ['3.1', '3.3', '3.4', '3.5']:
    raise SystemExit('Versão inválida; confirme pela descoberta.')
key = getpass.getpass('Local Key (oculta; Enter mantém a existente): ') or config.get('TUYA_LOCAL_KEY', '')
if len(key.encode()) != 16:
    raise SystemExit('A Local Key deve ter 16 bytes.')
password = getpass.getpass('Crie a senha de acesso ao controlador (mínimo 12 caracteres): ')
if len(password) < 12 or password != getpass.getpass('Repita a senha: '):
    raise SystemExit('Senha curta ou confirmação diferente.')
salt = secrets.token_bytes(16)
hashed = salt.hex() + ':' + hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1).hex()
for k, v in {'TUYA_DEVICE_ID': 'CONFIGURE_TUYA_DEVICE_ID', 'TUYA_IP': ip, 'TUYA_VERSION': version,
             'TUYA_LOCAL_KEY': key, 'APP_PASSWORD_HASH': hashed,
             'ALLOWED_HOSTS': config.get('ALLOWED_HOSTS') or 'localhost,127.0.0.1,192.168.1.5',
             'COOKIE_SECURE': config.get('COOKIE_SECURE') or 'false'}.items():
    set_key(str(env), k, v)
print('Configuração salva no .env. Nenhum segredo foi exibido. Reinicie o servidor após alterações.')
