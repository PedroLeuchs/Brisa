import {afterEach,expect,it,vi} from 'vitest';
import {cleanup,render,screen} from '@testing-library/react';
import {mkdirSync,readFileSync,readdirSync,writeFileSync} from 'node:fs';
import {resolve} from 'node:path';
import {AutomationModal} from './AutomationModal';
import type {Automation,AutomationApi,DeviceInfo} from './types';

afterEach(()=>{cleanup();vi.unstubAllGlobals();});
const devices:DeviceInfo[]=[{id:'home-ac',name:'Clima da casa',transport:'local',capabilities:{switch:{type:'bool',values:null},temp_set:{type:'int',values:[16,31],step:1}}}];
const example:Automation={id:'visual-only',name:'Minha rotina diária',device_id:'home-ac',days:[0,1,2,3,4],enabled:false,
  code:'switch',value:true,time:'08:00',created_at:'fixture',updated_at:'fixture',last_run:null,last_result:null,
  entries:['08:00','10:00','14:00','16:00'].map((time,index)=>({id:'entry-'+index,time,code:'switch',value:index%2===0,last_run:null,last_result:null,history:[]}))};
function escape(text:string){return text.replaceAll('&','&amp;').replaceAll('"','&quot;').replaceAll('<','&lt;').replaceAll('>','&gt;');}
for(const mobile of [true,false])it(`hierarquia visual de rotina ${mobile?'mobile':'desktop'} sem rede real`,async()=>{
  vi.stubGlobal('matchMedia',()=>({matches:mobile,addEventListener(){},removeEventListener(){}}));
  const api:AutomationApi={automations:vi.fn().mockResolvedValue({automations:[example],timezone:'America/Sao_Paulo'}),createAutomation:vi.fn(),updateAutomation:vi.fn(),deleteAutomation:vi.fn()};
  const {container}=render(<AutomationModal api={api} devices={devices} onClose={vi.fn()}/>);
  await screen.findByText('16:00');expect(screen.getByText('Minha rotina diária')).toBeTruthy();expect(screen.getByText('Pausada')).toBeTruthy();
  if(process.env.BRISA_ROUTINE_QA==='1'){
    const assets=resolve('dist/assets'),css=readFileSync(resolve(assets,readdirSync(assets).find(file=>file.endsWith('.css'))!),'utf8');
    const inner=`<!doctype html><html lang="pt-BR"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>${css}</style><body><main class="app-theme climate-theme-cold">${container.innerHTML}</main></body></html>`;
    const output=resolve('../work');mkdirSync(output,{recursive:true});
    writeFileSync(resolve(output,`routines-${mobile?'mobile':'desktop'}-qa.html`),`<!doctype html><html lang="pt-BR"><meta charset="utf-8"><title>Brisa · QA visual de rotinas</title><style>body{background:#08151e;color:#d7e9ee;font:13px system-ui;margin:14px}p{margin:0 0 12px}iframe{display:block;width:${mobile?'390':'1000'}px;height:${mobile?'844':'800'}px;max-width:100%;border:1px solid #465b64;border-radius:12px}</style><p>QA visual · dados simulados · rotina pausada · nenhuma conexão com o ar</p><iframe title="Rotinas ${mobile?'mobile':'desktop'}" srcdoc="${escape(inner)}"></iframe></html>`);
  }
  expect(api.createAutomation).not.toHaveBeenCalled();expect(api.updateAutomation).not.toHaveBeenCalled();
});
