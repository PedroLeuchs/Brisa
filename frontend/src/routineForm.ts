import type {Automation,AutomationEntryPayload,Capability,ControlValue,DeviceInfo,FunctionCode,RoutinePayload} from './types';

export const dayNames=['Seg','Ter','Qua','Qui','Sex','Sáb','Dom'];
export const actionNames:Record<FunctionCode,string>={switch:'Ligar/desligar',temp_set:'Definir temperatura',mode:'Modo de operação',fan_speed_enum:'Velocidade do vento',mode_eco:'Modo econômico',sleep:'Dormir',cleaning:'Limpeza',switch_vertical:'Oscilação vertical',switch_horizontal:'Oscilação horizontal'};
const enumNames:Record<string,string>={auto:'Automático',cold:'Resfriar',hot:'Aquecer',wet:'Desumidificar',wind:'Ventilar',high:'Alta',middle:'Média',low:'Baixa'};
export const optionName=(value:string|number)=>enumNames[String(value)]??value;
export function defaultValue(capability?:Capability):ControlValue{
  return capability?.type==='bool'?true:capability?.type==='int'?capability.values?.[0]??16:capability?.values?.[0]??'';
}
export function newEntry(device:DeviceInfo):AutomationEntryPayload{
  const code=(Object.keys(device.capabilities)[0]??'switch') as FunctionCode;
  return {id:crypto.randomUUID(),time:'',code,value:defaultValue(device.capabilities[code])};
}
export function routineEntries(item:Automation):AutomationEntryPayload[]{
  return item.entries??[{code:item.code,value:item.value,time:item.time}];
}
export function routinePayload(item:Automation):RoutinePayload{
  return {name:item.name??'Rotina de climatização',device_id:item.device_id,days:[...item.days],enabled:item.enabled,
    entries:routineEntries(item).map(({id,time,code,value})=>id?{id,time,code,value}:{time,code,value})};
}
export function describe(entry:AutomationEntryPayload){
  if(entry.code==='switch')return entry.value?'Ligar o ar':'Desligar o ar';
  const value=typeof entry.value==='boolean'?(entry.value?'ativar':'desativar'):optionName(String(entry.value));
  return `${actionNames[entry.code]}: ${value}${entry.code==='temp_set'?' °C':''}`;
}
export function conflict(entries:AutomationEntryPayload[]){
  const slots=new Map<string,ControlValue>();
  for(const entry of entries){
    if(!entry.time)continue;
    const key=entry.time+'/'+entry.code;
    if(slots.has(key))return `Às ${entry.time} há uma ação ${slots.get(key)===entry.value?'duplicada':'conflitante'}. Edite a entrada existente ou escolha outro horário.`;
    slots.set(key,entry.value);
  }
  return '';
}
