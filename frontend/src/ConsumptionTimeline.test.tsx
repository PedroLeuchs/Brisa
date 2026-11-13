import {afterEach,expect,it,vi} from 'vitest';
import {cleanup,fireEvent,render,screen,within} from '@testing-library/react';
import {ConsumptionTimeline} from './ConsumptionTimeline';
import type {ConsumptionTimelineData} from './consumptionTypes';

afterEach(()=>{cleanup();vi.restoreAllMocks();});
const midnight=Date.parse('2026-10-23T00:00:00-03:00')/1000;
function fixture():ConsumptionTimelineData{return {date:'2026-10-23',start:midnight,end:midnight+15*3600,ends_at_now:true,sampling_seconds:60,transitions:[{start:midnight+8*3600,end:midnight+8*3600+60,from:'on',to:'off'}],segments:[
  {start:midnight,end:midnight+7*3600,state:'unknown'},
  {start:midnight+7*3600,end:midnight+8*3600,state:'on'},
  {start:midnight+8*3600,end:midnight+8*3600+60,state:'unknown'},
  {start:midnight+8*3600+60,end:midnight+15*3600,state:'off'}]};}

it('desenha linha em degraus com eixos de estado e horário, sem faixas coloridas',()=>{
  render(<ConsumptionTimeline timeline={fixture()}/>);
  const graph=screen.getByRole('group',{name:'Gráfico diário de estado em degraus'});
  expect(within(graph).getAllByRole('button')).toHaveLength(5);
  expect(within(graph).getByRole('button',{name:/Ligado · 07:00:00 a 08:00:00/}).tagName.toLowerCase()).toBe('path');
  expect(within(graph).getByRole('button',{name:/Desligado · 08:01:00/}).getAttribute('d')).toContain('145 H');
  expect(within(graph).getByRole('button',{name:/Mudança para desligado/}).getAttribute('d')).toMatch(/H .* V 145/);
  expect(within(graph).getByRole('button',{name:/Sem observação · 00:00:00/}).getAttribute('fill')).toBe('transparent');
  expect(within(graph).getByText('Ligado')).toBeTruthy();expect(within(graph).getByText('Desligado')).toBeTruthy();
  expect(within(graph).getByText('00:00')).toBeTruthy();expect(within(graph).getByText('Agora 15:00')).toBeTruthy();
  expect(within(graph).queryByText('24:00')).toBeNull();expect(screen.getByText(/não curva de watts/)).toBeTruthy();
});

it('permite toque, foco/teclado e seleção de segmentos curtos com início, fim e duração',()=>{
  render(<ConsumptionTimeline timeline={fixture()}/>);
  const graph=screen.getByRole('group',{name:'Gráfico diário de estado em degraus'});
  fireEvent.click(within(graph).getByRole('button',{name:/Ligado · 07:00:00/}));
  expect(screen.getByText('De 07:00:00 até 08:00:00 · 1h 0min 0s')).toBeTruthy();
  fireEvent.change(screen.getByLabelText('Detalhes do intervalo'),{target:{value:'s-2'}});
  expect(screen.getByText('De 08:00:00 até 08:01:00 · 1min 0s')).toBeTruthy();
  expect(screen.getByText(/A linha não atravessa esta lacuna/)).toBeTruthy();
  fireEvent.change(screen.getByLabelText('Detalhes do intervalo'),{target:{value:'t-0'}});
  expect(screen.getByText(/O instante exato do acionamento não é conhecido/)).toBeTruthy();
  fireEvent.keyDown(within(graph).getByRole('button',{name:/Desligado · 08:01:00/}),{key:'Enter'});
  expect(screen.getByText(/De 08:01:00 até 15:00:00/)).toBeTruthy();
});

it('mantém eixo legível no mobile e permite selecionar pela posição de toque',()=>{
  vi.spyOn(Element.prototype,'getBoundingClientRect').mockReturnValue({width:320,height:154,left:0,top:0,right:320,bottom:154,x:0,y:0,toJSON(){}});
  render(<ConsumptionTimeline timeline={fixture()}/>);
  const graph=screen.getByRole('group',{name:'Gráfico diário de estado em degraus'});
  expect(graph.getAttribute('viewBox')).toBe('0 0 320 222');
  // O seletor continua acessível para intervalos estreitos demais para um dedo.
  expect(screen.getByLabelText('Detalhes do intervalo')).toBeTruthy();
  fireEvent.focus(within(graph).getByRole('button',{name:/Ligado · 07:00:00/}));
  expect(screen.getByText(/De 07:00:00 até 08:00:00/)).toBeTruthy();
  expect(graph.querySelector('text')?.getAttribute('class')).toContain('chart-axis');
});
