import {useEffect,useId,useRef,useState} from 'react';
import type {ConsumptionDay} from './consumptionTypes';

const dateLabel=(value:string)=>value.slice(8,10)+'/'+value.slice(5,7);
const timeLabel=(seconds:number)=>`${Math.floor(seconds/3600)}h ${String(Math.floor(seconds%3600/60)).padStart(2,'0')}min`;
export function consumptionBuckets(days:ConsumptionDay[]){
  const group=days.length>62?7:1;
  const buckets=[];
  for(let index=0;index<days.length;index+=group){
    const portion=days.slice(index,index+group);
    const on=portion.reduce((sum,day)=>sum+day.on_seconds,0),off=portion.reduce((sum,day)=>sum+day.off_seconds,0),unknown=portion.reduce((sum,day)=>sum+day.unknown_seconds,0);
    buckets.push({start:portion[0].date,end:portion[portion.length-1].date,on,off,unknown,coverage:(on+off+unknown)>0?100*(on+off)/(on+off+unknown):0});
  }
  return buckets;
}

export function ConsumptionBars({days}:{days:ConsumptionDay[]}){
  const heading=useId(),ref=useRef<SVGSVGElement>(null),[width,setWidth]=useState(960),[selected,setSelected]=useState<number|null>(null);
  useEffect(()=>{const element=ref.current;if(!element)return;const resize=()=>{const next=element.getBoundingClientRect().width;if(next>0)setWidth(Math.max(280,next));};resize();if(typeof ResizeObserver==='undefined')return;const observer=new ResizeObserver(resize);observer.observe(element);return()=>observer.disconnect();},[]);
  const buckets=consumptionBuckets(days),left=40,right=width-15,bottom=164,top=30;
  const maximum=Math.max(1,Math.ceil(Math.max(0,...buckets.map(item=>item.on/3600))/2)*2);
  const pitch=(right-left)/Math.max(1,buckets.length),barWidth=Math.max(2,pitch*.6);
  const x=(index:number)=>left+pitch*(index+.5),y=(hours:number)=>bottom-hours/maximum*(bottom-top);
  const label=(item:typeof buckets[number])=>`${dateLabel(item.start)}${item.end!==item.start?' a '+dateLabel(item.end):''} · ${timeLabel(item.on)} ligado observado · cobertura ${item.coverage.toLocaleString('pt-BR',{maximumFractionDigits:1})}%`;
  const active=selected===null?null:buckets[selected];
  const tickStep=Math.max(1,Math.ceil(buckets.length/(width<500?5:9)));
  return <section className="consumption-timeline consumption-bars" aria-labelledby={heading}>
    <div className="timeline-heading"><div><p className="eyebrow">DISTRIBUIÇÃO DO USO NO PERÍODO</p><h3 id={heading}>Tempo ligado {days.length>62?'por semana':'por dia'}</h3><span className="chart-period-label">Horas observadas · h</span></div><div className="chart-reading"><strong>{(buckets.reduce((sum,item)=>sum+item.on,0)/3600).toLocaleString('pt-BR',{maximumFractionDigits:1})}<small>h</small></strong><span>no período observado</span></div></div>
    <svg ref={ref} className="usage-bars-chart" viewBox={`0 0 ${width} 214`} role="group" aria-label="Gráfico de barras de tempo observado ligado" onPointerDown={event=>{const box=event.currentTarget.getBoundingClientRect();if(!box.width)return;const position=(event.clientX-box.left)/box.width*width;setSelected(Math.max(0,Math.min(buckets.length-1,Math.floor((position-left)/pitch))));}}>
      {[0,maximum/2,maximum].map(value=><g key={value}><line x1={left} x2={right} y1={y(value)} y2={y(value)} className="chart-grid"/><text x={left-8} y={y(value)+4} textAnchor="end" className="chart-axis">{value.toLocaleString('pt-BR')}h</text></g>)}
      {buckets.map((item,index)=><g key={item.start} role="button" tabIndex={0} aria-label={label(item)} aria-pressed={selected===index} onFocus={()=>setSelected(index)} onClick={()=>setSelected(index)} onKeyDown={event=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();setSelected(index);}}}>
        <rect x={x(index)-pitch/2} y={top} width={pitch} height={bottom-top+8} fill="transparent"/>
        {item.on+item.off===0?<text x={x(index)} y={bottom-6} textAnchor="middle" className="bar-missing">?</text>:item.on===0?<circle cx={x(index)} cy={bottom} r="2.5" className="usage-bar"/>:<rect x={x(index)-barWidth/2} y={y(item.on/3600)} width={barWidth} height={bottom-y(item.on/3600)} rx="2" className={selected===index?'usage-bar selected':'usage-bar'}/>}
        <title>{label(item)}{item.on+item.off===0?' · sem observação':''}</title>
      </g>)}
      {buckets.map((item,index)=>index%tickStep===0||index===buckets.length-1?<text key={item.start} x={x(index)} y="190" textAnchor="middle" className="chart-axis bar-date">{dateLabel(item.start)}</text>:null)}
    </svg>
    <div className="timeline-details" aria-live="polite">{active?<><strong>{dateLabel(active.start)}{active.end!==active.start?' a '+dateLabel(active.end):''}</strong><span>{timeLabel(active.on)} ligado observado · {timeLabel(active.off)} desligado</span><small>{timeLabel(active.unknown)} sem observação · cobertura {active.coverage.toLocaleString('pt-BR',{maximumFractionDigits:1})}%. {active.on+active.off===0?'Sem dados; não equivale a zero uso.':''}</small></>:<><strong>Compare os dias</strong><span>Toque em uma barra para consultar tempo ligado e cobertura.</span></>}</div>
    <label className="timeline-picker">Detalhes do dia ou grupo<select aria-label="Detalhes do dia ou grupo" value={selected===null?'':String(selected)} onChange={event=>setSelected(event.target.value===''?null:Number(event.target.value))}><option value="">Selecione uma barra</option>{buckets.map((item,index)=><option key={item.start} value={index}>{label(item)}</option>)}</select></label>
    <p className="hint">Altura = horas observadas ligado, não kWh. “?” indica ausência de observação; períodos parcialmente cobertos não têm lacunas preenchidas. {days.length>62?'Para períodos maiores, cada barra reúne até sete dias.':''} Energia e custo só aparecem no resumo quando há estimativa válida e identificada.</p>
  </section>;
}
