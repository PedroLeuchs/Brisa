import {useEffect,useRef,useState} from 'react';
import type {FormEvent} from 'react';
import type {Automation,AutomationApi,AutomationEntryPayload,DeviceInfo,FunctionCode,RoutinePayload} from './types';
import {actionNames,conflict,dayNames,defaultValue,describe,newEntry,optionName,routineEntries,routinePayload} from './routineForm';
import './routines.css';

export function AutomationModal({api,devices,onClose}:{api:AutomationApi;devices:DeviceInfo[];onClose:()=>void}){
  const initial=devices[0],dialog=useRef<HTMLElement>(null),close=useRef<HTMLButtonElement>(null);
  const fresh=():RoutinePayload=>({name:'Rotina de climatização',device_id:initial.id,entries:[newEntry(initial)],days:[0,1,2,3,4],enabled:true});
  const [items,setItems]=useState<Automation[]>([]),[editing,setEditing]=useState<string|null>(null);
  const [form,setForm]=useState<RoutinePayload>(fresh);
  const [loading,setLoading]=useState(true),[saving,setSaving]=useState(false),[message,setMessage]=useState('');
  const [mobile,setMobile]=useState(()=>window.matchMedia?.('(max-width: 700px)').matches??false);
  const device=devices.find(item=>item.id===form.device_id)??initial;
  const actions=Object.keys(device.capabilities) as FunctionCode[];
  const duplicate=conflict(form.entries);
  useEffect(()=>{
    const before=document.activeElement as HTMLElement|null,overflow=document.body.style.overflow;
    document.body.style.overflow='hidden';close.current?.focus();
    const query=window.matchMedia?.('(max-width: 700px)');
    const resize=()=>query&&setMobile(query.matches);query?.addEventListener('change',resize);
    return()=>{document.body.style.overflow=overflow;query?.removeEventListener('change',resize);if(before?.isConnected)before.focus();};
  },[]);
  const load=async()=>{
    setLoading(true);
    try{const result=await api.automations();setItems(result.automations);if(result.scheduler?.status==='degraded')setMessage(result.scheduler.message??'A agenda está temporariamente indisponível.');return true;}
    catch(error){setMessage(error instanceof Error?error.message:'Não foi possível carregar as rotinas.');return false;}
    finally{setLoading(false);}
  };
  useEffect(()=>{void load();},[]);
  const reset=()=>{setEditing(null);setForm(fresh());};
  const changeEntry=(index:number,changes:Partial<AutomationEntryPayload>)=>setForm(previous=>({...previous,entries:previous.entries.map((entry,i)=>i===index?{...entry,...changes}:entry)}));
  const changeDevice=(id:string)=>{
    const next=devices.find(item=>item.id===id)??initial;
    setForm(previous=>({...previous,device_id:id,entries:previous.entries.map(entry=>next.capabilities[entry.code]?entry:{...entry,code:(Object.keys(next.capabilities)[0]??'switch') as FunctionCode,value:defaultValue(next.capabilities[(Object.keys(next.capabilities)[0]??'switch') as FunctionCode])})}));
  };
  const save=async(event:FormEvent)=>{
    event.preventDefault();if(duplicate){setMessage(duplicate);return;}
    setSaving(true);setMessage('');
    try{if(editing)await api.updateAutomation(editing,form);else await api.createAutomation(form);if(await load())reset();}
    catch(error){setMessage(error instanceof Error?error.message:'Não foi possível salvar a rotina.');}
    finally{setSaving(false);}
  };
  const edit=(item:Automation)=>{setEditing(item.id);setForm(routinePayload(item));setMessage('');};
  const toggle=async(item:Automation)=>{
    setSaving(true);setMessage('');
    try{await api.updateAutomation(item.id,{...routinePayload(item),enabled:!item.enabled});await load();if(editing===item.id)setForm(previous=>({...previous,enabled:!item.enabled}));}
    catch(error){setMessage(error instanceof Error?error.message:'Não foi possível alterar a rotina.');}
    finally{setSaving(false);}
  };
  const remove=async(item:Automation)=>{
    if(!window.confirm('Excluir esta rotina e todos os seus horários?'))return;
    setSaving(true);setMessage('');
    try{await api.deleteAutomation(item.id);await load();if(editing===item.id)reset();}
    catch(error){setMessage(error instanceof Error?error.message:'Não foi possível excluir a rotina.');}
    finally{setSaving(false);}
  };
  return <div className={`modal-backdrop automation-overlay ${mobile?'routine-mobile':''}`} onMouseDown={event=>{if(event.target===event.currentTarget&&!saving)onClose();}}>
    <section ref={dialog} className="automation-modal card automation-routines" role="dialog" aria-modal="true" aria-labelledby="automation-title" onKeyDown={event=>{
      if(event.key==='Escape'&&!saving){event.preventDefault();onClose();}
      if(event.key==='Tab'){
        const controls=Array.from(dialog.current?.querySelectorAll<HTMLElement>('button:not(:disabled),input:not(:disabled),select:not(:disabled),[tabindex="0"]')??[]);
        const first=controls[0],last=controls[controls.length-1];
        if(event.shiftKey&&document.activeElement===first){event.preventDefault();last?.focus();}
        else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first?.focus();}
      }
    }}>
      <div className="routine-screen-header"><button ref={close} className="quiet routine-back" disabled={saving} aria-label={mobile?'Voltar ao controle':'Fechar automações'} onClick={onClose}>{mobile?'← Voltar':'✕'}</button><div><p className="eyebrow">ROTINAS SEMANAIS</p><h2 id="automation-title">Automações</h2></div></div>
      <div className="routine-scroll"><p className="hint">Vários horários na mesma rotina, no horário de Brasília. O servidor precisa permanecer ligado.</p>
        {loading?<p role="status">Carregando…</p>:<div className="automation-list">{items.length===0?<p className="muted">Nenhuma rotina criada.</p>:items.map(item=><article className={`automation-item routine-summary ${item.enabled?'':'paused'}`} key={item.id}>
          <div className="routine-summary-main"><div className="routine-summary-title"><strong>{item.name??'Rotina de climatização'}</strong><span>{item.enabled?'Ativa':'Pausada'}</span></div><p className="hint">{item.days.map(day=>dayNames[day]).join(', ')} · {routineEntries(item).length} horário(s)</p>
            <ol className="routine-timeline">{routineEntries(item).map((entry,i)=><li key={entry.id??i}><strong>{entry.time}</strong><span>{describe(entry)}</span>{item.entries?.[i]?.last_result?.status==='offline'&&<small>Sem resposta na última execução; não será repetida.</small>}{item.entries?.[i]?.last_result?.status==='uncertain'&&<small>Última execução sem confirmação; não será repetida.</small>}</li>)}</ol>
          </div><div className="automation-actions"><button onClick={()=>void toggle(item)} disabled={saving}>{item.enabled?'Pausar':'Ativar'}</button><button onClick={()=>edit(item)} disabled={saving}>Editar</button><button onClick={()=>void remove(item)} disabled={saving}>Excluir</button></div>
        </article>)}</div>}
        <form className="automation-form" onSubmit={save}><h3>{editing?'Editar rotina':'Nova rotina'}</h3>
          <label>Nome da rotina<input aria-label="Nome da rotina" className="routine-name" required maxLength={80} value={form.name} disabled={saving} onChange={event=>setForm({...form,name:event.target.value})}/></label>
          {devices.length>1&&<label>Ambiente<select aria-label="Ambiente da rotina" value={form.device_id} disabled={saving} onChange={event=>changeDevice(event.target.value)}>{devices.map(item=><option key={item.id} value={item.id}>{item.name}</option>)}</select></label>}
          <fieldset className="routine-days"><legend>Dias de repetição da rotina</legend><div className="day-picker">{dayNames.map((name,day)=><label key={name}><input type="checkbox" checked={form.days.includes(day)} disabled={saving} onChange={()=>setForm({...form,days:form.days.includes(day)?form.days.filter(value=>value!==day):[...form.days,day].sort()})}/><span>{name}</span></label>)}</div></fieldset>
          <label className="routine-enabled"><input type="checkbox" checked={form.enabled} disabled={saving} onChange={event=>setForm({...form,enabled:event.target.checked})}/> Rotina ativa</label>
          <div className="routine-entries">{form.entries.map((entry,index)=>{
            const capability=device.capabilities[entry.code],n=index+1;
            return <fieldset className="routine-entry" key={entry.id??`legacy-${index}`}><legend>Horário {n}</legend><div className="routine-entry-header"><span>Defina uma ação para este horário</span><button type="button" className="quiet" aria-label={`Remover horário ${n}`} disabled={saving||form.entries.length===1} onClick={()=>setForm({...form,entries:form.entries.filter((_,i)=>i!==index)})}>Remover</button></div>
              <div className="form-grid"><label>Horário<input aria-label={`Horário ${n}`} type="time" required value={entry.time} disabled={saving} onChange={event=>changeEntry(index,{time:event.target.value})}/></label>
                <label>Ação<select aria-label={`Ação do horário ${n}`} value={entry.code} disabled={saving} onChange={event=>{const code=event.target.value as FunctionCode;changeEntry(index,{code,value:defaultValue(device.capabilities[code])});}}>{actions.map(code=><option key={code} value={code}>{actionNames[code]}</option>)}</select></label>
                <label>Valor{capability?.type==='bool'?<select aria-label={`Valor do horário ${n}`} value={String(entry.value)} disabled={saving} onChange={event=>changeEntry(index,{value:event.target.value==='true'})}><option value="true">{entry.code==='switch'?'Ligar':'Ativar'}</option><option value="false">{entry.code==='switch'?'Desligar':'Desativar'}</option></select>:capability?.type==='enum'?<select aria-label={`Valor do horário ${n}`} value={String(entry.value)} disabled={saving} onChange={event=>changeEntry(index,{value:event.target.value})}>{capability.values?.map(value=><option key={String(value)} value={String(value)}>{optionName(value)}</option>)}</select>:<input aria-label={`Valor do horário ${n}`} type="number" required min={capability?.values?.[0] as number} max={capability?.values?.[1] as number} step={capability?.step??1} value={Number(entry.value)} disabled={saving} onChange={event=>changeEntry(index,{value:Number(event.target.value)})}/>}</label></div>
            </fieldset>;
          })}</div>
          <button className="add-routine-time" type="button" disabled={saving||form.entries.length>=16} onClick={()=>setForm({...form,entries:[...form.entries,newEntry(device)]})}>+ Adicionar horário</button>
          <p className="hint">Até 16 horários. Ações diferentes no mesmo minuto seguem a ordem mostrada. A mesma ação não pode se repetir nem ter valores conflitantes no mesmo horário.</p>
          {duplicate&&<p className="notice" role="status">{duplicate}</p>}
          <div className="form-buttons"><button className="primary" type="submit" disabled={saving||form.days.length===0||!!duplicate}>{saving?'Salvando…':editing?'Salvar alterações':'Criar rotina'}</button>{editing&&<button type="button" disabled={saving} onClick={reset}>Cancelar edição</button>}</div>
        </form>{message&&<p className="notice" role="status">{message}</p>}
      </div>
    </section></div>;
}
