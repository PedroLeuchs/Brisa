"""Ensaio HTTP real, efêmero, só loopback e aparelho inteiramente simulado."""
import json
from pathlib import Path
import socket
import tempfile
import threading
import time
import uuid

import httpx
import uvicorn

from remote.agent import Agent, RelayClient
from remote.broker import create_app
from remote.journal import Journal
from remote.storage import RelayStore


class SimulatedExecutor:
    def __init__(self):
        self.state={'switch':False,'temp_set':21}
        self.attempts=0

    def capabilities(self,device):
        return ['switch','temp_set']

    def execute(self,device,code,value,deadline):
        if time.monotonic()>=deadline:
            raise TimeoutError('expired')
        self.attempts+=1
        self.state[code]=value

    def status(self,device):
        return {'state':dict(self.state),'timestamp':time.time()}


def main():
    with tempfile.TemporaryDirectory(prefix='brisa-remote-simulation-') as temp:
        directory=Path(temp)
        store=RelayStore(directory/'relay.sqlite3')
        agent_token=store.provision_agent('simulation-home','simulation-agent',{'test-ac':['switch','temp_set']})
        operator_token=store.provision_operator('simulation-home','test-operator',['test-ac'])
        # Porta efêmera: nenhum processo/porta do painel doméstico é alterado.
        listener=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
        listener.bind(('127.0.0.1',0));listener.listen(16)
        url='http://127.0.0.1:'+str(listener.getsockname()[1])
        server=uvicorn.Server(uvicorn.Config(create_app(store),log_level='critical',access_log=False,proxy_headers=False))
        thread=threading.Thread(target=lambda:server.run(sockets=[listener]),daemon=True)
        thread.start()
        client=None
        try:
            limit=time.monotonic()+5
            while not server.started and thread.is_alive() and time.monotonic()<limit:
                time.sleep(0.02)
            if not server.started:
                raise RuntimeError('simulation_server_unavailable')
            executor=SimulatedExecutor()
            client=RelayClient(url,agent_token,allow_loopback_http=True)
            agent=Agent(client,Journal(directory/'agent.sqlite3'),executor,'simulation-home','simulation-agent',['test-ac'])
            with httpx.Client(base_url=url,headers={'Authorization':'Bearer '+operator_token},trust_env=False,timeout=5) as operator:
                created=operator.post('/v1/devices/test-ac/commands',json={
                    'request_id':str(uuid.uuid4()),'code':'temp_set','value':24,'ttl_seconds':10})
                created.raise_for_status()
                agent.step()
                reply=operator.get('/v1/commands/'+created.json()['id'])
                reply.raise_for_status()
                result=reply.json()
                if result['status']!='confirmed' or executor.attempts!=1:
                    raise RuntimeError('simulation_failed')
            print(json.dumps({'simulation_only':True,'network':'loopback_ephemeral',
                              'result':result['status'],'simulated_attempts':executor.attempts,
                              'real_device_commands':0,'shared_server_changed':False},indent=2))
        finally:
            if client:
                client.close()
            server.should_exit=True
            thread.join(timeout=5)
            listener.close()
    return 0


if __name__=='__main__':
    try:
        raise SystemExit(main())
    except Exception:
        print('Ensaio remoto não concluído. Nenhum dado de credencial será exibido.')
        raise SystemExit(1)
