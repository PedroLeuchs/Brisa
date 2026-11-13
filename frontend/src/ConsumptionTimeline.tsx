import {useEffect,useId,useRef,useState} from 'react';
import type {ConsumptionTimelineData,ConsumptionSegment,ConsumptionTransition} from './consumptionTypes';

const names={on:'Ligado',off:'Desligado',unknown:'Sem observação'};
const clock=(value:number)=>new Date(value*1000).toLocaleTimeString('pt-BR',{timeZone:'America/Sao_Paulo',hour:'2-digit',minute:'2-digit',second:'2-digit'});
function length(seconds:number){const value=Math.round(seconds);const hours=Math.floor(value/3600),minutes=Math.floor(value%3600/60);return `${hours?hours+'h ':''}${minutes}min ${value%60}s`;}
function description(segment:ConsumptionSegment){return `${names[segment.state]} · ${clock(segment.start)} a ${clock(segment.end)} · ${length(segment.end-segment.start)}`;}
function changeDescription(change:ConsumptionTransition){return `Mudança para ${names[change.to].toLowerCase()} observada às ${clock(change.end)}, entre ${clock(change.start)} e ${clock(change.end)}`;}

export function ConsumptionTimeline({timeline}:{timeline:ConsumptionTimelineData}){
  const heading=useId(),[selected,setSelected]=useState('');
  const graphic=useRef<SVGSVGElement>(null),[width,setWidth]=useState(960);
  useEffect(()=>{const element=graphic.current;if(!element)return;const resize=()=>{const next=element.getBoundingClientRect().width;if(next>0)setWidth(Math.max(280,next));};resize();if(typeof ResizeObserver==='undefined')return;const observer=new ResizeObserver(resize);observer.observe(element);return()=>observer.disconnect();},[]);
  const left=width<500?66:85,right=width-18,track=right-left,total=timeline.end-timeline.start;
  const x=(timestamp:number)=>left+(timestamp-timeline.start)/total*track;
  const y=(state:'on'|'off')=>state==='on'?48:145;
  const ticks:number[]=[],step=Math.max(1,Math.ceil(total/3600/(width<500?3:5)))*3600;
  for(let offset=0;offset<total;offset+=step){if(offset===0||total-offset>step*.65)ticks.push(timeline.start+offset);}
  const changes=timeline.transitions??[];
  const onSeconds=timeline.segments.reduce((sum,item)=>sum+(item.state==='on'?item.end-item.start:0),0);
  const active=selected.startsWith('s-')?timeline.segments[Number(selected.slice(2))]:null;
  const change=selected.startsWith('t-')?changes[Number(selected.slice(2))]:null;
  function point(event:React.PointerEvent<SVGSVGElement>){
    const box=event.currentTarget.getBoundingClientRect();if(!box.width)return;
    const position=(event.clientX-box.left)/box.width*width;
    const at=timeline.start+Math.max(0,Math.min(1,(position-left)/track))*total;
    const transition=changes.findIndex(item=>at>=item.start&&at<=item.end);
    if(transition>=0){setSelected('t-'+transition);return;}
    const index=timeline.segments.findIndex(item=>at>=item.start&&(at<item.end||at===timeline.end&&item.end===timeline.end));
    if(index>=0)setSelected('s-'+index);
  }
  function key(event:React.KeyboardEvent,selection:string){if(event.key==='Enter'||event.key===' '){event.preventDefault();setSelected(selection);}}
  return <section className="consumption-timeline" aria-labelledby={heading}>
    <div className="timeline-heading"><div><p className="eyebrow">ESTADO DO APARELHO · POR HORÁRIO</p><h3 id={heading}>Ligado e desligado</h3><span className="chart-period-label">{timeline.ends_at_now?'Hoje, até agora':new Date(timeline.date+'T12:00:00Z').toLocaleDateString('pt-BR',{timeZone:'America/Sao_Paulo'})}</span></div><div className="chart-reading"><strong>{(onSeconds/3600).toLocaleString('pt-BR',{maximumFractionDigits:2})}<small>h</small></strong><span>ligado observado</span></div></div>
    <div className="state-chart-legend"><span><i className="state-solid"/>Estado observado</span><span><i className="state-dashed"/>Mudança entre leituras</span><span>Lacuna = linha interrompida</span></div>
    <svg ref={graphic} className="state-chart" viewBox={`0 0 ${width} 222`} role="group" aria-label="Gráfico diário de estado em degraus" onPointerDown={point} onPointerMove={event=>{if(event.pointerType==='mouse')point(event);}}>
      {(['on','off'] as const).map(state=><g key={state}><line x1={left} x2={right} y1={y(state)} y2={y(state)} className="chart-grid"/><text x={left-10} y={y(state)+4} textAnchor="end" className="chart-axis">{names[state]}</text></g>)}
      {ticks.map(at=><g key={at}><line x1={x(at)} x2={x(at)} y1="35" y2="153" className="chart-grid vertical"/><text x={x(at)} y="177" textAnchor={at===timeline.start?'start':'middle'} className="chart-axis">{clock(at).slice(0,5)}</text></g>)}
      {timeline.segments.map((segment,index)=>segment.state==='unknown'?<g key={index}>
        <rect x={x(segment.start)} y="32" width={Math.max(0,x(segment.end)-x(segment.start))} height="122" fill="transparent" role="button" tabIndex={0} aria-label={description(segment)} onFocus={()=>setSelected('s-'+index)} onClick={()=>setSelected('s-'+index)} onKeyDown={event=>key(event,'s-'+index)}><title>{description(segment)}</title></rect>
        {x(segment.end)-x(segment.start)>85&&<text x={(x(segment.start)+x(segment.end))/2} y="101" textAnchor="middle" className="chart-gap">Sem dados</text>}
      </g>:<path key={index} d={`M ${x(segment.start)} ${y(segment.state)} H ${x(segment.end)}`} className={selected==='s-'+index?'state-line selected':'state-line'} fill="none" role="button" tabIndex={0} aria-label={description(segment)} aria-pressed={selected==='s-'+index} onFocus={()=>setSelected('s-'+index)} onClick={()=>setSelected('s-'+index)} onKeyDown={event=>key(event,'s-'+index)}><title>{description(segment)}</title></path>)}
      {changes.map((item,index)=><path key={index} d={`M ${x(item.start)} ${y(item.from)} H ${x(item.end)} V ${y(item.to)}`} className={selected==='t-'+index?'state-change selected':'state-change'} fill="none" role="button" tabIndex={0} aria-label={changeDescription(item)} aria-pressed={selected==='t-'+index} onFocus={()=>setSelected('t-'+index)} onClick={()=>setSelected('t-'+index)} onKeyDown={event=>key(event,'t-'+index)}><title>{changeDescription(item)}</title></path>)}
      <text x={right} y="203" textAnchor="end" className="chart-axis chart-now">{timeline.ends_at_now?'Agora '+clock(timeline.end).slice(0,5):'24:00'}</text>
    </svg>
    <div className="timeline-details" aria-live="polite">{change?<><strong>Mudança observada: {names[change.from].toLowerCase()} → {names[change.to].toLowerCase()}</strong><span>Entre {clock(change.start)} e {clock(change.end)} · janela de {length(change.end-change.start)}</span><small>Degrau pontilhado na leitura que detectou a mudança. O instante exato do acionamento não é conhecido.</small></>:active?<><strong>{names[active.state]}</strong><span>De {clock(active.start)} até {clock(active.end)} · {length(active.end-active.start)}</span><small>{active.state==='unknown'?'Sem leitura suficiente neste intervalo. A linha não atravessa esta lacuna.':'Intervalo inferido entre leituras concordantes, não tempo de funcionamento do compressor.'}</small></>:<><strong>Explore a linha</strong><span>Toque no gráfico ou selecione um intervalo para ver os detalhes.</span></>}</div>
    <label className="timeline-picker">Detalhes do intervalo<select aria-label="Detalhes do intervalo" value={selected} onChange={event=>setSelected(event.target.value)}><option value="">Selecione um intervalo</option>{timeline.segments.map((segment,index)=><option key={'s'+index} value={'s-'+index}>{description(segment)}</option>)}{changes.map((item,index)=><option key={'t'+index} value={'t-'+index}>{changeDescription(item)}</option>)}</select></label>
    <p className="hint">Estado ligado/desligado, não curva de watts ou consumo. Leituras a cada {timeline.sampling_seconds} segundos; degraus pontilhados indicam mudança entre amostras. Lacunas offline e anteriores à coleta interrompem a linha. O eixo termina {timeline.ends_at_now?'agora':'no fim do dia'}, sem projetar o futuro.</p>
  </section>;
}
