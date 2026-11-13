import {afterEach,expect,it,vi} from 'vitest';
import {cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react';
import {AutomationModal} from './AutomationModal';
import type {Automation,AutomationApi,DeviceInfo} from './types';

afterEach(()=>{cleanup();vi.restoreAllMocks();vi.unstubAllGlobals();});
const devices:DeviceInfo[]=[{id:'home-ac',name:'Clima da casa',transport:'local',capabilities:{switch:{type:'bool',values:null},temp_set:{type:'int',values:[16,31],step:1}}}];
const existing:Automation={id:'one',device_id:'home-ac',code:'switch',value:true,time:'08:30',days:[0,2,4],enabled:true,created_at:'2026-10-23T10:00:00-03:00',updated_at:'2026-10-23T10:00:00-03:00',last_run:null,last_result:null};
function api(items:Automation[]=[]):AutomationApi{return {
  automations:vi.fn().mockResolvedValue({automations:items,timezone:'America/Sao_Paulo'}),
  createAutomation:vi.fn().mockResolvedValue(existing),updateAutomation:vi.fn().mockResolvedValue(existing),deleteAutomation:vi.fn().mockResolvedValue(undefined)
};}

it('cria uma automação no modal sem enviar comando ao aparelho',async()=>{
  const mock=api();render(<AutomationModal api={mock} devices={devices} onClose={vi.fn()}/>);
  await screen.findByText('Nenhuma rotina criada.');
  fireEvent.change(screen.getByLabelText('Ação do horário 1'),{target:{value:'temp_set'}});
  fireEvent.change(screen.getByLabelText('Valor do horário 1'),{target:{value:'23'}});
  fireEvent.change(screen.getByLabelText('Horário 1'),{target:{value:'21:15'}});
  fireEvent.click(screen.getByRole('button',{name:'Criar rotina'}));
  await waitFor(()=>expect(mock.createAutomation).toHaveBeenCalledWith({name:'Rotina de climatização',device_id:'home-ac',entries:[{id:expect.any(String),code:'temp_set',value:23,time:'21:15'}],days:[0,1,2,3,4],enabled:true}));
});

it('permite pausar, editar e excluir uma automação existente',async()=>{
  const mock=api([existing]);vi.spyOn(window,'confirm').mockReturnValue(true);
  render(<AutomationModal api={mock} devices={devices} onClose={vi.fn()}/>);
  await screen.findByText('08:30');
  fireEvent.click(screen.getByRole('button',{name:'Pausar'}));
  await waitFor(()=>expect(mock.updateAutomation).toHaveBeenCalledWith('one',expect.objectContaining({enabled:false})));
  fireEvent.click(screen.getByRole('button',{name:'Editar'}));
  expect(screen.getByRole('button',{name:'Salvar alterações'})).toBeTruthy();
  fireEvent.click(screen.getByRole('button',{name:'Excluir'}));
  await waitFor(()=>expect(mock.deleteAutomation).toHaveBeenCalledWith('one'));
});
it('adiciona quatro horários e ações dentro de uma única rotina',async()=>{
  const mock=api();render(<AutomationModal api={mock} devices={devices} onClose={vi.fn()}/>);
  await screen.findByText('Nenhuma rotina criada.');
  fireEvent.change(screen.getByLabelText('Nome da rotina'),{target:{value:'Minha rotina diária'}});
  for(let n=1;n<=4;n++){
    if(n>1)fireEvent.click(screen.getByRole('button',{name:/Adicionar horário/}));
    fireEvent.change(screen.getByLabelText(`Horário ${n}`),{target:{value:['08:00','10:00','14:00','16:00'][n-1]}});
    fireEvent.change(screen.getByLabelText(`Valor do horário ${n}`),{target:{value:n%2?'true':'false'}});
  }
  fireEvent.click(screen.getByRole('button',{name:'Criar rotina'}));
  await waitFor(()=>expect(mock.createAutomation).toHaveBeenCalledTimes(1));
  const payload=vi.mocked(mock.createAutomation).mock.calls[0][0];
  expect('entries' in payload&&payload.entries.map(({time,value})=>[time,value])).toEqual([['08:00',true],['10:00',false],['14:00',true],['16:00',false]]);
  expect(payload.days).toEqual([0,1,2,3,4]);expect(payload.name).toBe('Minha rotina diária');
});
it('remove entrada e bloqueia conflito de ação no mesmo minuto sem salvar',async()=>{
  const mock=api();render(<AutomationModal api={mock} devices={devices} onClose={vi.fn()}/>);await screen.findByText('Nenhuma rotina criada.');
  fireEvent.change(screen.getByLabelText('Horário 1'),{target:{value:'08:00'}});
  fireEvent.click(screen.getByRole('button',{name:/Adicionar horário/}));
  fireEvent.change(screen.getByLabelText('Horário 2'),{target:{value:'08:00'}});
  fireEvent.change(screen.getByLabelText('Valor do horário 2'),{target:{value:'false'}});
  expect(screen.getByText(/ação conflitante/)).toBeTruthy();expect(screen.getByRole('button',{name:'Criar rotina'}).hasAttribute('disabled')).toBe(true);
  fireEvent.click(screen.getByRole('button',{name:'Remover horário 2'}));
  expect(screen.queryByLabelText('Horário 2')).toBeNull();expect(mock.createAutomation).not.toHaveBeenCalled();
});
it('mobile usa tela inteira com voltar, prende foco e devolve foco ao fechar',async()=>{
  vi.stubGlobal('matchMedia',()=>({matches:true,addEventListener(){},removeEventListener(){}}));
  const before=document.createElement('button');before.textContent='Abrir rotinas';document.body.appendChild(before);before.focus();
  const onClose=vi.fn(),mock=api();const {unmount}=render(<AutomationModal api={mock} devices={devices} onClose={onClose}/>);
  await screen.findByText('Nenhuma rotina criada.');
  expect(screen.getByRole('dialog',{name:'Automações'}).parentElement?.classList.contains('routine-mobile')).toBe(true);
  const back=screen.getByRole('button',{name:'Voltar ao controle'});expect(document.activeElement).toBe(back);
  fireEvent.keyDown(back,{key:'Tab',shiftKey:true});expect(document.activeElement).toBe(screen.getByRole('button',{name:'Criar rotina'}));
  fireEvent.click(back);expect(onClose).toHaveBeenCalledTimes(1);unmount();expect(document.activeElement).toBe(before);before.remove();
});
it('editar rotina pausada mantém estado e todos os horários',async()=>{
  const paused:Automation={...existing,name:'Pausada',enabled:false,entries:[
    {id:'a',time:'08:30',code:'switch',value:true,last_run:null,last_result:null,history:[]},
    {id:'b',time:'10:00',code:'switch',value:false,last_run:null,last_result:null,history:[]}]};
  const mock=api([paused]);render(<AutomationModal api={mock} devices={devices} onClose={vi.fn()}/>);await screen.findByText('08:30');
  fireEvent.click(screen.getByRole('button',{name:'Editar'}));
  expect((screen.getByLabelText('Rotina ativa') as HTMLInputElement).checked).toBe(false);
  fireEvent.change(screen.getByLabelText('Horário 2'),{target:{value:'11:00'}});
  fireEvent.click(screen.getByRole('button',{name:'Salvar alterações'}));
  await waitFor(()=>expect(mock.updateAutomation).toHaveBeenCalledWith('one',expect.objectContaining({enabled:false,entries:[{id:'a',time:'08:30',code:'switch',value:true},{id:'b',time:'11:00',code:'switch',value:false}]})));
});
