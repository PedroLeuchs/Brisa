"""Integração isolada do relay/agente. Nenhum teste importa ou inicia app.py."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import json
import threading
import uuid

import pytest
from fastapi.testclient import TestClient

from remote.agent import Agent, RelayClient
from remote.broker import create_app
from remote.inprocess import ProcessLock
from remote.journal import Journal
from remote.local_executor import SharedLanExecutor
from remote.protocol import safe_observation
from remote.storage import RelayError, RelayStore


class Clock:
    value=1000.0
    def __call__(self):return self.value


class SimulatedExecutor:
    def __init__(self,clock):
        self.clock=clock;self.calls=[];self.state={'switch':False,'temp_set':21}
    def capabilities(self,device):return ['switch','temp_set']
    def execute(self,device,code,value,deadline):
        assert self.clock()<deadline
        self.calls.append((device,code,value))
        self.state[code]=value
    def status(self,device):
        return {'state':dict(self.state),'timestamp':self.clock(),'dps':{'1':True},'local_key':'DO_NOT_EXPORT'}


@pytest.fixture
def setup(tmp_path):
    clock=Clock();store=RelayStore(tmp_path/'relay.sqlite3',clock)
    agent_token=store.provision_agent('home','bridge',{'home-ac':['switch','temp_set']})
    operator=store.provision_operator('home','owner',['home-ac'])
    app=create_app(store)
    with TestClient(app,base_url='http://127.0.0.1:8090') as http:
        class Client:
            fail_ack=False
            def poll(self):
                reply=http.post('/v1/agent/poll',json={},headers={'Authorization':'Bearer '+agent_token});reply.raise_for_status();return reply.json()
            def acknowledge(self,key,result):
                if self.fail_ack:raise ConnectionError('simulated disconnect')
                reply=http.post('/v1/agent/commands/'+key+'/result',json=result,headers={'Authorization':'Bearer '+agent_token});reply.raise_for_status()
        client=Client();executor=SimulatedExecutor(clock)
        journal=Journal(tmp_path/'agent.sqlite3')
        agent=Agent(client,journal,executor,'home','bridge',['home-ac'],clock=clock,monotonic=clock)
        yield {'http':http,'store':store,'clock':clock,'operator':operator,'agent_token':agent_token,
               'client':client,'executor':executor,'journal':journal,'agent':agent,'path':tmp_path}


def request(value=True,ttl=30,key=None):
    return {'request_id':str(key or uuid.uuid4()),'code':'switch','value':value,'ttl_seconds':ttl}


def enqueue(s,body=None):
    response=s['http'].post('/v1/devices/home-ac/commands',json=body or request(),headers={'Authorization':'Bearer '+s['operator']})
    assert response.status_code==200,response.text
    return response.json()


def result(s,key):
    return s['http'].get('/v1/commands/'+key,headers={'Authorization':'Bearer '+s['operator']})


def test_end_to_end_outbound_poll_and_observed_confirmation(setup):
    s=setup;command=enqueue(s);s['agent'].step();reply=result(s,command['id']).json()
    assert reply['status']=='confirmed'
    assert reply['result']['observation']['state']['switch'] is True
    assert len(s['executor'].calls)==1
    assert 'DO_NOT_EXPORT' not in json.dumps(reply)
    assert 'dps' not in reply['result']['observation']


def test_auth_roles_and_local_cookie_are_not_public_auth(setup):
    http=setup['http']
    assert http.get('/v1/devices').status_code==401
    assert http.get('/v1/devices',cookies={'ar_session':'anything'}).status_code==401
    assert http.post('/v1/agent/poll',headers={'Authorization':'Bearer '+setup['operator']}).status_code==401
    assert http.get('/v1/devices',headers={'Authorization':'Bearer '+setup['agent_token']}).status_code==401
    assert http.get('/v1/devices',headers={'Authorization':'Bearer '+setup['operator'],'Origin':'https://evil.test'}).status_code==403


def test_cross_home_isolation_and_revocation(setup):
    s=setup;command=enqueue(s)
    s['store'].provision_agent('other','other-bridge',{'other-ac':['switch']})
    token=s['store'].provision_operator('other','other-owner',['other-ac'])
    headers={'Authorization':'Bearer '+token}
    assert s['http'].get('/v1/commands/'+command['id'],headers=headers).status_code==404
    assert s['http'].post('/v1/devices/home-ac/commands',json=request(),headers=headers).status_code==404
    s['store'].revoke(s['operator'])
    assert result(s,command['id']).status_code==401


def test_idempotency_survives_concurrent_requests_and_relay_restart(setup):
    s=setup;body=request();principal=s['store'].authenticate(s['operator'],'operator')
    with ThreadPoolExecutor(max_workers=6) as pool:
        ids=list(pool.map(lambda _:s['store'].enqueue(principal,'home-ac',body)['id'],range(6)))
    assert len(set(ids))==1
    reopened=RelayStore(s['path']/'relay.sqlite3',s['clock'])
    assert reopened.enqueue(principal,'home-ac',body)['id']==ids[0]
    with pytest.raises(RelayError) as error:reopened.enqueue(principal,'home-ac',{**body,'value':False})
    assert error.value.status==409


def test_expired_queue_never_reaches_executor(setup):
    s=setup;command=enqueue(s,request(ttl=1));s['clock'].value+=2;s['agent'].step()
    assert not s['executor'].calls
    assert result(s,command['id']).json()['status']=='expired'


def test_expiry_during_delivery_is_rejected_by_agent(setup):
    s=setup;command=enqueue(s,request(ttl=1));poll=s['client'].poll()
    key,outcome=s['agent'].process(poll['command'],poll['server_time'],request_elapsed=2)
    assert outcome['status']=='expired' and not s['executor'].calls


def test_clock_skew_fails_closed(setup):
    s=setup;enqueue(s);poll=s['client'].poll();s['clock'].value+=20
    _,outcome=s['agent'].process(poll['command'],poll['server_time'])
    assert outcome['reason']=='clock_skew' and not s['executor'].calls


def test_ack_loss_and_agent_restart_flush_result_without_resending(setup):
    s=setup;command=enqueue(s);s['client'].fail_ack=True
    with pytest.raises(ConnectionError):s['agent'].step()
    assert len(s['executor'].calls)==1
    s['client'].fail_ack=False
    new=Agent(s['client'],Journal(s['path']/'agent.sqlite3'),s['executor'],'home','bridge',['home-ac'],clock=s['clock'],monotonic=s['clock'])
    new.step()
    assert len(s['executor'].calls)==1 and result(s,command['id']).json()['status']=='confirmed'


def test_reserved_before_crash_is_uncertain_and_never_reexecuted(setup):
    s=setup;command=enqueue(s);poll=s['client'].poll();s['journal'].reserve(poll['command'])
    restored=Journal(s['path']/'agent.sqlite3');restored.recover()
    new=Agent(s['client'],restored,s['executor'],'home','bridge',['home-ac'],clock=s['clock'],monotonic=s['clock']);new.step()
    assert not s['executor'].calls
    assert result(s,command['id']).json()['result']['reason']=='restart_uncertain'


def test_same_command_redelivery_uses_durable_result(setup):
    s=setup;enqueue(s);poll=s['client'].poll()
    first=s['agent'].process(poll['command'],poll['server_time'])
    repeated=s['agent'].process(poll['command'],poll['server_time'])
    assert first==repeated and len(s['executor'].calls)==1
    tampered={**poll['command'],'value':False}
    with pytest.raises(ValueError):s['agent'].process(tampered,poll['server_time'])


def test_send_error_not_replayed_even_if_observation_matches(setup):
    s=setup;command=enqueue(s)
    def uncertain(*args):
        s['executor'].calls.append(args);s['executor'].state['switch']=True
        raise OSError('SECRET_PAYLOAD_NOT_FOR_NETWORK')
    s['executor'].execute=uncertain;s['agent'].step()
    reply=result(s,command['id']).json()
    assert reply['status']=='uncertain' and reply['result']['reason']=='send_uncertain'
    assert 'SECRET_PAYLOAD' not in json.dumps(reply)
    s['agent'].step();assert len(s['executor'].calls)==1


@pytest.mark.parametrize('body',[{'code':'switch','value':True,'ttl_seconds':0}, {'code':'switch','value':True,'ttl_seconds':121},
    {'code':'temp_set','value':True,'ttl_seconds':30},{'code':'temp_set','value':99,'ttl_seconds':30},
    {'code':'switch','value':True,'ttl_seconds':30,'local_key':'DO_NOT_ECHO'}])
def test_rejects_invalid_and_untrusted_command_data(setup,body):
    response=setup['http'].post('/v1/devices/home-ac/commands',json={'request_id':str(uuid.uuid4()),**body},headers={'Authorization':'Bearer '+setup['operator']})
    assert response.status_code==422 and 'DO_NOT_ECHO' not in response.text


def test_credentials_are_only_hashes_in_database(setup):
    data=(setup['path']/'relay.sqlite3').read_bytes()
    assert setup['operator'].encode() not in data and setup['agent_token'].encode() not in data


def test_https_required_except_explicit_loopback_simulation():
    with pytest.raises(ValueError):RelayClient('http://example.com','x'*40,allow_loopback_http=True)
    with pytest.raises(ValueError):RelayClient('http://127.0.0.1:8090','x'*40)
    client=RelayClient('http://127.0.0.1:8090','x'*40,allow_loopback_http=True);client.close()
    with pytest.raises(ValueError):RelayClient('https://user:secret@example.com','x'*40)


def test_process_lease_prevents_second_local_agent(tmp_path):
    first=ProcessLock(tmp_path/'agent.lock');second=ProcessLock(tmp_path/'agent.lock')
    first.acquire()
    try:
        with pytest.raises(RuntimeError):second.acquire()
    finally:first.release()
    second.acquire();second.release()


def test_safe_observation_rejects_invalid_nested_state():
    assert safe_observation({'state':[],'timestamp':123}) is None
    assert safe_observation({'state':{},'timestamp':True}) is None


def test_shared_executor_uses_existing_lock_and_checks_expiry_after_connect(monkeypatch):
    clock=Clock();clock.value=100
    sends=[]
    class Socket:
        def sendall(self,data):sends.append(data)
    class Device:
        socket=Socket();closed=False
        def _get_socket(self,renew):clock.value=110;return True
        def set_multiple_values(self,data):self.socket.sendall(b'simulated');return {}
        def close(self):self.closed=True
    device=Device()
    class Controller:
        last_write=0;locks=0
        @contextmanager
        def operation(self):self.locks+=1;yield
        def device(self):return device
        def checked(self,reply):return reply
    controller=Controller()
    class Adapter:
        def capabilities(self):return {'switch':{}}
    adapter=Adapter();adapter.controller=controller
    class Devices:
        def adapter(self,id):return adapter
    executor=SharedLanExecutor(Devices(),clock=clock)
    monkeypatch.setattr(executor,'_dp',lambda code:'1')
    with pytest.raises(TimeoutError):executor.execute('home-ac','switch',True,105)
    assert controller.locks==1 and not sends and device.closed


def test_failed_reservation_never_reaches_executor(setup,monkeypatch):
    s=setup;enqueue(s);poll=s['client'].poll()
    def fail(envelope):raise OSError('disk unavailable')
    monkeypatch.setattr(s['journal'],'reserve',fail)
    with pytest.raises(OSError):s['agent'].process(poll['command'],poll['server_time'])
    assert not s['executor'].calls


def test_failed_result_commit_recovers_as_uncertain_without_another_attempt(setup,monkeypatch):
    s=setup;command=enqueue(s);poll=s['client'].poll()
    def fail(*args):raise OSError('disk unavailable')
    monkeypatch.setattr(s['journal'],'finish',fail)
    with pytest.raises(OSError):s['agent'].process(poll['command'],poll['server_time'])
    assert len(s['executor'].calls)==1
    restored=Journal(s['path']/'agent.sqlite3');restored.recover()
    agent=Agent(s['client'],restored,s['executor'],'home','bridge',['home-ac'],clock=s['clock'],monotonic=s['clock'])
    agent.step()
    assert len(s['executor'].calls)==1
    assert result(s,command['id']).json()['status']=='uncertain'


def test_read_must_match_value_and_be_newer_than_command(setup):
    s=setup;command=enqueue(s);s['client'].poll()
    headers={'Authorization':'Bearer '+s['agent_token']}
    for state,timestamp in [({'switch':False},1000),({'switch':True},999)]:
        response=s['http'].post('/v1/agent/commands/'+command['id']+'/result',headers=headers,json={
            'status':'confirmed','reason':'observed','observation':{'state':state,'timestamp':timestamp}})
        assert response.status_code==422


def test_wrong_scope_envelope_does_not_reserve_or_execute(setup):
    s=setup;enqueue(s);poll=s['client'].poll()
    with pytest.raises(ValueError):s['agent'].process({**poll['command'],'home_id':'other'},poll['server_time'])
    assert not s['executor'].calls and not s['journal'].outbox()


def test_revoked_agent_cannot_receive_new_commands(setup):
    s=setup;enqueue(s);s['store'].revoke(s['agent_token'])
    response=s['http'].post('/v1/agent/poll',headers={'Authorization':'Bearer '+s['agent_token']})
    assert response.status_code==401


def test_expiry_guard_at_socket_send(monkeypatch):
    from remote.local_executor import DeadlineSocket
    sends=[]
    class Socket:
        def sendall(self,data):sends.append(data)
    clock=Clock();clock.value=100
    socket=DeadlineSocket(Socket(),101,clock)
    clock.value=101
    with pytest.raises(TimeoutError):socket.sendall(b'simulated')
    assert not sends
