"""Cloud transport contract; all Tuya responses are simulated."""
import io
import json

import pytest

from backend.adapters.tuya_cloud import TuyaCloudController, TuyaCloudAdapter


def test_cloud_status_capabilities_and_single_command():
    calls = []

    def opener(request, timeout):
        calls.append(request)
        path = request.full_url.split("openapi.tuyaus.com", 1)[1]
        if path.startswith("/v1.0/token"):
            result = {"access_token": "test-token", "expire_time": 3600}
        elif path.endswith("/functions"):
            result = {"functions": [{"code": "switch", "type": "Boolean"},
                                    {"code": "temp_set", "type": "Integer"},
                                    {"code": "mode_eco", "type": "Boolean"}]}
        elif path.endswith("/status"):
            result = [{"code": "switch", "value": False},
                      {"code": "temp_set", "value": 23},
                      {"code": "temp_current", "value": 31}]
        else:
            assert path.endswith("/commands")
            assert request.get_method() == "POST"
            assert json.loads(request.data) == {"commands": [{"code": "switch", "value": True}]}
            result = True
        return io.BytesIO(json.dumps({"success": True, "result": result}).encode())

    controller = TuyaCloudController(client_id="test-client", secret="test-secret",
                                     device_id="testdevice123", opener=opener)
    adapter = TuyaCloudAdapter(controller)
    assert set(adapter.capabilities()) == {"switch", "temp_set", "mode_eco"}
    status = adapter.status()
    assert status["state"]["switch"] is False
    assert status["telemetry"]["ambient_temperature"]["value"] == 31
    assert "dps" not in status
    assert adapter.command("switch", True)["sent"] is True
    assert len([request for request in calls if request.get_method() == "POST"]) == 1
    with pytest.raises(ValueError):
        adapter.command("switch", "true")
    assert len(calls) == 4
