import {useEffect,useRef,useState} from 'react';
import type {FormEvent} from 'react';
import type {ConsumptionApi,ConsumptionDashboard} from './consumptionTypes';
import './consumption.css';
import './consumptionCharts.css';
import './consumptionDashboard.css';
import {ConsumptionTimeline} from './ConsumptionTimeline';
import {ConsumptionBars} from './ConsumptionBars';

function today(){return new Intl.DateTimeFormat('en-CA',{timeZone:'America/Sao_Paulo',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());}
function before(day:string,offset:number){const value=new Date(day+'T12:00:00Z');value.setUTCDate(value.getUTCDate()-offset);return value.toISOString().slice(0,10);}
function duration(seconds:number){const minutes=Math.floor(seconds/60);return `${Math.floor(minutes/60)}h ${String(minutes%60).padStart(2,'0')}min`;}
const number=(value:number,digits=2)=>value.toLocaleString('pt-BR',{minimumFractionDigits:digits,maximumFractionDigits:digits});
const stamp=(value:number)=>new Date(value*1000).toLocaleString('pt-BR',{timeZone:'America/Sao_Paulo'});

export function ConsumptionModal({api,deviceId,deviceName,onClose}:{api:ConsumptionApi;deviceId:string;deviceName:string;onClose:()=>void}){
  const dialog=useRef<HTMLDialogElement>(null),sequence=useRef(0),alive=useRef(true);
  const [period,setPeriod]=useState('1'),[range,setRange]=useState(()=>({start:today(),end:today()}));
  const [data,setData]=useState<ConsumptionDashboard|null>(null),[loading,setLoading]=useState(true);
  const [message,setMessage]=useState(''),[saving,setSaving]=useState(false);
  const [watts,setWatts]=useState(''),[tariff,setTariff]=useState('');
  async function load(){
    const request=++sequence.current;setLoading(true);setMessage('');
    try{const result=await api.consumption(deviceId,range.start,range.end);if(!alive.current||request!==sequence.current)return;setData(result);setWatts(result.settings.reference_watts===null?'':String(result.settings.reference_watts));setTariff(String(result.settings.tariff_per_kwh));}
    catch(error){if(alive.current&&request===sequence.current){setData(null);setMessage(error instanceof Error?error.message:'Não foi possível carregar o consumo.');}}
    finally{if(alive.current&&request===sequence.current)setLoading(false);}
  }
  useEffect(()=>{alive.current=true;const opener=document.activeElement;const element=dialog.current;if(element&&!element.open){if(typeof element.showModal==='function')element.showModal();else element.setAttribute('open','');}return()=>{alive.current=false;sequence.current++;if(element?.open&&typeof element.close==='function')element.close();if(opener instanceof HTMLElement&&opener.isConnected)opener.focus();};},[]);
  useEffect(()=>{void load();return()=>{sequence.current++;};},[deviceId,range.start,range.end]);
  function selectPeriod(value:string){setPeriod(value);if(value!=='custom'){const end=today();setRange({start:before(end,Number(value)-1),end});}}
  async function save(event:FormEvent){
    event.preventDefault();setSaving(true);setMessage('');
    try{await api.saveConsumptionSettings(deviceId,{reference_watts:watts.trim()===''?null:Number(watts),tariff_per_kwh:Number(tariff)});if(alive.current)await load();}
    catch(error){if(alive.current)setMessage(error instanceof Error?error.message:'Não foi possível salvar as referências.');}
    finally{if(alive.current)setSaving(false);}
  }
  return <dialog ref={dialog} className="consumption-modal consumption-dashboard card" aria-labelledby="consumption-title" onCancel={event=>{event.preventDefault();onClose();}}>
    <div className="modal-heading"><button className="consumption-back quiet" aria-label="Voltar ao controle" onClick={onClose}><span aria-hidden="true">←</span></button><div><p className="eyebrow">USO DO SEU AR-CONDICIONADO</p><h2 id="consumption-title">Consumo</h2><p className="muted">{deviceName}</p></div><button className="consumption-close quiet" aria-label="Fechar consumo" onClick={onClose}>✕</button></div>
    <div className="consumption-period"><label>Período<select aria-label="Período" value={period} onChange={event=>selectPeriod(event.target.value)}><option value="1">Hoje</option><option value="7">Últimos 7 dias</option><option value="30">Últimos 30 dias</option><option value="custom">Escolher datas</option></select></label>
      {period==='custom'&&<><label>De<input aria-label="Data inicial" type="date" value={range.start} max={range.end} onChange={event=>setRange({...range,start:event.target.value})}/></label><label>Até<input aria-label="Data final" type="date" value={range.end} min={range.start} max={today()} onChange={event=>setRange({...range,end:event.target.value})}/></label></>}
      <button className="quiet" onClick={()=>void load()} disabled={loading||saving}>Atualizar dados</button></div>
    {loading&&<p role="status">Carregando consumo…</p>}
    {data&&!loading&&<>
      {range.start===range.end&&data.timeline?<ConsumptionTimeline key={`${data.timeline.date}-${data.timeline.end}`} timeline={data.timeline}/>:range.start!==range.end?<ConsumptionBars key={`${range.start}-${range.end}`} days={data.days}/>:<p className="hint">Aguardando os dados diários para desenhar a linha de estado.</p>}
      <p className="consumption-source">Tempo de uso observado · {data.measured_energy_available?'Medição disponível':'Sem medição elétrica comprovada'}</p>
      <div className="consumption-metrics">
        <article><span>Ligado no período observado</span><strong>{duration(data.totals.on_seconds)}</strong><small>Estado ligado, não tempo do compressor</small></article>
        <article><span>Energia estimada</span><strong>{data.totals.estimated_kwh===null?'Indisponível':`${number(data.totals.estimated_kwh,3)} kWh`}</strong><small>{data.settings.reference_watts===null?'Informe a potência elétrica de referência':'Estimativa pela potência de referência'}</small></article>
        <article><span>Custo estimado</span><strong>{data.totals.estimated_cost===null?'Indisponível':data.totals.estimated_cost.toLocaleString('pt-BR',{style:'currency',currency:'BRL'})}</strong><small>Sem créditos solares</small></article>
        <article><span>Cobertura do período</span><strong>{number(data.totals.coverage_percent,1)}%</strong><small>{duration(data.totals.unknown_seconds)} sem observação</small></article>
      </div>
      <div className="consumption-coverage"><p>{data.collection_started_at===null?'A coleta ainda não começou.':'Coleta iniciada em '+stamp(data.collection_started_at)+'.'} {data.last_observation?'Última leitura: '+stamp(data.last_observation.at)+'.':'Aguardando a primeira leitura.'}</p>
        <p>{data.collector.running?'O servidor coleta a cada 60 segundos, mesmo com esta tela fechada.':'O coletor está parado; o histórico existente continua disponível.'}</p>
        {data.collector.status==='offline'&&<p role="status">Aparelho sem leitura válida. O intervalo ficará sem observação.</p>}
        {data.collector.status==='storage_error'&&<p className="notice" role="status">Falha ao guardar leituras. O servidor tentará novamente; intervalos perdidos não serão preenchidos.</p>}
      </div>
      <section aria-label="Uso por dia" className="consumption-days"><h3>Tempo observado por dia</h3>{data.totals.on_seconds+data.totals.off_seconds===0&&<p className="hint">Sem intervalos observados neste período. Não há dados históricos anteriores à coleta.</p>}
        <div className="consumption-table"><table><thead><tr><th>Dia</th><th>Ligado</th><th>Desligado</th><th>Sem observação</th><th>Cobertura</th></tr></thead><tbody>{data.days.map(day=><tr key={day.date}><th scope="row">{new Date(day.date+'T12:00:00Z').toLocaleDateString('pt-BR',{timeZone:'America/Sao_Paulo'})}</th><td>{duration(day.on_seconds)}</td><td>{duration(day.off_seconds)}</td><td>{duration(day.unknown_seconds)}</td><td>{number(day.coverage_percent,1)}%</td></tr>)}</tbody></table></div>
      </section>
      <details className="consumption-reference"><summary>Referências para estimar energia e custo</summary><form onSubmit={save}>
        <p className="hint">Informe potência elétrica de entrada em watts, da etiqueta ou documentação. Capacidade em BTU/h não é potência elétrica. Sem referência, kWh e custo permanecem indisponíveis.</p>
        <div className="consumption-reference-fields"><label>Potência elétrica de referência (W)<input aria-label="Potência elétrica de referência (W)" type="number" min="0.001" max="100000" step="any" placeholder="Não informada" value={watts} onChange={event=>setWatts(event.target.value)}/></label><label>Tarifa de referência (R$/kWh)<input aria-label="Tarifa de referência (R$/kWh)" type="number" min="0" max="100" step="0.000001" required value={tariff} onChange={event=>setTariff(event.target.value)}/></label></div>
        <p className="hint">{data.settings.tariff_source}. R$ 1,056961/kWh = energia + uso do sistema + bandeira amarela. É referência da conta, não tarifa atual garantida ou preço por horário; tributos não são somados novamente.</p>
        <button className="primary" disabled={saving} type="submit">{saving?'Salvando…':'Salvar referências'}</button>
      </form></details>
      <p className="hint">{data.method}</p><p className="hint">{data.estimate_note} Alterar as referências recalcula a estimativa de todo o período selecionado.</p><p className="hint">Leituras detalhadas são mantidas por 90 dias; intervalos de uso, por 730 dias. Os horários seguem Brasília.</p>
    </>}
    {message&&<p className="notice" role="status">{message}</p>}
  </dialog>;
}
