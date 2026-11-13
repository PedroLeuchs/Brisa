"""Registro opcional do agente na API doméstica; não é ativado por importação."""
from dataclasses import dataclass, field
from pathlib import Path
import threading

from remote.agent import Agent, RelayClient
from remote.journal import Journal
from remote.local_executor import SharedLanExecutor


@dataclass
class AgentConfig:
    relay_url:str
    token:str=field(repr=False)
    home_id:str='home'
    agent_id:str='bridge-1'
    devices:tuple[str,...]=('home-ac',)
    journal_path:Path=Path('remote/runtime/agent.sqlite3')
    allow_loopback_http:bool=False


class ProcessLock:
    def __init__(self,path):
        self.path=Path(path)
        self.file=None

    def acquire(self):
        self.path.parent.mkdir(parents=True,exist_ok=True)
        self.file=self.path.open('a+b')
        if self.path.stat().st_size==0:
            self.file.write(b'0');self.file.flush()
        self.file.seek(0)
        try:
            import os
            if os.name=='nt':
                import msvcrt
                msvcrt.locking(self.file.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(self.file.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        except Exception:
            self.file.close();self.file=None
            raise RuntimeError('Outro agente já usa este diário.') from None

    def release(self):
        if self.file:
            self.file.close();self.file=None


def attach_agent(app,devices,config:AgentConfig):
    """Chamar explicitamente na composição futura, após pareamento e HTTPS.

    Recebe o DeviceService JÁ existente: rotinas, UI local e relay usam o mesmo
    controlador e exclusão mútua. Não importar outro app nem iniciar outro worker.
    """
    if getattr(app.state,'brisa_relay_registered',False):
        raise RuntimeError('Agente já registrado.')
    app.state.brisa_relay_registered=True
    stop=threading.Event()
    runtime={}

    def start():
        lease=ProcessLock(str(config.journal_path)+'.lock')
        lease.acquire()
        try:
            client=RelayClient(config.relay_url,config.token,allow_loopback_http=config.allow_loopback_http)
            agent=Agent(client,Journal(config.journal_path),SharedLanExecutor(devices),
                        config.home_id,config.agent_id,config.devices)
        except Exception:
            lease.release()
            raise RuntimeError('Configuração do agente inválida.') from None
        def run():
            try:
                agent.run(stop)
            finally:
                client.close();lease.release()
        runtime['thread']=threading.Thread(target=run,name='brisa-relay-agent',daemon=True)
        runtime['thread'].start()

    def shutdown():
        stop.set()
        thread=runtime.get('thread')
        if thread:
            thread.join(timeout=30)

    app.add_event_handler('startup',start)
    app.add_event_handler('shutdown',shutdown)
