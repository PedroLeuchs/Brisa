"""Coleta somente leitura de metadados, esquema integral e estado LAN.

Não modifica mapping.json, não envia comandos e não salva credenciais.
"""
import argparse
import contextlib
from datetime import datetime, timezone
import getpass
import hashlib
import hmac
import io
import json
import logging
import os
from pathlib import Path
import re
import time

from dotenv import load_dotenv
import requests
from controller import Controller
from mapear import DEVICE_ID, safe_error

ROOT = Path(__file__).resolve().parent
TOKEN_PATH = '/v1.0/token?grant_type=1'
PATHS = {
    'device_details': f'/v1.0/devices/{DEVICE_ID}',
    'things_model': f'/v2.0/cloud/thing/{DEVICE_ID}/model',
    'specifications_v11': f'/v1.1/devices/{DEVICE_ID}/specifications',
    'standard_specifications': f'/v1.0/iot-03/devices/{DEVICE_ID}/specification',
    'shadow_properties': f'/v2.0/cloud/thing/{DEVICE_ID}/shadow/properties',
}
PRIVATE = {'localkey','key','secret','clientsecret','apisecret','apikey','accesssecret',
           'accesstoken','refreshtoken','token','password','authorization','sign',
           'uid','ownerid','uuid','ip','mac','lat','lon','latitude','longitude'}


def keyname(value):
    return re.sub(r'[^a-z0-9]', '', str(value).lower())


def scrub(value):
    """Remove campos secretos/identificadores pessoais antes de gravar relatórios."""
    if isinstance(value, dict):
        if keyname(value.get('code', '')) in PRIVATE:
            # Mantém definição funcional, nunca valor corrente/default de credencial.
            return {k: scrub(v) for k, v in value.items()
                    if keyname(k) not in PRIVATE | {'value', 'values', 'typespec', 'typedefaultvalue'}}
        return {k: scrub(v) for k, v in value.items() if keyname(k) not in PRIVATE}
    if isinstance(value, list):
        return [scrub(item) for item in value]
    return value


def sign_get(client_id, secret, timestamp, path, token=''):
    canonical = 'GET\n' + hashlib.sha256(b'').hexdigest() + '\n\n' + path
    return hmac.new(secret.encode(), (client_id + token + str(timestamp) + canonical).encode(), hashlib.sha256).hexdigest().upper()


class ReadOnlyCloud:
    def __init__(self, client_id, secret):
        self.client_id, self.secret, self.token = client_id, secret, ''
        self.session = requests.Session()

    def get(self, path):
        if path not in {TOKEN_PATH, *PATHS.values()}:
            raise ValueError('Consulta fora da lista de leituras permitidas.')
        stamp = str(int(time.time() * 1000))
        token = '' if path == TOKEN_PATH else self.token
        if path != TOKEN_PATH and not token:
            raise ValueError('Autenticação necessária.')
        headers = {'client_id': self.client_id, 't': stamp, 'sign_method': 'HMAC-SHA256',
                   'sign': sign_get(self.client_id, self.secret, stamp, path, token)}
        if token:
            headers['access_token'] = token
        response = self.session.get('https://openapi.tuyaus.com' + path, headers=headers,
                                    timeout=(5, 15), allow_redirects=False)
        if response.status_code != 200:
            return {'success': False, 'code': response.status_code}
        return response.json()

    def authenticate(self):
        reply = self.get(TOKEN_PATH)
        if not isinstance(reply, dict) or reply.get('success') is not True:
            raise ValueError('Autenticação: ' + safe_error(reply))
        self.token = reply.get('result', {}).get('access_token', '')
        if not self.token:
            raise ValueError('Autenticação sem token válido.')

    def close(self):
        self.session.close()
        self.secret = self.token = ''


def decode_model(result):
    if isinstance(result, dict) and isinstance(result.get('model'), str):
        return {**result, 'model': json.loads(result['model'])}
    return result


def property_definitions(source, result):
    """Preserva todas as funções, inclusive IDs desconhecidos ou acima de 255."""
    rows = []
    def visit(node, scope='', section=''):
        if isinstance(node, dict):
            code = node.get('code')
            has_definition = section in {'properties', 'functions', 'status'}
            if isinstance(code, str) and has_definition:
                spec = node.get('typeSpec', node.get('values', {}))
                if isinstance(spec, str):
                    try:
                        spec = json.loads(spec)
                    except ValueError:
                        spec = {'unparsed': spec}
                if not isinstance(spec, dict):
                    spec = {'unparsed': spec}
                rows.append(scrub({
                    'source': source, 'service': scope, 'section': section,
                    'dp_id': node.get('dp_id', node.get('dpId', node.get('abilityId'))),
                    'code': code, 'name': node.get('name'),
                    'type': node.get('type', spec.get('type')),
                    'access': node.get('accessMode'),
                    'access_inferred': ('w' if section == 'functions' else 'r' if section == 'status' else None)
                                       if 'accessMode' not in node else None,
                    'unit': spec.get('unit'), 'scale': spec.get('scale'),
                    'type_spec': spec,
                }))
            next_scope = node.get('code', scope) if 'properties' in node else scope
            for key, value in node.items():
                if isinstance(value, (dict, list)):
                    visit(value, next_scope, key if key in {'properties', 'functions', 'status'} else section)
        elif isinstance(node, list):
            for value in node:
                visit(value, scope, section)
    visit(result)
    return rows


def collect(cloud=None, controller=None):
    report = {'device_id': DEVICE_ID, 'collected_at_utc': datetime.now(timezone.utc).isoformat(),
              'cloud_requested': cloud is not None, 'metadata': {}, 'queries': {},
              'schema': {}, 'properties': [], 'lan': {},
              'limitations': [
                  'Nome Smart Life, product_id e modelId não confirmam modelo comercial.',
                  'Ausência de medição no mapping não prova ausência no aparelho.',
                  'Amostra de estado não prova todas as propriedades ou recursos físicos.',
              ]}
    if cloud:
        for label, path in PATHS.items():
            try:
                reply = cloud.get(path)
                if not isinstance(reply, dict) or reply.get('success') is not True:
                    report['queries'][label] = {'ok': False, 'error': safe_error(reply)}
                    continue
                result = reply.get('result', {})
                report['queries'][label] = {'ok': True}
                if label == 'device_details':
                    # Esta API também devolve a Local Key: somente estes campos saem da memória.
                    fields = ['name', 'product_name', 'product_id', 'category', 'model', 'brand', 'manufacturer']
                    report['metadata'] = {key: result[key] for key in fields if key in result}
                elif label == 'shadow_properties':
                    report['schema'][label] = scrub(result)
                else:
                    result = decode_model(result)
                    report['schema'][label] = scrub(result)
                    report['properties'].extend(property_definitions(label, result))
            except Exception:
                report['queries'][label] = {'ok': False, 'error': 'Falha de rede ou resposta inválida; nenhum detalhe privado exibido.'}
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            local = (controller or Controller()).status()
        report['lan'] = {'ok': True, 'timestamp': local['timestamp'], 'dps': scrub(local['dps'])}
    except Exception:
        report['lan'] = {'ok': False, 'error': 'Leitura LAN indisponível nesta tentativa.'}
    return scrub(report)


def main():
    args = argparse.ArgumentParser(description=__doc__)
    args.add_argument('--somente-lan', action='store_true', help='Não solicita credenciais nem consulta a cloud.')
    options = args.parse_args()
    load_dotenv(ROOT / '.env')
    logging.getLogger('tinytuya').setLevel(logging.CRITICAL)
    cloud = None
    try:
        if not options.somente_lan:
            print('Coleta de metadados e esquema completo. Somente leitura; nenhum comando será enviado.')
            print('Use Authorization Key do projeto Tuya; credenciais não serão salvas.')
            client = os.getenv('TUYA_ACCESS_ID') or input('Access ID: ').strip()
            secret = os.getenv('TUYA_ACCESS_SECRET') or getpass.getpass('Access Secret (oculto; não é a Local Key): ').strip()
            if not secret:
                raise ValueError('Access Secret não informado.')
            cloud = ReadOnlyCloud(client, secret)
            cloud.authenticate()
        report = collect(cloud)
        directory = ROOT / 'reports'
        directory.mkdir(exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        output = directory / f'esquema-completo-{stamp}.json'
        output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
        print(f'Relatório salvo em: {output}')
        print(f"Definições coletadas sem filtro de funções: {len(report['properties'])}")
        for name, info in report['queries'].items():
            print(name + ': ' + ('ok' if info['ok'] else info['error']))
        print('mapping.json e funcionamento do ar foram preservados.')
        if options.somente_lan:
            print('Coleta parcial: o esquema cloud ainda não foi consultado.')
        return 0
    except ValueError as error:
        print(str(error))
        return 1
    except (KeyboardInterrupt, EOFError):
        print('\nColeta cancelada. Credenciais não foram salvas.')
        return 1
    except Exception:
        print('Não foi possível concluir a coleta. Verifique rede e credenciais localmente; nenhum segredo foi exibido.')
        return 1
    finally:
        if cloud:
            cloud.close()


if __name__ == '__main__':
    raise SystemExit(main())
