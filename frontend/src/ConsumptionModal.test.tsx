import {afterEach,expect,it,vi} from 'vitest';
import {cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react';
import {ConsumptionModal} from './ConsumptionModal';
import type {ConsumptionApi,ConsumptionDashboard} from './consumptionTypes';

afterEach(()=>{cleanup();vi.restoreAllMocks();});
export function consumptionFixture():ConsumptionDashboard{return {
  device_id:'home-ac',start_date:'2026-10-23',end_date:'2026-10-23',timezone:'America/Sao_Paulo',collection_started_at:null,retained_from:0,last_observation:null,
  settings:{reference_watts:null,tariff_per_kwh:1.056961,tariff_source:'Referência da conta Copel · Toledo/PR · convencional · set/26',solar_credits_included:false},
  days:[{date:'2026-10-23',on_seconds:0,off_seconds:0,unknown_seconds:3600,coverage_percent:0}],
  timeline:{date:'2026-10-23',start:Date.parse('2026-10-23T00:00:00-03:00')/1000,end:Date.parse('2026-10-23T01:00:00-03:00')/1000,ends_at_now:true,sampling_seconds:60,segments:[{start:Date.parse('2026-10-23T00:00:00-03:00')/1000,end:Date.parse('2026-10-23T01:00:00-03:00')/1000,state:'unknown'}]},
  totals:{on_seconds:0,off_seconds:0,unknown_seconds:3600,coverage_percent:0,estimated_kwh:null,estimated_cost:null},
  energy_source:'unavailable',measured_energy_available:false,method:'Leituras concordantes; lacunas não são preenchidas.',estimate_note:'Referências atuais, sem créditos solares.',collector:{status:'waiting',last_check_at:null,failures:0,running:true,interval_seconds:60}
};}
function api(result=consumptionFixture()){
  return {consumption:vi.fn().mockResolvedValue(result),saveConsumptionSettings:vi.fn().mockResolvedValue(result.settings)} satisfies ConsumptionApi;
}

it('mostra Consumo sem inventar energia e custo quando não há referência nem dados',async()=>{
  render(<ConsumptionModal api={api()} deviceId="home-ac" deviceName="Clima da casa" onClose={vi.fn()}/>);
  await screen.findByRole('dialog',{name:'Consumo'});
  await screen.findByText('A coleta ainda não começou. Aguardando a primeira leitura.');
  expect(screen.getAllByText('Indisponível')).toHaveLength(2);
  expect(screen.getByText(/Sem intervalos observados/)).toBeTruthy();
  expect((screen.getByLabelText('Potência elétrica de referência (W)') as HTMLInputElement).value).toBe('');
  expect(screen.getByText(/Sem medição elétrica comprovada/)).toBeTruthy();
  expect((screen.getByLabelText('Período') as HTMLSelectElement).value).toBe('1');
  expect(screen.getByRole('group',{name:'Gráfico diário de estado em degraus'})).toBeTruthy();
});

it('altera período e salva referências somente para estimativa identificada',async()=>{
  const mock=api();render(<ConsumptionModal api={mock} deviceId="home-ac" deviceName="Clima da casa" onClose={vi.fn()}/>);
  await screen.findByText(/Sem intervalos observados/);
  fireEvent.change(screen.getByLabelText('Período'),{target:{value:'30'}});
  await waitFor(()=>expect(mock.consumption).toHaveBeenCalledTimes(2));
  expect(screen.getByRole('group',{name:'Gráfico de barras de tempo observado ligado'})).toBeTruthy();
  fireEvent.click(screen.getByText('Referências para estimar energia e custo'));
  fireEvent.change(screen.getByLabelText('Potência elétrica de referência (W)'),{target:{value:'1200'}});
  fireEvent.change(screen.getByLabelText('Tarifa de referência (R$/kWh)'),{target:{value:'1.1'}});
  fireEvent.click(screen.getByRole('button',{name:'Salvar referências'}));
  await waitFor(()=>expect(mock.saveConsumptionSettings).toHaveBeenCalledWith('home-ac',{reference_watts:1200,tariff_per_kwh:1.1}));
});

it('diferencia estimativa, cobertura e falha de coleta',async()=>{
  const result=consumptionFixture();result.totals={...result.totals,on_seconds:3600,coverage_percent:50,estimated_kwh:1.2,estimated_cost:1.27};
  result.settings.reference_watts=1200;result.energy_source='reference_estimate';result.collector.status='storage_error';
  render(<ConsumptionModal api={api(result)} deviceId="home-ac" deviceName="Clima da casa" onClose={vi.fn()}/>);
  expect(await screen.findByText('1,200 kWh')).toBeTruthy();
  expect(screen.getByText(/Falha ao guardar leituras/)).toBeTruthy();
  expect(screen.getByText('50,0%')).toBeTruthy();
  expect(screen.getByText('Estimativa pela potência de referência')).toBeTruthy();
});

it('informa erro de backend e permite fechar sem comandar o aparelho',async()=>{
  const mock=api(),close=vi.fn();mock.consumption.mockRejectedValue(new Error('Histórico temporariamente indisponível.'));
  render(<ConsumptionModal api={mock} deviceId="home-ac" deviceName="Clima da casa" onClose={close}/>);
  expect(await screen.findByText('Histórico temporariamente indisponível.')).toBeTruthy();
  fireEvent.click(screen.getByRole('button',{name:'Fechar consumo'}));expect(close).toHaveBeenCalledTimes(1);
});

it('oferece voltar e devolve foco ao elemento que abriu Consumo',async()=>{
  const opener=document.createElement('button');opener.textContent='Abrir Consumo';document.body.appendChild(opener);opener.focus();
  const close=vi.fn(),view=render(<ConsumptionModal api={api()} deviceId="home-ac" deviceName="Clima da casa" onClose={close}/>);
  await screen.findByText(/Sem intervalos observados/);
  fireEvent.click(screen.getByRole('button',{name:'Voltar ao controle'}));expect(close).toHaveBeenCalledTimes(1);
  view.unmount();expect(document.activeElement).toBe(opener);opener.remove();
});
