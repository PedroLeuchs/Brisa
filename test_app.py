"""Testes sem conexão nem comandos ao ar-condicionado."""
import hashlib
import pytest
from fastapi.testclient import TestClient
import app as server
from controller import validate, Controller, ControllerError

HEADERS = {'Origin': 'http://localhost', 'X-Ar-Request': '1'}

@pytest.fixture
def client(monkeypatch, tmp_path):
    salt = b'test-only-salt!!'
    digest = hashlib.scrypt(b'test-password-123', salt=salt, n=16384, r=8, p=1).hex()
    monkeypatch.setenv('APP_PASSWORD_HASH', salt.hex() + ':' + digest)
    from backend.services.sessions import SessionStore
    monkeypatch.setattr(server, 'sessions', SessionStore(tmp_path / 'sessions.sqlite3'))
    # O coletor de uso nunca consulta o aparelho físico durante testes HTTP.
    from backend.services.consumption import ConsumptionStore
    monkeypatch.setattr(server.consumption, 'store', ConsumptionStore(tmp_path / 'consumption.sqlite3'))
    monkeypatch.setattr(server.consumption, 'start', lambda: None)
    monkeypatch.setattr(server.consumption, 'stop', lambda: None)
    server.attempts.clear()
    with TestClient(server.app, base_url='http://localhost') as c:
        yield c

def login(client):
    return client.post('/api/login', json={'password': 'test-password-123'}, headers=HEADERS)

def test_auth_required(client):
    assert client.get('/api/status').status_code == 401
    assert client.post('/api/command', json={'code': 'switch', 'value': True}, headers=HEADERS).status_code == 401

def test_remembered_session_survives_reload_restart_and_logout_revokes_cookie(client, monkeypatch):
    from backend.services.sessions import SessionStore
    response = client.post('/api/login', json={'password':'test-password-123','remember':True}, headers=HEADERS)
    assert response.status_code == 200
    assert 'Max-Age=2592000' in response.headers['set-cookie']
    token = client.cookies.get('ar_session')
    monkeypatch.setattr(server, 'sessions', SessionStore(server.sessions.path))
    assert client.get('/api/session').status_code == 200
    assert client.get('/api/session').status_code == 200
    assert client.post('/api/logout', json={}, headers=HEADERS).status_code == 200
    client.cookies.set('ar_session', token)
    assert client.get('/api/session').status_code == 401

def test_short_session_validity_and_invalid_remember(client):
    response = login(client)
    assert 'Max-Age=43200' in response.headers['set-cookie']
    assert client.post('/api/login',json={'password':'test-password-123','remember':'true'},headers=HEADERS).status_code == 400

def test_csrf_and_host(client):
    assert client.post('/api/login', json={'password': 'x'}).status_code == 403
    assert client.post('/api/login', json={}, headers={**HEADERS, 'Origin': 'http://evil.test'}).status_code == 403
    assert client.get('/', headers={'Host': 'evil.test'}).status_code == 400

def test_session_and_logout(client, monkeypatch):
    monkeypatch.setattr(server.controller, 'status', lambda: {'state': {}, 'available': [], 'dps': {}})
    response = login(client)
    assert response.status_code == 200
    assert 'HttpOnly' in response.headers['set-cookie']
    assert 'SameSite=strict' in response.headers['set-cookie']
    assert client.get('/api/status').status_code == 200
    assert client.post('/api/logout', json={}, headers=HEADERS).status_code == 200
    assert client.get('/api/status').status_code == 401

def test_login_limit(client):
    for _ in range(5):
        assert client.post('/api/login', json={'password': 'wrong'}, headers=HEADERS).status_code == 401
    assert login(client).status_code == 429

@pytest.mark.parametrize('code,value', [('temp_set',15),('temp_set',32),('temp_set',True),('temp_set',22.5),('switch','true'),('mode','cool'),('fan_speed_enum','max'),('unknown',True)])
def test_invalid_controls(code,value):
    with pytest.raises(ValueError): validate(code,value)

def test_no_unmapped_writes(monkeypatch):
    import controller
    monkeypatch.setattr(controller, 'mapping', lambda: {})
    c = Controller()
    monkeypatch.setattr(c, 'device', lambda: pytest.fail('Unmapped command reached device'))
    with pytest.raises(ControllerError): c.command('switch',True)

def test_secrets_not_served(client):
    for path in ['/.env', '/assets/.env', '/mapping.json', '/discovery.json']:
        assert client.get(path).status_code == 404

def test_backend_errors_redacted(client,monkeypatch):
    login(client)
    def fail(): raise RuntimeError('SECRET_MUST_NOT_APPEAR')
    monkeypatch.setattr(server.controller,'status',fail)
    response = client.get('/api/status')
    assert response.status_code == 503
    assert 'SECRET_MUST_NOT_APPEAR' not in response.text

def test_bad_payload(client):
    login(client)
    for value in [[],{}, {'code': [], 'value': True}, {'code': 'switch', 'value': True, 'ip': '1.1.1.1'}]:
        assert client.post('/api/command', json=value, headers=HEADERS).status_code == 422

def test_shell_and_api_cache(client,monkeypatch):
    assert client.get('/').status_code == 200
    assert client.get('/sw.js').status_code == 200
    assert client.get('/api/status').headers['cache-control'] == 'no-store'

def test_read_and_write_serialization(monkeypatch):
    import controller
    monkeypatch.setattr(controller, 'mapping', lambda: {'switch': '1', 'temp_set': '2'})
    class Fake:
        closed = False
        def status(self): return {'dps': {'1': False, '2': 24}}
        def set_multiple_values(self, values):
            assert values == {'1': True}
            return {'dps': values}
        def close(self): self.closed = True
    device = Fake()
    c = Controller()
    monkeypatch.setattr(c,'device',lambda: device)
    assert c.status()['state'] == {'switch': False, 'temp_set': 24}
    assert c.command('switch',True)['sent']
    assert device.closed
    delays = []
    monkeypatch.setattr(controller.time, 'sleep', delays.append)
    assert c.command('switch',True)['sent']
    assert delays and 0 < delays[0] <= 1.1

def test_read_reconnects_after_failure(monkeypatch):
    import controller
    monkeypatch.setattr(controller, 'mapping', lambda: {'switch': '1'})
    monkeypatch.setattr(controller.time, 'sleep', lambda _: None)
    class Fake:
        def __init__(self, reply): self.reply, self.closed = reply, False
        def status(self): return self.reply
        def close(self): self.closed = True
    failed, recovered = Fake({'Error':'offline'}), Fake({'dps':{'1':True}})
    devices = iter([failed, recovered])
    c = Controller()
    monkeypatch.setattr(c, 'device', lambda: next(devices))
    assert c.status()['state']['switch'] is True
    assert failed.closed and recovered.closed
    assert not c.lock.locked()

def test_write_failure_not_repeated_and_lock_released(monkeypatch):
    import controller
    monkeypatch.setattr(controller, 'mapping', lambda: {'switch': '1'})
    class Fake:
        calls = 0
        closed = False
        def set_multiple_values(self, values):
            self.calls += 1
            raise OSError('connection lost')
        def close(self): self.closed = True
    device = Fake()
    c = Controller()
    monkeypatch.setattr(c, 'device', lambda: device)
    with pytest.raises(OSError): c.command('switch',True)
    assert device.calls == 1 and device.closed and not c.lock.locked()

def test_busy_device_does_not_accumulate_waiters(monkeypatch):
    c = Controller()
    monkeypatch.setattr(c, 'device', lambda: pytest.fail('Must not open competing connection'))
    c.lock.acquire()
    try:
        with pytest.raises(ControllerError, match='outro pedido'): c.status()
    finally:
        c.lock.release()

def test_session_check_does_not_contact_device(client,monkeypatch):
    monkeypatch.setattr(server.controller,'status', lambda: pytest.fail('Session check contacted AC'))
    assert client.get('/api/session').status_code == 401
    login(client)
    assert client.get('/api/session').status_code == 200

def test_local_device_connects_once_but_never_reconnects_inside_write(monkeypatch):
    import tinytuya
    from controller import LocalDevice
    calls = []
    def connect(device, renew):
        calls.append(renew)
        return True
    monkeypatch.setattr(tinytuya.Device, '_get_socket', connect)
    device = LocalDevice('test-id', '192.168.1.3', '0'*16)
    assert device._get_socket(False) is True
    # Simula perda de socket; uma repetição não pode abrir outra conexão.
    device.socket = None
    assert device._get_socket(False) == tinytuya.ERR_OFFLINE
    assert calls == [False]

def test_device_catalog_and_status_are_authenticated_and_protocol_independent(client,monkeypatch):
    assert client.get('/api/devices').status_code == 401
    assert client.get('/api/devices/home-ac/status').status_code == 401
    login(client)
    monkeypatch.setattr(server.devices.adapter('home-ac'), 'capabilities', lambda: {'switch':{'type':'bool','values':None}})
    monkeypatch.setattr(server.controller, 'status', lambda: {'state':{'switch':False},'available':['switch'],'timestamp':123,'dps':{'1':False}})
    catalog=client.get('/api/devices')
    assert catalog.status_code == 200
    assert catalog.json()['devices'][0]['id'] == 'home-ac'
    import backend.adapters.tuya_local as adapter_module
    monkeypatch.setattr(adapter_module,'ambient_reading',lambda dps,timestamp: {'available':False,'value':None,'unit':'°C','observed_at':None,'reason':'schema_unconfirmed'})
    status=client.get('/api/devices/home-ac/status')
    assert status.json() == {'device_id':'home-ac','state':{'switch':False},'available':['switch'],'timestamp':123,
                            'telemetry':{'ambient_temperature':{'available':False,'value':None,'unit':'°C','observed_at':None,'reason':'schema_unconfirmed'}}}
    assert 'dps' not in status.json()
    assert client.get('/api/devices/unknown/status').status_code == 404

def test_device_command_routes_validate_target_and_payload(client,monkeypatch):
    login(client)
    calls=[]
    monkeypatch.setattr(server.controller,'command',lambda code,value: calls.append((code,value)) or {'sent':True})
    assert client.post('/api/devices/unknown/command',json={'code':'switch','value':True},headers=HEADERS).status_code == 404
    assert client.post('/api/devices/home-ac/command',json={'code':'switch','value':True,'ip':'1.1.1.1'},headers=HEADERS).status_code == 422
    assert not calls
    assert client.post('/api/devices/home-ac/command',json={'code':'switch','value':True},headers=HEADERS).status_code == 200
    assert calls == [('switch',True)]

def test_automation_routes_are_authenticated_and_forward_safe_payloads(client, monkeypatch):
    assert client.get('/api/automations').status_code == 401
    assert client.get('/api/automations/health').status_code == 401
    login(client)
    health = client.get('/api/automations/health')
    assert health.status_code == 200
    assert health.json()['worker_scope'] == 'single_process_single_worker'
    created = {'id':'schedule-1','device_id':'home-ac','code':'switch','value':True,
               'time':'08:30','days':[0],'enabled':True}
    monkeypatch.setattr(server.automations, 'list', lambda: [created])
    monkeypatch.setattr(server.automations, 'create', lambda body: {**created, **body})
    monkeypatch.setattr(server.automations, 'update', lambda automation_id, body: {**created, **body, 'id':automation_id})
    deleted=[]
    monkeypatch.setattr(server.automations, 'delete', deleted.append)
    response=client.get('/api/automations')
    assert response.status_code == 200 and response.json()['timezone'] == 'America/Sao_Paulo'
    body={'device_id':'home-ac','code':'switch','value':True,'time':'08:30','days':[0],'enabled':True}
    assert client.post('/api/automations',json=body,headers=HEADERS).status_code == 200
    assert client.post('/api/automations/schedule-1',json={**body,'enabled':False},headers=HEADERS).json()['enabled'] is False
    assert client.post('/api/automations/schedule-1/delete',json={},headers=HEADERS).status_code == 200
    assert deleted == ['schedule-1']

def test_consumption_auth_empty_history_settings_persistence_and_validation(client, monkeypatch):
    monkeypatch.setattr(server.controller, 'status', lambda: pytest.fail('Dashboard não pode consultar o aparelho'))
    assert client.get('/api/consumption/home-ac').status_code == 401
    assert client.post('/api/consumption/home-ac/settings',json={},headers=HEADERS).status_code == 401
    login(client)
    assert client.get('/api/consumption/unknown').status_code == 404
    response = client.get('/api/consumption/home-ac')
    assert response.status_code == 200
    assert response.json()['totals']['estimated_kwh'] is None
    assert response.json()['collection_started_at'] is None
    assert response.json()['settings']['tariff_per_kwh'] == 1.056961
    body = {'reference_watts':1200,'tariff_per_kwh':1.2}
    assert client.post('/api/consumption/home-ac/settings',json=body,headers=HEADERS).status_code == 200
    from backend.services.consumption import ConsumptionStore
    monkeypatch.setattr(server.consumption,'store',ConsumptionStore(server.consumption.store.path))
    assert client.get('/api/consumption/home-ac').json()['settings']['reference_watts'] == 1200
    assert client.get('/api/consumption/home-ac?start=invalid').status_code == 422
    assert client.post('/api/consumption/home-ac/settings',json={'reference_watts':-2,'tariff_per_kwh':1},headers=HEADERS).status_code == 422
    assert client.post('/api/consumption/home-ac/settings',json=body).status_code == 403

def test_consumption_storage_failure_is_redacted(client, monkeypatch):
    login(client)
    def fail(*args): raise OSError('secret-never-return')
    monkeypatch.setattr(server.consumption.store,'dashboard',fail)
    response=client.get('/api/consumption/home-ac')
    assert response.status_code == 503
    assert 'secret-never-return' not in response.text
