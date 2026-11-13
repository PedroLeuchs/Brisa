import {afterEach,beforeEach,describe,expect,it,vi} from 'vitest';
import {ControllerStore} from './controller';
import {ApiError,HttpApi} from './api';
import type {ControllerApi,DeviceInfo,DeviceStatus} from './types';

const device:DeviceInfo={id:'home-ac',name:'Clima da casa',transport:'local',capabilities:{switch:{type:'bool',values:null}}};
const status:DeviceStatus={device_id:'home-ac',state:{switch:false,temp_set:21},available:['switch','temp_set'],timestamp:1700000000};
function fixture(){
  const api={session:vi.fn().mockResolvedValue(undefined),login:vi.fn().mockResolvedValue(undefined),logout:vi.fn().mockResolvedValue(undefined),devices:vi.fn().mockResolvedValue([device]),status:vi.fn().mockResolvedValue(status),command:vi.fn().mockResolvedValue(undefined),dispose:vi.fn()} satisfies ControllerApi;
  const store=new ControllerStore(api);stores.push(store);return {api,store};
}
const stores:ControllerStore[]=[];
beforeEach(()=>{vi.useFakeTimers();vi.setSystemTime(new Date('2026-10-23T20:00:00Z'));});
afterEach(()=>{for(const store of stores.splice(0))store.dispose();vi.useRealTimers();vi.unstubAllGlobals();});

describe('controlador da interface',()=>{
  it('mantém verificação durante queda do servidor e recupera sessão sem pedir senha',async()=>{
    const {api,store}=fixture();api.session.mockRejectedValueOnce(new ApiError('Servidor indisponível',503));
    await store.start();expect(store.snapshot().auth).toBe('checking');
    await vi.advanceTimersByTimeAsync(5000);
    expect(store.snapshot().auth).toBe('signedin');expect(api.login).not.toHaveBeenCalled();
  });
  it('encaminha lembrar dispositivo e mantém acesso após login com aparelho offline',async()=>{
    const {api,store}=fixture();api.status.mockRejectedValueOnce(new ApiError('offline',503));
    await store.login('test-only',true);
    expect(api.login).toHaveBeenCalledWith('test-only',true);expect(store.snapshot().auth).toBe('signedin');
  });
  it('recupera leitura offline sem perder a sessão e sem reiniciar',async()=>{
    const {api,store}=fixture();api.status.mockRejectedValueOnce(new ApiError('offline',503));
    await store.start();expect(store.snapshot().auth).toBe('signedin');expect(store.snapshot().connection).toBe('offline');
    await vi.advanceTimersByTimeAsync(2000);
    expect(store.snapshot().connection).toBe('online');expect(store.snapshot().phase).toBe('idle');expect(api.status).toHaveBeenCalledTimes(2);
  });
  it('não simula sucesso enquanto aguarda confirmação de um comando',async()=>{
    const {api,store}=fixture();await store.start();
    let resolve!:()=>void;api.command.mockImplementationOnce(()=>new Promise<void>(done=>{resolve=done;}));
    const sending=store.send('switch',true);await Promise.resolve();
    expect(store.snapshot().phase).toBe('sending');expect(store.snapshot().data?.state.switch).toBe(false);
    await store.send('switch',true);expect(api.command).toHaveBeenCalledTimes(1);
    resolve();await vi.advanceTimersByTimeAsync(1200);await sending;
    expect(store.snapshot().data?.state.switch).toBe(false);expect(store.snapshot().message).toContain('ainda não confirmou');expect(store.snapshot().phase).toBe('idle');
  });
  it('confirma por leitura mesmo após envio incerto e nunca repete a escrita',async()=>{
    const {api,store}=fixture();await store.start();api.command.mockRejectedValueOnce(new ApiError('timeout'));
    api.status.mockResolvedValueOnce({...status,state:{...status.state,switch:true}});
    const sending=store.send('switch',true);await vi.advanceTimersByTimeAsync(1200);await sending;
    expect(api.command).toHaveBeenCalledTimes(1);expect(store.snapshot().data?.state.switch).toBe(true);expect(store.snapshot().phase).toBe('idle');expect(store.snapshot().message).toContain('Envio sem confirmação');
  });
  it('sai para o login em sessão expirada, sem tentar comandar novamente',async()=>{
    const {api,store}=fixture();await store.start();api.command.mockRejectedValueOnce(new ApiError('sessão expirada',401));
    const sending=store.send('switch',true);await vi.advanceTimersByTimeAsync(1200);await sending;
    expect(store.snapshot().auth).toBe('signedout');expect(store.snapshot().data).toBeNull();expect(api.status).toHaveBeenCalledTimes(1);
  });
  it('descarte cancela pedidos e ignora respostas atrasadas',async()=>{
    const {api,store}=fixture();let done!:(value:DeviceStatus)=>void;api.status.mockImplementationOnce(()=>new Promise<DeviceStatus>(resolve=>{done=resolve;}));
    const starting=store.start();await vi.advanceTimersByTimeAsync(0);store.dispose();
    const listener=vi.fn();store.subscribe(listener);done(status);await starting;
    expect(listener).not.toHaveBeenCalled();expect(api.dispose).toHaveBeenCalled();
  });
  it('não envia função ausente do estado do aparelho',async()=>{
    const {api,store}=fixture();await store.start();await store.send('mode_eco',true);expect(api.command).not.toHaveBeenCalled();
  });
  it('consulta periódica não interrompe um gesto de ajuste',async()=>{
    const {api,store}=fixture();await store.start();store.setInteraction(true);
    await vi.advanceTimersByTimeAsync(16000);await store.refresh();expect(api.status).toHaveBeenCalledTimes(1);
    store.setInteraction(false);await vi.advanceTimersByTimeAsync(15000);expect(api.status).toHaveBeenCalledTimes(2);
  });
  it('mantém mensagem de senha incorreta no login',async()=>{
    const {api,store}=fixture();api.session.mockRejectedValueOnce(new ApiError('Entre',401));await store.start();
    api.login.mockRejectedValueOnce(new ApiError('Senha incorreta.',401));await store.login('test-only');
    expect(store.snapshot().auth).toBe('signedout');expect(store.snapshot().message).toBe('Senha incorreta.');
  });
});

it('HTTP interrompe um pedido pendurado e não guarda a senha em storage',async()=>{
  const fetcher=vi.fn((_url:unknown,options:RequestInit)=>new Promise((_resolve,reject)=>{
    options.signal?.addEventListener('abort',()=>reject(new DOMException('Aborted','AbortError')));
  }));
  vi.stubGlobal('fetch',fetcher);const api=new HttpApi();
  const request=api.status('home-ac');const assertion=expect(request).rejects.toThrow('demorou demais');
  await vi.advanceTimersByTimeAsync(20000);await assertion;api.dispose();
  expect(localStorage.length).toBe(0);expect(sessionStorage.length).toBe(0);
});
