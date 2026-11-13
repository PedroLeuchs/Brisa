"""Tuya Cloud transport for the existing Brisa device contract."""
import hashlib
import hmac
import json
import os
import threading
import time
import urllib.error
import urllib.request

from controller import ControllerError, FIELDS, validate
from backend.adapters.ambient import unavailable


HOSTS = {"us": "https://openapi.tuyaus.com"}
EMPTY_HASH = hashlib.sha256(b"").hexdigest()


class TuyaCloudController:
    def __init__(self, *, client_id=None, secret=None, device_id=None, opener=None):
        self.client_id = client_id or os.getenv("TUYA_ACCESS_ID", "")
        self.secret = secret or os.getenv("TUYA_ACCESS_SECRET", "")
        self.device_id = device_id or os.getenv("TUYA_DEVICE_ID", "")
        region = os.getenv("TUYA_CLOUD_REGION", "us").lower()
        if region not in HOSTS:
            raise ControllerError("Região Tuya Cloud não suportada.")
        self.host = HOSTS[region]
        self.opener = opener or urllib.request.urlopen
        self.lock = threading.RLock()
        self.token = ""
        self.token_until = 0.0
        self.functions = None
        self.functions_until = 0.0

    def _configured(self):
        if not all((self.client_id, self.secret, self.device_id)):
            raise ControllerError("Configure as credenciais Tuya Cloud no servidor.")
        if not self.device_id.isalnum():
            raise ControllerError("Identificador Tuya inválido.")

    def _request(self, method, path, body=None, token=""):
        self._configured()
        payload = b"" if body is None else json.dumps(body, separators=(",", ":")).encode()
        stamp = str(int(time.time() * 1000))
        digest = hashlib.sha256(payload).hexdigest()
        canonical = f"{method}\n{digest}\n\n{path}"
        signed = (self.client_id + token + stamp + canonical).encode()
        signature = hmac.new(self.secret.encode(), signed, hashlib.sha256).hexdigest().upper()
        headers = {"client_id": self.client_id, "t": stamp,
                   "sign_method": "HMAC-SHA256", "sign": signature}
        if token:
            headers["access_token"] = token
        if body is not None:
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(self.host + path, data=payload if body is not None else None,
                                         headers=headers, method=method)
        try:
            with self.opener(request, timeout=15) as response:
                reply = json.load(response)
        except (urllib.error.URLError, TimeoutError, ValueError, OSError) as exc:
            raise ControllerError("Sem resposta da Tuya Cloud; confira conexão e permissões.") from None
        if not isinstance(reply, dict) or reply.get("success") is not True:
            code = reply.get("code") if isinstance(reply, dict) else None
            label = str(code) if isinstance(code, (str, int)) and str(code).isalnum() else "indisponível"
            raise ControllerError(f"Tuya Cloud recusou a operação (código {label}).")
        return reply.get("result")

    def _token(self):
        if self.token and time.time() < self.token_until:
            return self.token
        result = self._request("GET", "/v1.0/token?grant_type=1")
        if not isinstance(result, dict) or not isinstance(result.get("access_token"), str):
            raise ControllerError("Autenticação Tuya Cloud sem token válido.")
        self.token = result["access_token"]
        self.token_until = time.time() + max(1, min(int(result.get("expire_time", 3600)), 3600) - 60)
        return self.token

    def capabilities(self):
        with self.lock:
            if self.functions is None or time.time() >= self.functions_until:
                result = self._request("GET", f"/v1.0/iot-03/devices/{self.device_id}/functions",
                                       token=self._token())
                rows = result.get("functions", []) if isinstance(result, dict) else result
                if not isinstance(rows, list):
                    raise ControllerError("Tuya Cloud não retornou funções válidas.")
                self.functions = {row["code"] for row in rows if isinstance(row, dict)
                                  and isinstance(row.get("code"), str)}
                self.functions_until = time.time() + 3600
            return {code: {"type": FIELDS[code][0], "values": FIELDS[code][1],
                           **({"step": 1} if code == "temp_set" else {})}
                    for code in FIELDS if code in self.functions}

    def status(self):
        with self.lock:
            available = list(self.capabilities())
            result = self._request("GET", f"/v1.0/iot-03/devices/{self.device_id}/status",
                                   token=self._token())
            if not isinstance(result, list):
                raise ControllerError("Tuya Cloud não retornou estado válido.")
            state = {row["code"]: row.get("value") for row in result
                     if isinstance(row, dict) and isinstance(row.get("code"), str)
                     and row["code"] in set(available) | {"temp_current", "work_status"}}
            return {"state": state, "available": available, "dps": {}, "timestamp": time.time()}

    def command(self, code, value):
        validate(code, value)
        with self.lock:
            if code not in self.capabilities():
                raise ControllerError("Esta função não está disponível na Tuya Cloud.")
            # A escrita ocorre uma vez. Um erro de rede pode deixar o resultado incerto.
            self._request("POST", f"/v1.0/iot-03/devices/{self.device_id}/commands",
                          {"commands": [{"code": code, "value": value}]}, self._token())
        return {"sent": True, "message": "Comando enviado. Atualizando estado do aparelho."}


class TuyaCloudAdapter:
    transport = "tuya_cloud"

    def __init__(self, controller):
        self.controller = controller

    def capabilities(self):
        return self.controller.capabilities()

    def status(self):
        reply = self.controller.status()
        raw = reply["state"].get("temp_current")
        ambient = ({"available": True, "value": raw, "unit": "°C",
                    "observed_at": reply["timestamp"], "source": "device"}
                   if type(raw) is int and -20 <= raw <= 80 else unavailable("reading_missing"))
        return {key: reply[key] for key in ("state", "available", "timestamp")} | {
            "telemetry": {"ambient_temperature": ambient}}

    def command(self, code, value):
        return self.controller.command(code, value)
