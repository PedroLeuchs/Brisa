import {useEffect,useId,useRef,useState} from 'react';
import type {KeyboardEvent,PointerEvent} from 'react';

interface Props {
  value:number|null;min:number;max:number;step:number;disabled:boolean;busy:boolean;
  online:boolean;power:boolean|undefined;onCommit:(value:number)=>void;
  onInteraction?:(active:boolean)=>void;
  variant?:'panel'|'remote';
}
const keys=new Set(['ArrowLeft','ArrowRight','ArrowUp','ArrowDown','Home','End','PageUp','PageDown']);

export function TemperatureControl({value,min,max,step,disabled,busy,online,power,onCommit,onInteraction,variant='panel'}:Props){
  const id=useId();
  const [draft,setDraft]=useState<number|null>(null);
  const [pending,setPending]=useState<number|null>(null);
  const [active,setActive]=useState(false);
  const gesture=useRef<'pointer'|'keyboard'|null>(null);
  const pointerId=useRef<number|null>(null);
  const range=useRef<HTMLInputElement>(null);
  const circleValue=useRef<number|null>(null);
  const normalize=(raw:number)=>Math.max(min,Math.min(max,min+Math.round((raw-min)/step)*step));
  const selected=draft??pending??value;
  const usable=!disabled&&value!==null;
  useEffect(()=>{if(!busy&&!active)setPending(null);},[busy,active,value]);
  useEffect(()=>()=>{onInteraction?.(false);},[onInteraction]);
  function begin(kind:'pointer'|'keyboard'){
    if(!usable||gesture.current)return;
    gesture.current=kind;setActive(true);setDraft(value);onInteraction?.(true);
  }
  function finish(raw:number){
    const next=normalize(raw);gesture.current=null;pointerId.current=null;
    setActive(false);setDraft(null);onInteraction?.(false);
    if(usable&&next!==value){setPending(next);onCommit(next);}
  }
  function cancel(){gesture.current=null;pointerId.current=null;setDraft(null);setActive(false);onInteraction?.(false);}
  function pointerDown(event:PointerEvent<HTMLInputElement>){
    if(!usable)return;begin('pointer');pointerId.current=event.pointerId;
    event.currentTarget.setPointerCapture?.(event.pointerId);
  }
  function pointerUp(event:PointerEvent<HTMLInputElement>){
    if(gesture.current!=='pointer'||pointerId.current!==event.pointerId)return;
    finish(Number(event.currentTarget.value));
  }
  function circleSelection(event:PointerEvent<HTMLDivElement>){
    const rect=event.currentTarget.getBoundingClientRect();
    const angle=(Math.atan2(event.clientY-rect.top-rect.height/2,event.clientX-rect.left-rect.width/2)*180/Math.PI-135+360)%360;
    const offset=angle>270?(angle>315?0:270):angle;
    const next=normalize(min+offset/270*(max-min));circleValue.current=next;setDraft(next);
  }
  function circleDown(event:PointerEvent<HTMLDivElement>){
    if(!usable)return;event.preventDefault();range.current?.focus();begin('pointer');pointerId.current=event.pointerId;
    event.currentTarget.setPointerCapture?.(event.pointerId);circleSelection(event);
  }
  function circleMove(event:PointerEvent<HTMLDivElement>){
    if(gesture.current==='pointer'&&pointerId.current===event.pointerId)circleSelection(event);
  }
  function circleUp(event:PointerEvent<HTMLDivElement>){
    if(gesture.current!=='pointer'||pointerId.current!==event.pointerId)return;
    circleSelection(event);finish(circleValue.current??value??min);
  }
  function keyDown(event:KeyboardEvent<HTMLInputElement>){
    if(event.key==='Escape'){event.preventDefault();cancel();return;}
    if(keys.has(event.key))begin('keyboard');
  }
  function keyUp(event:KeyboardEvent<HTMLInputElement>){
    if(keys.has(event.key)&&gesture.current==='keyboard')finish(Number(event.currentTarget.value));
  }
  function button(next:number){if(!usable)return;const bounded=normalize(next);if(bounded!==value){setPending(bounded);onCommit(bounded);}}
  const caption=active?'ESCOLHENDO TEMPERATURA':pending!==null?'TEMPERATURA SOLICITADA':'TEMPERATURA DEFINIDA';
  const ratio=selected===null?0:Math.max(0,Math.min(1,(selected-min)/(max-min)));
  const point=(angle:number,radius:number)=>({x:160+radius*Math.cos(angle*Math.PI/180),y:160+radius*Math.sin(angle*Math.PI/180)});
  const handle=point(135+ratio*270,128),length=2*Math.PI*128;
  return <div className="temperature-control">
    <div className={`dial ${!online?'stale':''}`} data-testid={variant==='remote'?'temperature-dial':undefined}
      onPointerDown={variant==='remote'?circleDown:undefined} onPointerMove={variant==='remote'?circleMove:undefined} onPointerUp={variant==='remote'?circleUp:undefined}
      onPointerCancel={variant==='remote'?cancel:undefined} onLostPointerCapture={()=>{if(variant==='remote'&&gesture.current==='pointer')cancel();}}>
      {variant==='remote'&&<svg className="dial-ring" viewBox="0 0 320 320" aria-hidden="true">
        {Array.from({length:46},(_,i)=>{const angle=135+i*6,a=point(angle,i%3===0?140:145),b=point(angle,151);return <line key={i} className={`ring-tick ${i/45<=ratio?'passed':''}`} x1={a.x} y1={a.y} x2={b.x} y2={b.y}/>;})}
        <circle className="ring-track" cx="160" cy="160" r="128" strokeDasharray={`${length*.75} ${length}`} transform="rotate(135 160 160)"/>
        <circle className="ring-progress" cx="160" cy="160" r="128" strokeDasharray={`${length*.75*ratio} ${length}`} transform="rotate(135 160 160)"/>
        <circle className="ring-handle" cx={handle.x} cy={handle.y} r="8"/>
      </svg>}
      <span className="dial-caption">{caption}</span><div><strong aria-live="off">{selected??'—'}</strong><span className="degree">°C</span></div><span className="muted">{!online?'Aguardando conexão':power===true?'Ar ligado':power===false?'Ar desligado':'Aguardando leitura'}</span></div>
    <label className="range-label" htmlFor={id}>{variant==='remote'?'Arraste o anel para ajustar':'Arraste para escolher'}</label>
    <input ref={range} id={id} className="temperature-range" type="range" min={min} max={max} step={step} disabled={!usable}
      value={selected??min} aria-label="Temperatura desejada" aria-valuetext={`${selected??min} graus Celsius`}
      onChange={event=>setDraft(normalize(Number(event.target.value)))} onPointerDown={pointerDown} onPointerUp={pointerUp}
      onPointerCancel={cancel} onLostPointerCapture={()=>{if(gesture.current==='pointer')cancel();}}
      onKeyDown={keyDown} onKeyUp={keyUp} onBlur={()=>{
        if(gesture.current==='keyboard')finish(Number(range.current?.value??value));
        else if(gesture.current==='pointer')cancel();
      }}/>
    <div className="range-scale" aria-hidden="true"><span>{min} °C</span><span>{max} °C</span></div>
    <p className="selection-state" role="status">{active?'Solte para enviar ao aparelho':pending!==null?'Solicitado · aguardando confirmação do aparelho':value!==null?`Confirmado pelo aparelho: ${value} °C`:'Aguardando leitura'}</p>
    <div className="temperature-actions"><button disabled={!usable||value===null||value<=min} aria-label="Diminuir temperatura" onClick={()=>value!==null&&button(value-step)}>−</button><span>Ajuste fino</span><button disabled={!usable||value===null||value>=max} aria-label="Aumentar temperatura" onClick={()=>value!==null&&button(value+step)}>+</button></div>
  </div>;
}
