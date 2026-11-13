"""Consulta de provisionamento: somente leituras na cloud; sem salvar credenciais."""
import contextlib
import getpass
import io
import json
import logging
import os
from pathlib import Path

from dotenv import load_dotenv
import tinytuya
from controller import Controller, FIELDS, validate

ROOT = Path(__file__).resolve().parent
DEVICE_ID = 'CONFIGURE_TUYA_DEVICE_ID'


def safe_error(reply):
    """Exibe somente códigos e mensagens conhecidas; nunca a resposta completa."""
    if not isinstance(reply, dict):
        return 'resposta ausente ou inválida'
    code = str(reply.get('code', reply.get('Err', '')))
    code = code if code.isdigit() and len(code) <= 12 else 'indisponível'
    message = reply.get('msg', '')
    known = {
        'sign invalid': 'assinatura rejeitada',
        'clientId is invalid': 'Client ID rejeitado',
        'client_id is invalid': 'Client ID rejeitado',
        'request time is invalid': 'horário da requisição rejeitado',
        'permission deny': 'permissão negada',
        'No permissions. This project is not authorized to call this API': 'projeto sem autorização para esta API',
        'token invalid': 'token rejeitado',
        'token expired': 'token expirado',
    }
    reason = known.get(message, 'falha retornada pela Tuya') if isinstance(message, str) else 'falha retornada pela Tuya'
    return f'código {code}: {reason}'


class DiagnosticCloud(tinytuya.Cloud):
    last_failure = None

    def _tuyaplatform(self, *args, **kwargs):
        reply = super()._tuyaplatform(*args, **kwargs)
        if not isinstance(reply, dict) or reply.get('success') is not True:
            self.last_failure = safe_error(reply)
        return reply


def extract_ids(reply):
    """Somente associações explícitas code -> dp_id; nunca por posição."""
    result = {}
    def visit(node):
        if isinstance(node, dict):
            code = node.get('code')
            dp = node.get('dp_id', node.get('dpId'))
            if isinstance(code, str) and code in FIELDS and type(dp) is int and 1 <= dp <= 255:
                if code in result and result[code] != dp:
                    raise ValueError('IDs conflitantes para uma função.')
                result[code] = dp
            for value in node.values():
                visit(value)
        elif isinstance(node, list):
            for value in node:
                visit(value)
    visit(reply)
    if len(set(result.values())) != len(result):
        raise ValueError('IDs duplicados para funções diferentes.')
    return result


def main():
    load_dotenv(ROOT / '.env')
    logging.getLogger('tinytuya').setLevel(logging.CRITICAL)
    print('Obter IDs das funções. Esta etapa consulta a cloud uma vez; o painel continua local.')
    print('Credenciais: projeto Tuya > Overview > Authorization Key.')
    client_id = os.getenv('TUYA_ACCESS_ID') or input('Access ID / Client ID: ').strip()
    secret = os.getenv('TUYA_ACCESS_SECRET') or getpass.getpass('Access Secret do projeto (oculto; não é a Local Key): ').strip()
    if not secret:
        raise ValueError('Access Secret não informado.')
    with contextlib.redirect_stdout(io.StringIO()):
        cloud = DiagnosticCloud(apiRegion='us', apiKey=client_id, apiSecret=secret, apiDeviceID=DEVICE_ID)
    if not cloud.token:
        raise ValueError('Autenticação: ' + (cloud.last_failure or 'resposta inválida') + '. Nenhum arquivo alterado.')
    paths = [f'/v2.0/cloud/thing/{DEVICE_ID}/shadow/properties',
             f'/v1.1/devices/{DEVICE_ID}/specifications']
    found = {}
    for path in paths:
        with contextlib.redirect_stdout(io.StringIO()):
            reply = cloud.cloudrequest(path, action='GET')
        if isinstance(reply, dict) and reply.get('success') is True:
            found = extract_ids(reply.get('result', {}))
            if found:
                break
        else:
            print('Consulta de IDs: ' + safe_error(reply))
    if not found:
        raise ValueError('As consultas não retornaram IDs. Verifique as permissões/validade do serviço no projeto. Nenhum mapeamento foi alterado.')
    # A resposta cloud deve apontar para um DP presente e de tipo compatível na LAN.
    local = Controller().status()['dps']
    accepted = {}
    for code, dp in found.items():
        if str(dp) not in local:
            continue
        try:
            validate(code, local[str(dp)])
        except ValueError:
            print(f'{code}: tipo/valor local incompatível; função mantida bloqueada.')
            continue
        accepted[code] = dp
    if not accepted:
        raise ValueError('Nenhum ID retornado corresponde ao estado LAN com tipo compatível. Nada alterado.')
    path = ROOT / 'mapping.json'
    current = json.loads(path.read_text(encoding='utf-8'))
    updated = {**current, **accepted}
    ids = [v for v in updated.values() if v is not None]
    if len(ids) != len(set(ids)):
        raise ValueError('Mapeamento existente conflita com os IDs retornados. Nada alterado.')
    # Preserva a versão anterior, sem incluir chave ou credenciais.
    path.with_name('mapping.previous.json').write_text(json.dumps(current, indent=2) + '\n', encoding='utf-8')
    temporary = path.with_name('mapping.pending.json')
    temporary.write_text(json.dumps(updated, indent=2) + '\n', encoding='utf-8')
    temporary.replace(path)
    print('Funções configuradas: ' + ', '.join(accepted))
    print('Atualize a página do painel. Não precisa reiniciar o servidor.')


if __name__ == '__main__':
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        print('\nCancelado. Nenhuma credencial foi salva.')
    except ValueError as exc:
        print(str(exc))
        raise SystemExit(1)
    except Exception:
        print('Não foi possível concluir a consulta. Verifique conexão, credenciais e disponibilidade da API. Credenciais não foram exibidas.')
        raise SystemExit(1)
