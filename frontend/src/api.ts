import type {Automation,AutomationApi,AutomationList,AutomationPayload,ControllerApi,ControlValue,DeviceInfo,DeviceStatus,FunctionCode} from './types';
import type {ConsumptionApi,ConsumptionDashboard,ConsumptionSettings} from './consumptionTypes';

export class ApiError extends Error {
  constructor(message:string,public status=0){super(message);}
}
export class HttpApi implements ControllerApi,AutomationApi,ConsumptionApi {
  private active = new Set<AbortController>();
  private async request<T>(path:string,body?:unknown):Promise<T> {
    const abort = new AbortController(); this.active.add(abort);
    const timeout = setTimeout(()=>abort.abort(),20000);
    try {
      const response = await fetch('/api/'+path,{
        method:body===undefined?'GET':'POST',credentials:'same-origin',cache:'no-store',signal:abort.signal,
        headers:body===undefined?{}:{'Content-Type':'application/json','X-Ar-Request':'1'},
        body:body===undefined?undefined:JSON.stringify(body)
      });
      const data = await response.json();
      if(!response.ok)throw new ApiError(typeof data.detail==='string'?data.detail:'Pedido não concluído.',response.status);
      return data as T;
    } catch(error) {
      if(error instanceof ApiError)throw error;
      if(abort.signal.aborted)throw new ApiError('O pedido demorou demais. Reconectando…');
      throw new ApiError('Conexão interrompida. Tentando reconectar…');
    } finally {clearTimeout(timeout);this.active.delete(abort);}
  }
  async session(){await this.request('session');}
  async login(password:string,remember=false){await this.request('login',{password,remember});}
  async logout(){await this.request('logout',{});}
  async devices(){return (await this.request<{devices:DeviceInfo[]}>('devices')).devices;}
  status(id:string){return this.request<DeviceStatus>(`devices/${encodeURIComponent(id)}/status`);}
  async command(id:string,code:FunctionCode,value:ControlValue){await this.request(`devices/${encodeURIComponent(id)}/command`,{code,value});}
  automations(){return this.request<AutomationList>('automations');}
  consumption(id:string,start:string,end:string){return this.request<ConsumptionDashboard>(`consumption/${encodeURIComponent(id)}?start=${encodeURIComponent(start)}&end=${encodeURIComponent(end)}`);}
  saveConsumptionSettings(id:string,settings:Pick<ConsumptionSettings,'reference_watts'|'tariff_per_kwh'>){return this.request<ConsumptionSettings>(`consumption/${encodeURIComponent(id)}/settings`,settings);}
  createAutomation(payload:AutomationPayload){return this.request<Automation>('automations',payload);}
  updateAutomation(id:string,payload:AutomationPayload){return this.request<Automation>(`automations/${encodeURIComponent(id)}`,payload);}
  async deleteAutomation(id:string){await this.request(`automations/${encodeURIComponent(id)}/delete`,{});}
  dispose(){for(const abort of this.active)abort.abort();this.active.clear();}
}
