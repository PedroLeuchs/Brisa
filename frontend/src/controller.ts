import {ApiError} from './api';
import type {ControllerApi,ControlValue,DeviceInfo,DeviceStatus,FunctionCode} from './types';

export interface ViewState {
  auth:'checking'|'signedout'|'signedin';connection:'connecting'|'online'|'offline';
  phase:'idle'|'reading'|'sending'|'confirming';devices:DeviceInfo[];selected:string;
  data:DeviceStatus|null;message:string;
}
const initial:ViewState={auth:'checking',connection:'connecting',phase:'idle',devices:[],selected:'',data:null,message:''};
export class ControllerStore {
  private view:ViewState={...initial}; private listeners=new Set<()=>void>();
  private timer:ReturnType<typeof setTimeout>|undefined; private busy=false;private disposed=false;
  private failures=0; private lastCommand=0;
  private interacting=false;
  constructor(private api:ControllerApi){}
  snapshot=()=>this.view;
  subscribe=(listener:()=>void)=>{this.listeners.add(listener);return()=>{this.listeners.delete(listener);};};
  private update(next:Partial<ViewState>){if(this.disposed)return;this.view={...this.view,...next};for(const listener of this.listeners)listener();}
  private clear(){clearTimeout(this.timer);}
  private later(fn:()=>void,ms:number){this.clear();if(!this.disposed)this.timer=setTimeout(fn,ms);}
  private schedule(){if(this.view.auth==='signedin')this.later(()=>void this.refresh(),this.view.connection==='online'?15000:Math.min(10000,2000*2**Math.max(0,this.failures-1)));}
  setInteraction=(active:boolean)=>{this.interacting=active;if(active)this.clear();else this.schedule();};
  private error(error:unknown){
    if(error instanceof ApiError&&error.status===401){this.clear();this.update({auth:'signedout',data:null,connection:'offline',message:'Sua sessão terminou. Entre novamente.'});return;}
    this.failures=Math.min(4,this.failures+1);
    this.update({connection:'offline',message:error instanceof Error?error.message:'Falha na conexão. Tentando novamente…'});
  }
  private async catalog(){
    const devices=await this.api.devices();
    if(!devices.length)throw new ApiError('Nenhum aparelho configurado neste servidor.');
    this.update({devices,selected:devices.some(d=>d.id===this.view.selected)?this.view.selected:devices[0].id});
  }
  private async read(){
    const data=await this.api.status(this.view.selected);this.failures=0;
    this.update({data,connection:'online',message:data.available.length?'':'As funções deste aparelho ainda precisam ser configuradas no computador.'});
  }
  async start(){
    if(this.busy||this.disposed)return;this.busy=true;this.clear();
    try {await this.api.session();this.update({auth:'signedin'});await this.catalog();this.update({phase:'reading'});await this.read();}
    catch(error){if(error instanceof ApiError&&error.status===401)this.update({auth:'signedout',message:''});else this.error(error);}
    finally {this.busy=false;this.update({phase:'idle'});if(this.view.auth==='checking')this.later(()=>void this.start(),5000);else this.schedule();}
  }
  async login(password:string,remember=false){
    if(this.busy||this.disposed)return;this.busy=true;this.clear();this.update({phase:'reading',message:''});
    try {await this.api.login(password,remember);this.update({auth:'signedin'});await this.catalog();await this.read();}
    catch(error){if(error instanceof ApiError&&error.status===401)this.update({auth:'signedout',data:null,connection:'offline',message:error.message});else this.error(error);}
    finally {this.busy=false;this.update({phase:'idle'});this.schedule();}
  }
  async logout(){
    if(this.busy||this.disposed)return;this.busy=true;this.clear();
    try {await this.api.logout();this.update({...initial,auth:'signedout',connection:'offline'});}
    catch(error){this.error(error);}
    finally{this.busy=false;this.update({phase:'idle'});this.schedule();}
  }
  async refresh(){
    if(this.busy||this.disposed||this.interacting||this.view.auth!=='signedin')return;
    this.busy=true;this.clear();this.update({phase:'reading'});
    try {if(!this.view.selected)await this.catalog();await this.read();}
    catch(error){this.error(error);}
    finally{this.busy=false;this.update({phase:'idle'});this.schedule();}
  }
  async select(id:string){
    if(this.busy||!this.view.devices.some(device=>device.id===id))return;
    this.update({selected:id,data:null,connection:'connecting'});await this.refresh();
  }
  async send(code:FunctionCode,value:ControlValue){
    if(this.busy||this.disposed||this.view.auth!=='signedin'||this.view.connection!=='online'||!this.view.data?.available.includes(code))return;
    this.busy=true;this.clear();this.update({phase:'sending',message:'Enviando ao aparelho…'});
    let uncertain=false;
    try {
      await this.pause(Math.max(0,1100-(Date.now()-this.lastCommand)));if(this.disposed)return;
      this.lastCommand=Date.now();
      try{await this.api.command(this.view.selected,code,value);}
      catch(error){if(error instanceof ApiError&&error.status===401)throw error;uncertain=true;}
      if(this.disposed)return;
      this.update({phase:'confirming',message:'Confirmando estado do aparelho…'});await this.pause(350);
      if(this.disposed)return;await this.read();
      const observed=this.view.data?.state[code];
      if(uncertain)this.update({message:'Envio sem confirmação. Confira o estado lido antes de tentar novamente.'});
      else if(observed!==value)this.update({message:'O aparelho ainda não confirmou a alteração. O estado exibido é a última leitura.'});
    } catch(error){this.error(error);}
    finally{await this.pause(Math.max(0,1100-(Date.now()-this.lastCommand)));this.busy=false;this.update({phase:'idle'});this.schedule();}
  }
  private pause(ms:number){return ms>0?new Promise<void>(resolve=>setTimeout(resolve,ms)):Promise.resolve();}
  dispose(){this.disposed=true;this.clear();this.api.dispose();this.listeners.clear();}
}
