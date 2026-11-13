import {afterEach,expect,it,vi} from 'vitest';
import {cleanup,fireEvent,render,screen,waitFor,within} from '@testing-library/react';
import {App} from './App';
import {ControllerStore} from './controller';
import {ApiError} from './api';
import type {ControllerApi} from './types';
import {HttpApi} from './api';
afterEach(()=>{cleanup();vi.restoreAllMocks();vi.unstubAllGlobals();});

function mockApi():ControllerApi{return {
  session:vi.fn().mockResolvedValue(undefined),login:vi.fn().mockResolvedValue(undefined),logout:vi.fn().mockResolvedValue(undefined),
  devices:vi.fn().mockResolvedValue([{id:'home-ac',name:'Clima da casa',transport:'local',capabilities:{switch:{type:'bool',values:null},temp_set:{type:'int',values:[16,31]}}}]),
  status:vi.fn().mockResolvedValue({device_id:'home-ac',state:{switch:false,temp_set:21},available:['switch','temp_set'],timestamp:1700000000}),
  command:vi.fn().mockResolvedValue(undefined),dispose:vi.fn()
};}
it('mostra estado real e mantém recursos não mapeados desabilitados',async()=>{
  const api=mockApi();render(<App store={new ControllerStore(api)}/>);
  await screen.findByText('Ar desligado');
  const powerButton=screen.getByRole('button',{name:'Ligar ar'});
  expect(powerButton.hasAttribute('disabled')).toBe(false);
  expect(powerButton.querySelector('svg.power-icon')).toBeTruthy();
  expect(powerButton.textContent).toBe('');
  expect(screen.getByRole('checkbox',{name:'Modo econômico'}).hasAttribute('disabled')).toBe(true);
  expect(screen.getByText('21')).toBeTruthy();expect(api.command).not.toHaveBeenCalled();
});
it('uma sessão válida com aparelho offline mantém o painel e oferece atualização',async()=>{
  const api=mockApi();vi.mocked(api.status).mockRejectedValue(new ApiError('Sem resposta do ar.',503));
  render(<App store={new ControllerStore(api)}/>);
  await screen.findByText('○ Reconectando…');
  expect(screen.getByRole('button',{name:'Ligar ar'}).hasAttribute('disabled')).toBe(true);
  await waitFor(()=>expect(screen.getByRole('button',{name:/Atualizar estado/}).hasAttribute('disabled')).toBe(false));
  expect(screen.queryByLabelText('Senha do controlador')).toBeNull();expect(api.command).not.toHaveBeenCalled();
});
it('desktop alterna modo controle usando exatamente os mesmos controles e volta ao painel',async()=>{
  const api=mockApi();render(<App store={new ControllerStore(api)}/>);await screen.findByText('Ar desligado');
  const slider=screen.getByRole('slider');const section=screen.getByRole('region',{name:'Controle do ambiente'});
  expect(section.classList.contains('dashboard-view')).toBe(true);
  fireEvent.click(screen.getByRole('button',{name:'Modo controle'}));
  expect(section.classList.contains('remote-view')).toBe(true);expect(screen.getByRole('slider')).toBe(slider);
  fireEvent.click(screen.getByRole('button',{name:'Voltar ao painel'}));
  expect(section.classList.contains('dashboard-view')).toBe(true);expect(api.command).not.toHaveBeenCalled();
});
it('controle abre opções em painel e preserva Timer do módulo de automações',async()=>{
  const api=mockApi();vi.spyOn(HttpApi.prototype,'automations').mockResolvedValue({automations:[],timezone:'America/Sao_Paulo'});
  render(<App store={new ControllerStore(api)}/>);await screen.findByText('Ar desligado');
  fireEvent.click(screen.getByRole('button',{name:'Modo controle'}));
  const navigation=screen.getByRole('navigation',{name:'Opções do controle'});
  fireEvent.click(within(navigation).getByRole('button',{name:/Modo/}));
  expect(screen.getByRole('dialog',{name:'Modo de operação'})).toBeTruthy();
  fireEvent.click(screen.getByRole('button',{name:'Fechar opções'}));
  fireEvent.click(within(navigation).getByRole('button',{name:/Timer/}));
  expect(await screen.findByRole('dialog',{name:'Automações'})).toBeTruthy();expect(api.command).not.toHaveBeenCalled();
});
it('mobile usa diretamente o mesmo seletor circular e a barra inferior',async()=>{
  vi.stubGlobal('matchMedia',()=>({matches:true,addEventListener(){},removeEventListener(){}}));
  const api=mockApi();render(<App store={new ControllerStore(api)}/>);await screen.findByText('Ar desligado');
  expect(screen.getByTestId('temperature-dial')).toBeTruthy();expect(screen.getByRole('navigation',{name:'Opções do controle'})).toBeTruthy();
  expect(screen.queryByRole('button',{name:'Modo controle'})).toBeNull();expect(api.command).not.toHaveBeenCalled();
});

it.each([
  [false,'cold','off','Desligado'],
  [true,'cold','cold','Ligado · Resfriar'],
  [true,'hot','hot','Ligado · Aquecer'],
] as const)('mobile renderiza estado confirmado %s/%s sem enviar comando',async(power,mode,theme,label)=>{
  vi.stubGlobal('matchMedia',()=>({matches:true,addEventListener(){},removeEventListener(){}}));
  const api=mockApi();
  vi.mocked(api.status).mockResolvedValue({device_id:'home-ac',state:{switch:power,temp_set:21,mode},available:['switch','temp_set','mode'],timestamp:1700000000});
  render(<App store={new ControllerStore(api)}/>);
  await screen.findByText(label);
  expect(screen.getByRole('region',{name:'Controle do ambiente'}).getAttribute('data-climate-state')).toBe(theme);
  expect(screen.getByRole('main').classList.contains(`climate-theme-${theme}`)).toBe(true);
  expect(api.command).not.toHaveBeenCalled();
});

it('abre Consumo pelo botão do cabeçalho em desktop e controle',async()=>{
  const api=mockApi();vi.spyOn(HttpApi.prototype,'consumption').mockRejectedValue(new Error('Histórico aguardando servidor.'));
  render(<App store={new ControllerStore(api)}/>);await screen.findByText('Ar desligado');
  fireEvent.click(screen.getByRole('button',{name:'Consumo'}));
  expect(await screen.findByRole('dialog',{name:'Consumo'})).toBeTruthy();
  fireEvent.click(screen.getByRole('button',{name:'Fechar consumo'}));
  fireEvent.click(screen.getByRole('button',{name:'Modo controle'}));
  expect(screen.getByRole('button',{name:'Consumo'})).toBeTruthy();expect(api.command).not.toHaveBeenCalled();
});
