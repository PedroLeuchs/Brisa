import {useEffect,useState} from 'react';
import type {SensorReading} from './types';
import './ambient.css';

export function AmbientTemperature({reading,online}:{reading?:SensorReading;online:boolean}){
  const [now,setNow]=useState(Date.now());
  useEffect(()=>{const timer=setInterval(()=>setNow(Date.now()),5000);return()=>clearInterval(timer);},[]);
  const known=reading?.available===true&&typeof reading.value==='number'&&Number.isFinite(reading.value)&&reading.unit==='°C'
    &&typeof reading.observed_at==='number'&&Number.isFinite(reading.observed_at);
  const stale=!online||(known&&now-reading!.observed_at!*1000>45000);
  const time=known?new Date(reading!.observed_at!*1000).toLocaleTimeString('pt-BR'):'';
  return <section aria-label="Temperatura ambiente" className={`ambient-reading ${stale?'ambient-stale':''}`}>
    <div><span className="ambient-label">Ambiente</span><p className="ambient-description">{known?'Sensor do ar-condicionado':'Leitura do sensor ainda não validada'}</p></div>
    <div className="ambient-result"><strong>{known?`${reading!.value!.toLocaleString('pt-BR',{maximumFractionDigits:6})} °C`:'Indisponível'}</strong>
      <span role="status">{known?`${stale?'Última leitura · desatualizada':'Lido'} às ${time}`:online?'Aguardando identificação do sensor':'Sem leitura confirmada'}</span></div>
  </section>;
}
