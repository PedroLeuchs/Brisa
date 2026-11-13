import json
import os
import threading
import time
import ipaddress
from contextlib import contextmanager
from pathlib import Path
import tinytuya

ROOT = Path(__file__).resolve().parent
FIELDS = {
    'switch': ('bool', None), 'temp_set': ('int', (16, 31)),
    'mode': ('enum', ['auto', 'cold', 'hot', 'wet', 'wind']),
    'fan_speed_enum': ('enum', ['auto', 'high', 'middle', 'low']),
    **{k: ('bool', None) for k in ['mode_eco', 'cleaning', 'sleep', 'switch_vertical', 'switch_horizontal']},
}

class ControllerError(Exception):
    pass

class LocalDevice(tinytuya.Device):
    """Uma conexão por operação, sem reenvio após perder o socket."""
    def _get_socket(self, renew):
        # TinyTuya usa socketRetryLimit também para a primeira conexão:
        # zero impede qualquer conexão. A recuperação usa um objeto novo.
        if renew or self.socket is None:
            if getattr(self, '_connection_attempted', False):
                return tinytuya.ERR_OFFLINE
            self._connection_attempted = True
        return super()._get_socket(renew)

def validate(code, value):
    if code not in FIELDS:
        raise ValueError('Função desconhecida.')
    kind, allowed = FIELDS[code]
    if kind == 'bool' and type(value) is not bool:
        raise ValueError('Informe verdadeiro ou falso.')
    if kind == 'int' and (type(value) is not int or not allowed[0] <= value <= allowed[1]):
        raise ValueError('Temperatura deve ser um inteiro entre 16 e 31.')
    if kind == 'enum' and (not isinstance(value, str) or value not in allowed):
        raise ValueError('Opção inválida.')

def mapping():
    data = json.loads((ROOT / 'mapping.json').read_text(encoding='utf-8'))
    result = {}
    for code, dp in data.items():
        if code not in FIELDS or dp is None:
            continue
        if type(dp) is not int or not 1 <= dp <= 255 or str(dp) in result.values():
            raise ControllerError('Revise mapping.json: IDs devem ser únicos, entre 1 e 255.')
        result[code] = str(dp)
    return result

class Controller:
    def __init__(self):
        self.lock = threading.Lock()
        self.last_write = 0

    @contextmanager
    def operation(self):
        if not self.lock.acquire(timeout=0.25):
            raise ControllerError('O aparelho está atendendo outro pedido. Tentando novamente em instantes.')
        try:
            yield
        finally:
            self.lock.release()

    def device(self):
        key = os.getenv('TUYA_LOCAL_KEY', '')
        ip = os.getenv('TUYA_IP', '')
        version = os.getenv('TUYA_VERSION', '')
        if not key or not ip or not version:
            raise ControllerError('Preencha IP, versão e Local Key no .env deste computador.')
        try:
            address = ipaddress.IPv4Address(ip)
            if not address.is_private or address.is_loopback or address.is_multicast:
                raise ValueError()
            if version not in ['3.1', '3.3', '3.4', '3.5']:
                raise ValueError()
        except ValueError:
            raise ControllerError('IP privado ou versão do protocolo inválidos.') from None
        device = LocalDevice(os.getenv('TUYA_DEVICE_ID', 'CONFIGURE_TUYA_DEVICE_ID'), ip,
                              key, version=float(version), connection_timeout=3,
                              connection_retry_limit=1, connection_retry_delay=0)
        # Limita esperas e não reenvia comandos cujo resultado é incerto.
        device.set_socketRetryLimit(1)
        return device

    @staticmethod
    def checked(reply):
        if not isinstance(reply, dict) or 'Error' in reply or 'Err' in reply:
            raise ControllerError('O aparelho não respondeu. Verifique IP, chave e protocolo no computador.')
        return reply

    def status(self):
        with self.operation():
            # Apenas leituras são repetidas, sempre com uma conexão nova.
            for attempt in range(2):
                d = self.device()
                try:
                    reply = self.checked(d.status())
                    dps = reply.get('dps')
                    if not isinstance(dps, dict) or not dps:
                        raise ControllerError('Resposta sem estado local. Tentando reconectar.')
                    ids = mapping()
                    return {'state': {code: dps[dp] for code, dp in ids.items() if dp in dps},
                            'available': list(ids), 'dps': dps, 'timestamp': time.time()}
                except (ControllerError, OSError):
                    if attempt == 1:
                        raise ControllerError('Sem resposta do ar. O painel tentará reconectar automaticamente.') from None
                finally:
                    d.close()
                time.sleep(0.2)

    def command(self, code, value):
        validate(code, value)
        ids = mapping()
        if code not in ids:
            raise ControllerError('Mapeie esta função no mapping.json antes de usar.')
        with self.operation():
            remaining = 1.1 - (time.monotonic() - self.last_write)
            if remaining > 0:
                time.sleep(remaining)
            d = self.device()
            try:
                self.last_write = time.monotonic()
                self.checked(d.set_multiple_values({ids[code]: value}))
            finally:
                d.close()
        return {'sent': True, 'message': 'Comando enviado. Atualizando estado do aparelho.'}
