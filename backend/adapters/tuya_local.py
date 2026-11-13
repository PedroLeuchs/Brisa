"""Fronteira de compatibilidade: preserva a integração TinyTuya validada."""
from controller import Controller, FIELDS, mapping
from backend.adapters.ambient import ambient_reading


class TuyaLocalAdapter:
    def __init__(self, controller=None):
        self.controller = controller or Controller()

    def capabilities(self):
        ids = mapping()
        return {code: {'type': FIELDS[code][0], 'values': FIELDS[code][1],
                       **({'step': 1} if code == 'temp_set' else {})} for code in ids}

    def status(self):
        reply = self.controller.status()
        # O contrato da interface não depende de DPS ou identificadores Tuya.
        return {**{key: reply[key] for key in ('state', 'available', 'timestamp')},
                'telemetry': {'ambient_temperature': ambient_reading(reply.get('dps', {}), reply['timestamp'])}}

    def command(self, code, value):
        return self.controller.command(code, value)
