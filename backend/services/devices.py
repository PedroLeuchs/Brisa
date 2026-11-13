from typing import Protocol


class DeviceAdapter(Protocol):
    def capabilities(self) -> dict: ...
    def status(self) -> dict: ...
    def command(self, code: str, value): ...


class DeviceService:
    """Registro explícito; o cliente não pode fornecer IP, chave ou destino LAN."""
    def __init__(self, adapter: DeviceAdapter):
        self.adapters = {'home-ac': adapter}

    def adapter(self, device_id):
        if device_id not in self.adapters:
            raise KeyError(device_id)
        return self.adapters[device_id]

    def list(self):
        return [{'id': key, 'name': 'Clima da casa', 'transport': getattr(adapter, 'transport', 'local'),
                 'capabilities': adapter.capabilities()} for key, adapter in self.adapters.items()]

    def status(self, device_id):
        return {'device_id': device_id, **self.adapter(device_id).status()}

    def command(self, device_id, code, value):
        return self.adapter(device_id).command(code, value)
