import {useId} from 'react';
import type {ControlValue,DeviceInfo,FunctionCode} from './types';

export const modes=[['auto','Automático'],['cold','Resfriar'],['hot','Aquecer'],['wet','Desumidificar'],['wind','Ventilar']];
export const fans=[['auto','Automática'],['high','Alta'],['middle','Média'],['low','Baixa']];
const switches:{code:FunctionCode;title:string;hint?:string}[]=[
  {code:'mode_eco',title:'Modo econômico',hint:'Conforto com economia'},
  {code:'sleep',title:'Dormir',hint:'Para a hora de descansar'},
  {code:'switch_vertical',title:'Oscilação vertical'},
  {code:'switch_horizontal',title:'Oscilação horizontal'},
  {code:'cleaning',title:'Limpeza'}
];
export type OptionSection='all'|'mode'|'fan'|'functions';
interface Props{section:OptionSection;values:Partial<Record<FunctionCode,ControlValue>>;device?:DeviceInfo;can:(code:FunctionCode)=>boolean|undefined;onSend:(code:FunctionCode,value:ControlValue)=>void}
export function ClimateOptions({section,values,device,can,onSend}:Props){
  const id=useId();
  return <>
    {(section==='all'||section==='mode')&&<div className="mode-options"><label htmlFor={id+'mode'}>Modo de operação</label><select id={id+'mode'} value={typeof values.mode==='string'?values.mode:''} disabled={!can('mode')} onChange={event=>onSend('mode',event.target.value)}><option value="" disabled>Aguardando leitura</option>{modes.map(([value,label])=><option key={value} value={value}>{label}</option>)}</select></div>}
    {(section==='all'||section==='fan')&&<div className="fan-options"><label htmlFor={id+'fan'}>Velocidade do vento</label><select id={id+'fan'} value={typeof values.fan_speed_enum==='string'?values.fan_speed_enum:''} disabled={!can('fan_speed_enum')} onChange={event=>onSend('fan_speed_enum',event.target.value)}><option value="" disabled>Aguardando leitura</option>{fans.map(([value,label])=><option key={value} value={value}>{label}</option>)}</select></div>}
    {(section==='all'||section==='functions')&&<div className="toggles">{switches.map(({code,title,hint})=><label className="toggle" key={code}><span>{title}<small>{!device?.capabilities[code]?'Ainda não disponível neste aparelho':hint}</small></span><input aria-label={title} type="checkbox" checked={values[code]===true} disabled={!can(code)||typeof values[code]!=='boolean'} onChange={event=>onSend(code,event.target.checked)}/></label>)}</div>}
  </>;
}
