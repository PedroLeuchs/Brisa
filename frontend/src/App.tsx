import {useEffect,useState,useSyncExternalStore} from 'react';
import type {FormEvent} from 'react';
import {HttpApi} from './api';
import {ControllerStore} from './controller';
import type {FunctionCode} from './types';
import {TemperatureControl} from './TemperatureControl';
import {AmbientTemperature} from './AmbientTemperature';
import {AutomationModal} from './AutomationModal';
import {ClimateOptions,modes,fans} from './ClimateOptions';
import type {OptionSection} from './ClimateOptions';
import {ControlSheet} from './ControlSheet';
import {ControlIcon,PowerIcon} from './ControlIcon';
import {ConsumptionModal} from './ConsumptionModal';
import {climatePresentation} from './climateTheme';

interface InstallEvent extends Event {prompt():Promise<void>;userChoice:Promise<{outcome:string}>}

export function App({store:provided}:{store?:ControllerStore}){
  const [store]=useState(()=>provided??new ControllerStore(new HttpApi()));
  const [automationApi]=useState(()=>new HttpApi());
  const view=useSyncExternalStore(store.subscribe,store.snapshot);
  const [password,setPassword]=useState('');
  const [remember,setRemember]=useState(true);
  const [install,setInstall]=useState<InstallEvent|null>(null);
  const [remoteMode,setRemoteMode]=useState(false);
  const [automationOpen,setAutomationOpen]=useState(false);
  const [consumptionOpen,setConsumptionOpen]=useState(false);
  const [options,setOptions]=useState<Exclude<OptionSection,'all'>|null>(null);
  const [mobile,setMobile]=useState(()=>window.matchMedia?.('(max-width: 700px)').matches??false);
  useEffect(()=>{
    const query=window.matchMedia?.('(max-width: 700px)');
    if(!query)return;
    const change=()=>setMobile(query.matches);change();query.addEventListener('change',change);
    return()=>query.removeEventListener('change',change);
  },[]);
  useEffect(()=>{
    void store.start();
    const reconnect=()=>{if(store.snapshot().auth==='signedin')void store.refresh();else void store.start();};
    const visible=()=>{if(!document.hidden)reconnect();};
    const offer=(event:Event)=>{event.preventDefault();setInstall(event as InstallEvent);};
    window.addEventListener('online',reconnect);document.addEventListener('visibilitychange',visible);
    window.addEventListener('beforeinstallprompt',offer);
    return()=>{window.removeEventListener('online',reconnect);document.removeEventListener('visibilitychange',visible);window.removeEventListener('beforeinstallprompt',offer);store.dispose();automationApi.dispose();};
  },[store,automationApi]);
  const signed=view.auth==='signedin', busy=view.phase!=='idle';
  const remote=mobile||remoteMode;
  const current=view.devices.find(device=>device.id===view.selected);
  const values=view.data?.state??{};
  const can=(code:FunctionCode)=>signed&&!busy&&view.connection==='online'&&view.data?.available.includes(code)&&values[code]!==undefined;
  const temperature=typeof values.temp_set==='number'?values.temp_set:null;
  const power=values.switch;
  const presentation=climatePresentation(view.connection,view.phase,power,values.mode);
  const bound=current?.capabilities.temp_set?.values;
  const min=typeof bound?.[0]==='number'?bound[0]:16,max=typeof bound?.[1]==='number'?bound[1]:31;
  const step=current?.capabilities.temp_set?.step??1;
  const signIn=async(event:FormEvent)=>{event.preventDefault();const entered=password;setPassword('');await store.login(entered,remember);};
  const connectionText=view.connection==='online'?'● Conectado na rede':view.connection==='offline'?'○ Reconectando…':'◌ Conectando…';
  const mainClass=[signed&&remote?'remote-shell':'',signed?`app-theme climate-theme-${presentation.theme}`:''].filter(Boolean).join(' ');
  return <main className={mainClass||undefined}>
    <header><a className="brand" href="/" aria-label="Brisa, início"><span className="brand-icon" aria-hidden="true">≈</span> brisa<span className="local">SEU CLIMA, POR PERTO</span></a>
      <div className="header-actions">{signed&&<button className="quiet" onClick={()=>setConsumptionOpen(true)}>Consumo</button>}{signed&&!remote&&<button className="quiet" onClick={()=>setAutomationOpen(true)}>Automações</button>}{signed&&!mobile&&<button className="quiet" aria-pressed={remoteMode} onClick={()=>setRemoteMode(!remoteMode)}>{remoteMode?'Voltar ao painel':'Modo controle'}</button>}{install&&<button className="quiet" onClick={async()=>{await install.prompt();await install.userChoice;setInstall(null);}}>Instalar aplicativo</button>}{signed&&<button className="quiet" disabled={busy} onClick={()=>void store.logout()}>Sair</button>}</div>
    </header>
    {view.auth==='checking'?<section className="card login"><p className="eyebrow">BEM-VINDO DE VOLTA</p><h1>Preparando<br/>seu espaço.</h1><p className="muted" role="status">Conectando ao controlador…</p><button className="quiet" onClick={()=>void store.start()}>Tentar novamente</button></section>:
      !signed?<section className="login card"><p className="eyebrow">SEU CLIMA, NO SEU ESPAÇO</p><h1>Conforto a<br/>um toque.</h1><p className="muted">Conecte-se ao controle do seu ar-condicionado.</p>
        <form onSubmit={signIn}><label htmlFor="password">Senha do controlador</label><input id="password" type="password" autoComplete="current-password" required maxLength={256} value={password} onChange={event=>setPassword(event.target.value)} placeholder="Sua senha de acesso" disabled={busy}/><label><input type="checkbox" checked={remember} onChange={event=>setRemember(event.target.checked)} disabled={busy}/> Lembrar deste dispositivo por 30 dias</label><p className="hint">Desmarque em computadores compartilhados. Sem esta opção, o acesso dura 12 horas. Sair encerra o acesso neste dispositivo.</p><button className="primary" type="submit" disabled={busy}>{busy?'Entrando…':'Entrar'}<span aria-hidden="true">↗</span></button></form>
        <p className="hint">Use a senha criada na configuração deste controlador.</p></section>:
      <section aria-label="Controle do ambiente" data-climate-state={presentation.theme} className={remote?'control-layout remote-view':'control-layout dashboard-view'}>
        <div className="heading"><div><p className="eyebrow">DO JEITO QUE VOCÊ GOSTA</p><h1>Seu ambiente.</h1></div><span className={`badge ${view.connection}`} role="status">{connectionText}</span></div>
        {view.devices.length>1&&<label className="device-selector">Ambiente<select value={view.selected} disabled={busy} onChange={event=>void store.select(event.target.value)}>{view.devices.map(device=><option key={device.id} value={device.id}>{device.name}</option>)}</select></label>}
        <div className="layout">
          <section className="card climate" aria-label="Temperatura e energia"><div className="card-top"><div><p className="eyebrow">AR-CONDICIONADO</p><h2>{current?.name??'Clima da casa'}</h2>{remote&&<span className="remote-connection">{connectionText}</span>}<span className="climate-state">{presentation.label}</span></div><button className="power" disabled={!can('switch')||typeof power!=='boolean'} aria-label={power===true?'Desligar ar':'Ligar ar'} aria-pressed={power===true} onClick={()=>void store.send('switch',power!==true)}><PowerIcon/></button></div>
            <AmbientTemperature reading={view.data?.telemetry?.ambient_temperature} online={view.connection==='online'}/>
            <TemperatureControl value={temperature} min={min} max={max} step={step} disabled={!can('temp_set')} busy={busy}
              online={view.connection==='online'} power={typeof power==='boolean'?power:undefined}
              onCommit={value=>void store.send('temp_set',value)} onInteraction={store.setInteraction} variant={remote?'remote':'panel'}/>
            <p className="hint">{view.data?`${view.connection==='online'?'Lido':'Última leitura'} às ${new Date(view.data.timestamp*1000).toLocaleTimeString('pt-BR')}`:'O estado é consultado diretamente no aparelho.'}</p>
            <div className="read-status" role="status">{view.phase==='sending'?'Enviando seu ajuste…':view.phase==='confirming'?'Confirmando com o aparelho…':view.phase==='reading'?'Atualizando estado…':view.connection==='online'?'Estado recebido do aparelho':'A reconexão acontece automaticamente'}</div>
          </section>
          <section className="card settings" hidden={remote}><p className="eyebrow">AJUSTE O CONFORTO</p><h2>Um clima para cada momento</h2>
            <ClimateOptions section="all" values={values} device={current} can={can} onSend={(code,value)=>void store.send(code,value)}/>
          </section>
        </div>
        {remote&&<nav className="control-nav" aria-label="Opções do controle">
          <button aria-expanded={options==='mode'} onClick={()=>setOptions('mode')}><ControlIcon kind="mode"/><span>Modo</span><small>{modes.find(([code])=>code===values.mode)?.[1]??'—'}</small></button>
          <button aria-expanded={options==='fan'} onClick={()=>setOptions('fan')}><ControlIcon kind="fan"/><span>Velocidade</span><small>{fans.find(([code])=>code===values.fan_speed_enum)?.[1]??'—'}</small></button>
          <button aria-expanded={options==='functions'} onClick={()=>setOptions('functions')}><ControlIcon kind="functions"/><span>Funções</span><small>Ajustes extras</small></button>
          <button onClick={()=>setAutomationOpen(true)}><ControlIcon kind="timer"/><span>Timer</span><small>Horários</small></button>
        </nav>}
        <ControlSheet open={remote&&options!==null} title={options==='mode'?'Modo de operação':options==='fan'?'Velocidade do vento':'Funções'} onClose={()=>setOptions(null)}>
          <ClimateOptions section={options??'functions'} values={values} device={current} can={can} onSend={(code,value)=>{void store.send(code,value);if(options!=='functions')setOptions(null);}}/>
        </ControlSheet>
        <div className="bottom-row"><span>⌁ {current?.transport==='tuya_cloud'?'Conexão Tuya Cloud':current?.transport==='remote'?'Conexão segura com sua casa':'Conexão direta pela sua rede'}</span><button className="quiet" disabled={busy} onClick={()=>void store.refresh()}>Atualizar estado ↻</button></div>
        <details className="diagnostics"><summary>Informações da conexão</summary><p>O estado é confirmado por uma leitura do aparelho. Durante uma queda, os controles ficam indisponíveis e a última leitura permanece identificada.</p><p>{view.data?.available.length??0} funções disponíveis · {current?.name??'Aparelho'}</p></details>
      </section>}
    {view.message&&<p className="notice" role="status" aria-live="polite">{view.message}</p>}
    {signed&&automationOpen&&view.devices.length>0&&<AutomationModal api={automationApi} devices={view.devices} onClose={()=>setAutomationOpen(false)}/>}
    {signed&&consumptionOpen&&current&&<ConsumptionModal key={current.id} api={automationApi} deviceId={current.id} deviceName={current.name} onClose={()=>setConsumptionOpen(false)}/>}
    <footer>brisa<span>Um pouco mais de conforto. Tudo por perto.</span></footer>
  </main>;
}
