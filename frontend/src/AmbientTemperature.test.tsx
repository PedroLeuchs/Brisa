import {afterEach,expect,it,vi} from 'vitest';
import {cleanup,render,screen} from '@testing-library/react';
import {AmbientTemperature} from './AmbientTemperature';

afterEach(()=>{cleanup();vi.useRealTimers();});
it('não confunde ausência do sensor validado com temperatura definida',()=>{
  render(<AmbientTemperature online={true}/>);
  expect(screen.getByText('Ambiente')).toBeTruthy();expect(screen.getByText('Indisponível')).toBeTruthy();
  expect(screen.getByText('Leitura do sensor ainda não validada')).toBeTruthy();
});
it('exibe apenas a leitura identificada como sensor em graus Celsius',()=>{
  vi.useFakeTimers();vi.setSystemTime(new Date('2026-10-23T23:30:00Z'));
  render(<AmbientTemperature online={true} reading={{available:true,value:22.1,unit:'°C',observed_at:Date.now()/1000,source:'device'}}/>);
  expect(screen.getByText('22,1 °C')).toBeTruthy();expect(screen.getByText('Sensor do ar-condicionado')).toBeTruthy();
  expect(screen.queryByText(/desatualizada/)).toBeNull();
});
it('mantém a última leitura identificada como desatualizada quando perde conexão',()=>{
  render(<AmbientTemperature online={false} reading={{available:true,value:22,unit:'°C',observed_at:Date.now()/1000,source:'device'}}/>);
  expect(screen.getByText('22 °C')).toBeTruthy();expect(screen.getByText(/Última leitura · desatualizada/)).toBeTruthy();
});
it('também sinaliza leitura antiga mesmo que o transporte esteja online',()=>{
  render(<AmbientTemperature online={true} reading={{available:true,value:22,unit:'°C',observed_at:Date.now()/1000-60,source:'device'}}/>);
  expect(screen.getByText(/desatualizada/)).toBeTruthy();
});
