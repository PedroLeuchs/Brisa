import {expect,it} from 'vitest';
import {climatePresentation} from './climateTheme';

it.each([
  [false,'cold','off','Desligado'],
  [true,'cold','cold','Ligado · Resfriar'],
  [true,'hot','hot','Ligado · Aquecer'],
  [true,'auto','default','Ligado · Automático'],
] as const)('deriva tema %s/%s somente da leitura confirmada', (power,mode,theme,label)=>{
  expect(climatePresentation('online','idle',power,mode)).toEqual({theme,label});
});

it('não apresenta cor de modo durante confirmação nem com estado antigo',()=>{
  expect(climatePresentation('online','confirming',true,'hot')).toEqual({theme:'pending',label:'Confirmando alteração…'});
  expect(climatePresentation('offline','idle',true,'cold')).toEqual({theme:'stale',label:'Sem confirmação atual · último: ligado · resfriar'});
});
