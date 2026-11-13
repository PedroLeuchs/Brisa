"""Validação reproduzível da LAN; não envia comandos de operação."""
import contextlib
import io
import json
import logging
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from controller import Controller, ControllerError

ROOT = Path(__file__).resolve().parent


def validate_local(controller=None):
    start = time.monotonic()
    result = (controller or Controller()).status()
    return {
        'connection': 'LAN',
        'ip': os.getenv('TUYA_IP', ''),
        'protocol': os.getenv('TUYA_VERSION', ''),
        'duration_ms': round((time.monotonic() - start) * 1000),
        'state': result['state'],
        'available': result['available'],
        'timestamp': result['timestamp'],
    }


def main():
    load_dotenv(ROOT / '.env')
    logging.getLogger('tinytuya').setLevel(logging.CRITICAL)
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            report = validate_local()
    except ControllerError as error:
        print(f'Leitura local indisponível: {error}')
        return 1
    except Exception:
        print('Falha na leitura local. Confira a conexão e a configuração no computador. Nenhum segredo foi exibido.')
        return 1
    print(json.dumps(report, indent=2, ensure_ascii=False))
    print('Leitura concluída pela LAN. Nenhum comando de operação foi enviado.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
