"""Integração opcional no MESMO processo e DeviceService do painel doméstico."""
import time


class DeadlineSocket:
    def __init__(self,socket,deadline,clock):
        self.socket,self.deadline,self.clock=socket,deadline,clock

    def sendall(self,data,*args,**kwargs):
        if self.clock()>=self.deadline:
            raise TimeoutError('command_expired_before_send')
        return self.socket.sendall(data,*args,**kwargs)

    def __getattr__(self,name):
        return getattr(self.socket,name)


class SharedLanExecutor:
    """Não cria outro controlador, lock, agendador ou conexão persistente."""
    def __init__(self,devices,*,clock=time.monotonic,sleep=time.sleep):
        self.devices,self.clock,self.sleep=devices,clock,sleep

    def capabilities(self,device_id):
        return self.devices.adapter(device_id).capabilities()

    def status(self,device_id):
        return self.devices.status(device_id)

    def execute(self,device_id,code,value,deadline):
        from controller import validate
        validate(code,value)
        adapter=self.devices.adapter(device_id)
        if code not in adapter.capabilities():
            raise ValueError('unmapped')
        controller=adapter.controller
        with controller.operation():
            pause=max(0,1.1-(self.clock()-controller.last_write))
            if self.clock()+pause>=deadline:
                raise TimeoutError('expired')
            if pause:
                self.sleep(pause)
            device=controller.device()
            try:
                # Negocia a sessão antes do último teste de validade. A expiração
                # não é ignorada enquanto o socket conecta/negocia.
                if device._get_socket(False) is not True or self.clock()>=deadline:
                    raise TimeoutError('connection_unavailable_or_expired')
                device.socket=DeadlineSocket(device.socket,deadline,self.clock)
                controller.last_write=self.clock()
                controller.checked(device.set_multiple_values({
                    # IDs são lidos somente do arquivo doméstico; nunca do relay.
                    self._dp(code):value
                }))
            finally:
                device.close()

    @staticmethod
    def _dp(code):
        from controller import mapping
        ids=mapping()
        if code not in ids:
            raise ValueError('unmapped')
        return ids[code]
