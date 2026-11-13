"""Agente de saída com executor injetável. Importar não acessa o aparelho."""
import math
import time
from typing import Protocol
from urllib.parse import urlsplit

import httpx

from remote.journal import Journal
from remote.protocol import Envelope, safe_observation, validate_value


class Executor(Protocol):
    def capabilities(self,device_id:str): ...
    def execute(self,device_id:str,code:str,value,deadline:float): ...
    def status(self,device_id:str): ...


class RelayClient:
    def __init__(self,url,token,*,allow_loopback_http=False,transport=None):
        parsed=urlsplit(url)
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError('invalid_relay_url')
        local=parsed.hostname in {'127.0.0.1','localhost','::1'}
        if parsed.scheme!='https' and not (allow_loopback_http and parsed.scheme=='http' and local):
            raise ValueError('https_required')
        self.http=httpx.Client(base_url=url.rstrip('/'),headers={'Authorization':'Bearer '+token},
                               verify=True,follow_redirects=False,trust_env=False,
                               timeout=httpx.Timeout(20,connect=5),transport=transport)

    def poll(self):
        reply=self.http.post('/v1/agent/poll',json={})
        reply.raise_for_status()
        return reply.json()

    def acknowledge(self,key,result):
        reply=self.http.post('/v1/agent/commands/'+key+'/result',json=result)
        reply.raise_for_status()

    def close(self):
        self.http.close()


class Agent:
    def __init__(self,client,journal:Journal,executor:Executor,home_id,agent_id,devices,
                 *,clock=time.time,monotonic=time.monotonic):
        self.client,self.journal,self.executor=client,journal,executor
        self.home_id,self.agent_id,self.devices=home_id,agent_id,set(devices)
        self.clock,self.monotonic=clock,monotonic

    def process(self,raw,server_time,request_elapsed=0):
        envelope=Envelope.model_validate(raw).model_dump(mode='json')
        if envelope['home_id']!=self.home_id or envelope['agent_id']!=self.agent_id or envelope['device_id'] not in self.devices:
            raise ValueError('command_scope_mismatch')
        key=envelope['command_id']
        fresh,result=self.journal.reserve(envelope)
        if not fresh:
            return key,result
        result={'status':'rejected','reason':'invalid_command','observation':None}
        try:
            validate_value(envelope['code'],envelope['value'])
            lifetime=envelope['expires_at']-envelope['issued_at']
            if not 0<lifetime<=120 or type(server_time) not in {int,float} or not math.isfinite(server_time) or envelope['issued_at']>server_time+5:
                raise ValueError('invalid_command')
            now=self.clock()
            if abs(server_time-now)>5:
                result={'status':'rejected','reason':'clock_skew','observation':None}
            else:
                remaining=min(envelope['expires_at']-now,envelope['expires_at']-server_time-max(0,request_elapsed))
                deadline=self.monotonic()+remaining
                if remaining<=0:
                    result={'status':'expired','reason':'expired','observation':None}
                elif envelope['code'] not in self.executor.capabilities(envelope['device_id']):
                    result={'status':'rejected','reason':'unmapped','observation':None}
                elif self.monotonic()>=deadline:
                    result={'status':'expired','reason':'expired','observation':None}
                else:
                    sent=False
                    try:
                        # O executor deve verificar deadline no ponto da escrita física.
                        self.executor.execute(envelope['device_id'],envelope['code'],envelope['value'],deadline)
                        sent=True
                    except Exception:
                        pass
                    try:
                        observation=safe_observation(self.executor.status(envelope['device_id']))
                    except Exception:
                        observation=None
                    confirmed=sent and observation is not None and observation['state'].get(envelope['code'])==envelope['value']
                    result={'status':'confirmed' if confirmed else 'uncertain',
                            'reason':'observed' if confirmed else 'send_uncertain' if not sent else 'read_failed' if observation is None else 'state_mismatch',
                            'observation':observation}
        except ValueError:
            pass
        # Se o disco falhar aqui, a reserva continua started e não autoriza reenvio.
        self.journal.finish(key,result)
        return key,result

    def flush(self):
        for key,result in self.journal.outbox():
            self.client.acknowledge(key,result)
            self.journal.acknowledged(key)

    def step(self):
        self.flush()
        started=self.monotonic()
        reply=self.client.poll()
        elapsed=self.monotonic()-started
        if reply.get('command') is not None:
            self.process(reply['command'],reply.get('server_time'),elapsed)
            self.flush()

    def run(self,stop):
        self.journal.recover()
        delay=1
        while not stop.is_set():
            try:
                self.step()
                delay=1
            except Exception:
                # Nada de tokens, payloads ou respostas brutas em logs.
                delay=min(30,delay*2)
            stop.wait(delay)
