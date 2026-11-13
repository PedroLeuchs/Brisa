export type FunctionCode = 'switch'|'temp_set'|'mode'|'fan_speed_enum'|'mode_eco'|'sleep'|'cleaning'|'switch_vertical'|'switch_horizontal';
export type ControlValue = boolean|number|string;
export interface Capability {type:'bool'|'int'|'enum';values:null|number[]|string[];step?:number}
export interface DeviceInfo {id:string;name:string;transport:'local'|'remote'|'tuya_cloud';capabilities:Partial<Record<FunctionCode,Capability>>}
export interface SensorReading {available:boolean;value:number|null;unit:string;observed_at:number|null;source?:'device';reason?:string}
export interface DeviceStatus {device_id:string;state:Partial<Record<FunctionCode,ControlValue>>;available:FunctionCode[];timestamp:number;telemetry?:{ambient_temperature?:SensorReading}}
export interface AutomationEntryPayload {id?:string;code:FunctionCode;value:ControlValue;time:string}
export interface AutomationResult {status:'success'|'offline'|'uncertain';at:string;message?:string}
export interface AutomationEntry extends AutomationEntryPayload {id:string;last_run:string|null;last_result:AutomationResult|null;history:{occurrence:string;time:string;code:FunctionCode;value:ControlValue;result:AutomationResult|null}[]}
export interface RoutinePayload {name:string;device_id:string;entries:AutomationEntryPayload[];days:number[];enabled:boolean}
export type AutomationPayload=RoutinePayload|{name?:string;device_id:string;code:FunctionCode;value:ControlValue;time:string;days:number[];enabled:boolean};
export interface Automation {id:string;name?:string;device_id:string;entries?:AutomationEntry[];code:FunctionCode;value:ControlValue;time:string;days:number[];enabled:boolean;created_at:string;updated_at:string;last_run:string|null;last_result:AutomationResult|null}
export interface AutomationList {automations:Automation[];timezone:string;scheduler?:{status:string;message:string|null;running:boolean;failures:number}}
export interface AutomationApi {
  automations():Promise<AutomationList>;
  createAutomation(payload:AutomationPayload):Promise<Automation>;
  updateAutomation(id:string,payload:AutomationPayload):Promise<Automation>;
  deleteAutomation(id:string):Promise<void>;
}
export interface ControllerApi {
  session():Promise<void>;
  login(password:string,remember?:boolean):Promise<void>;
  logout():Promise<void>;
  devices():Promise<DeviceInfo[]>;
  status(id:string):Promise<DeviceStatus>;
  command(id:string,code:FunctionCode,value:ControlValue):Promise<void>;
  dispose():void;
}
