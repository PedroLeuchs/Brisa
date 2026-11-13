import {afterEach,expect,it,vi} from 'vitest';
import {cleanup,fireEvent,render,screen} from '@testing-library/react';
import {TemperatureControl} from './TemperatureControl';

afterEach(cleanup);
function setup(){
  const onCommit=vi.fn(),onInteraction=vi.fn();
  render(<TemperatureControl value={21} min={16} max={31} step={1} disabled={false} busy={false} online={true} power={false} onCommit={onCommit} onInteraction={onInteraction}/>);
  return {slider:screen.getByRole('slider'),onCommit,onInteraction};
}
it('mostra os graus durante arraste mas envia só a seleção final ao soltar',()=>{
  const {slider,onCommit}=setup();
  fireEvent.pointerDown(slider,{pointerId:1});
  fireEvent.change(slider,{target:{value:'24'}});fireEvent.change(slider,{target:{value:'27'}});
  expect(screen.getByText('27')).toBeTruthy();expect(screen.getByText('Solte para enviar ao aparelho')).toBeTruthy();expect(onCommit).not.toHaveBeenCalled();
  fireEvent.pointerUp(slider,{pointerId:1});
  expect(onCommit).toHaveBeenCalledTimes(1);expect(onCommit).toHaveBeenCalledWith(27);
});
it('cancelamento do gesto restaura leitura e não envia seleção parcial',()=>{
  const {slider,onCommit}=setup();fireEvent.pointerDown(slider,{pointerId:1});fireEvent.change(slider,{target:{value:'30'}});fireEvent.pointerCancel(slider);
  expect(onCommit).not.toHaveBeenCalled();expect((slider as HTMLInputElement).value).toBe('21');
});
it('teclado envia apenas ao terminar a tecla, respeitando o valor do range',()=>{
  const {slider,onCommit}=setup();fireEvent.keyDown(slider,{key:'End'});fireEvent.change(slider,{target:{value:'31'}});
  expect(onCommit).not.toHaveBeenCalled();fireEvent.keyUp(slider,{key:'End'});
  expect(onCommit).toHaveBeenCalledExactlyOnceWith(31);
});
it('mantém botões como alternativa acessível',()=>{
  const {onCommit}=setup();fireEvent.click(screen.getByRole('button',{name:'Aumentar temperatura'}));
  expect(onCommit).toHaveBeenCalledExactlyOnceWith(22);
});
it('aguarda confirmação real em vez de substituir o valor confirmado',()=>{
  const onCommit=vi.fn();
  const props={value:21,min:16,max:31,step:1,disabled:false,busy:false,online:true,power:false,onCommit};
  const {rerender}=render(<TemperatureControl {...props}/>);
  const slider=screen.getByRole('slider');fireEvent.pointerDown(slider,{pointerId:1});fireEvent.change(slider,{target:{value:'25'}});
  // A fase de envio é fornecida pelo controlador assim que o gesto termina.
  onCommit.mockImplementation(()=>rerender(<TemperatureControl {...props} busy={true} disabled={true}/>));
  fireEvent.pointerUp(slider,{pointerId:1});
  expect(screen.getByText('TEMPERATURA SOLICITADA')).toBeTruthy();expect(screen.getByText('25')).toBeTruthy();
  rerender(<TemperatureControl {...props} value={25}/>);
  expect(screen.getByText('Confirmado pelo aparelho: 25 °C')).toBeTruthy();
});
it('arraste circular percorre o anel mas emite apenas o valor final ao soltar',()=>{
  const onCommit=vi.fn();render(<TemperatureControl value={21} min={16} max={31} step={1} disabled={false} busy={false} online={true} power={false} onCommit={onCommit} variant="remote"/>);
  const dial=screen.getByTestId('temperature-dial');
  vi.spyOn(dial,'getBoundingClientRect').mockReturnValue({left:0,top:0,width:320,height:320,right:320,bottom:320,x:0,y:0,toJSON(){return {};}});
  const pointer=(type:string,x:number,y:number)=>{const event=new MouseEvent(type,{clientX:x,clientY:y,bubbles:true});Object.defineProperty(event,'pointerId',{value:1});fireEvent(dial,event);};
  pointer('pointerdown',32,160);pointer('pointermove',160,32);pointer('pointermove',288,160);
  expect(onCommit).not.toHaveBeenCalled();expect(screen.getByText('29')).toBeTruthy();
  pointer('pointerup',288,160);expect(onCommit).toHaveBeenCalledExactlyOnceWith(29);
});
it('cancelamento do anel não deixa comando parcial pendente',()=>{
  const onCommit=vi.fn();render(<TemperatureControl value={21} min={16} max={31} step={1} disabled={false} busy={false} online={true} power={false} onCommit={onCommit} variant="remote"/>);
  const dial=screen.getByTestId('temperature-dial');vi.spyOn(dial,'getBoundingClientRect').mockReturnValue({left:0,top:0,width:320,height:320,right:320,bottom:320,x:0,y:0,toJSON(){return {};}});
  const down=new MouseEvent('pointerdown',{clientX:288,clientY:160,bubbles:true});Object.defineProperty(down,'pointerId',{value:1});fireEvent(dial,down);fireEvent.pointerCancel(dial);
  expect(onCommit).not.toHaveBeenCalled();expect(screen.getByText('21')).toBeTruthy();
});
