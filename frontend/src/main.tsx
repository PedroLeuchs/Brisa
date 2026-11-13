import {createRoot} from 'react-dom/client';
import {App} from './App';
import './styles.css';
import './remote.css';

createRoot(document.getElementById('root')!).render(<App/>);
if('serviceWorker' in navigator && window.isSecureContext && import.meta.env.PROD){
  navigator.serviceWorker.register('/sw.js').catch(()=>{});
}
