import {afterEach,expect,it} from 'vitest';
import {cleanup,fireEvent,render,screen,within} from '@testing-library/react';
import {ConsumptionBars,consumptionBuckets} from './ConsumptionBars';
import type {ConsumptionDay} from './consumptionTypes';
afterEach(cleanup);
const days:ConsumptionDay[]=[
  {date:'2026-10-21',on_seconds:7200,off_seconds:3600,unknown_seconds:75600,coverage_percent:12.5},
  {date:'2026-10-22',on_seconds:0,off_seconds:0,unknown_seconds:86400,coverage_percent:0},
  {date:'2026-10-23',on_seconds:3600,off_seconds:7200,unknown_seconds:75600,coverage_percent:12.5}
];
it('semanal/mensal usa barras de horas observadas e distingue dia sem dados de zero uso',()=>{
  render(<ConsumptionBars days={days}/>);
  const graph=screen.getByRole('group',{name:'Gráfico de barras de tempo observado ligado'});
  expect(graph.querySelectorAll('rect.usage-bar')).toHaveLength(2);
  expect(within(graph).getByText('?')).toBeTruthy();
  expect(within(graph).getByText('2h')).toBeTruthy();
  fireEvent.change(screen.getByLabelText('Detalhes do dia ou grupo'),{target:{value:'1'}});
  expect(screen.getByText(/Sem dados; não equivale a zero uso/)).toBeTruthy();
  fireEvent.click(within(graph).getByRole('button',{name:/21\/10 · 2h 00min/}));
  expect(screen.getByText('2h 00min ligado observado · 1h 00min desligado')).toBeTruthy();
});
it('agrupa períodos longos em até sete dias sem perder somas nem lacunas',()=>{
  const long=Array.from({length:70},(_,index)=>({...days[0],date:new Date(Date.UTC(2026,0,1+index)).toISOString().slice(0,10)}));
  const buckets=consumptionBuckets(long);
  expect(buckets).toHaveLength(10);
  expect(buckets.reduce((sum,item)=>sum+item.on,0)).toBe(70*7200);
  expect(buckets[0].start).toBe('2026-01-01');expect(buckets[0].end).toBe('2026-01-07');
  expect(buckets[0].coverage).toBe(12.5);
});
