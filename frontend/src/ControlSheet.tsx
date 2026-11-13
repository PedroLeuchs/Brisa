import {useEffect,useId,useRef} from 'react';
import type {ReactNode} from 'react';

export function ControlSheet({open,title,onClose,children}:{open:boolean;title:string;onClose:()=>void;children:ReactNode}){
  const ref=useRef<HTMLDialogElement>(null),titleId=useId();
  useEffect(()=>{
    const dialog=ref.current;if(!dialog)return;
    if(open&&!dialog.open){if(typeof dialog.showModal==='function')dialog.showModal();else dialog.setAttribute('open','');}
    if(!open&&dialog.open){if(typeof dialog.close==='function')dialog.close();else dialog.removeAttribute('open');}
  },[open]);
  return <dialog ref={ref} className="control-sheet" aria-labelledby={titleId} onCancel={event=>{event.preventDefault();onClose();}}
    onClick={event=>{if(event.target!==event.currentTarget)return;const r=event.currentTarget.getBoundingClientRect();if(event.clientX<r.left||event.clientX>r.right||event.clientY<r.top||event.clientY>r.bottom)onClose();}}>
    <div className="sheet-grip" aria-hidden="true"/>
    <div className="sheet-heading"><div><p className="eyebrow">AJUSTE SEU CONFORTO</p><h2 id={titleId}>{title}</h2></div><button className="quiet" aria-label="Fechar opções" onClick={onClose}>✕</button></div>
    {children}
  </dialog>;
}
