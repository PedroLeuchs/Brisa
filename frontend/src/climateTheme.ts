import type {ControlValue} from './types';

type Connection='connecting'|'online'|'offline';
type Phase='idle'|'reading'|'sending'|'confirming';
export type ClimateTheme='off'|'cold'|'hot'|'default'|'pending'|'stale';

const modeLabels:Record<string,string>={auto:'Automático',cold:'Resfriar',hot:'Aquecer',wet:'Desumidificar',wind:'Ventilar'};

export function climatePresentation(connection:Connection,phase:Phase,power:ControlValue|undefined,mode:ControlValue|undefined):{theme:ClimateTheme;label:string}{
  const modeLabel=typeof mode==='string'?modeLabels[mode]:undefined;
  const last=power===true?`ligado${modeLabel?` · ${modeLabel.toLowerCase()}`:''}`:power===false?'desligado':null;
  if(connection!=='online')return {theme:'stale',label:`Sem confirmação atual${last?` · último: ${last}`:''}`};
  if(phase==='sending'||phase==='confirming')return {theme:'pending',label:'Confirmando alteração…'};
  if(power===false)return {theme:'off',label:'Desligado'};
  if(power!==true)return {theme:'stale',label:'Estado indisponível'};
  if(mode==='cold')return {theme:'cold',label:'Ligado · Resfriar'};
  if(mode==='hot')return {theme:'hot',label:'Ligado · Aquecer'};
  return {theme:'default',label:`Ligado${modeLabel?` · ${modeLabel}`:''}`};
}
