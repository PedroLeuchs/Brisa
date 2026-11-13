const $ = id => document.getElementById(id);
let state = {}, available = [], busy = false, signedIn = false, timer;
let online = false, failures = 0, lastCommand = 0, checkingSession = false;
function notice(message = '') { $('notice').textContent = message; $('notice').hidden = !message; }
async function api(path, body) {
  const abort = new AbortController();
  const timeout = setTimeout(() => abort.abort(), 20000);
  try {
    const response = await fetch('/api/' + path, {method: body ? 'POST' : 'GET', credentials: 'same-origin', cache: 'no-store', signal: abort.signal, headers: body ? {'Content-Type': 'application/json', 'X-Ar-Request': '1'} : {}, body: body ? JSON.stringify(body) : undefined});
    const data = await response.json();
    if (!response.ok) {
      if (response.status === 401 && path !== 'login') showLogin();
      const error = new Error(typeof data.detail === 'string' ? data.detail : 'Não foi possível concluir o pedido.');
      error.status = response.status;
      throw error;
    }
    return data;
  } catch (error) {
    if (error.name === 'AbortError') throw new Error('O pedido demorou demais. Tentando reconectar…');
    if (error instanceof TypeError) throw new Error('Conexão interrompida. Tentando reconectar…');
    throw error;
  } finally { clearTimeout(timeout); }
}
function showLogin() { signedIn = false; online = false; clearTimeout(timer); $('login').hidden = false; $('dashboard').hidden = true; $('logout').hidden = true; }
function showDashboard() { signedIn = true; $('login').hidden = true; $('dashboard').hidden = false; $('logout').hidden = false; }
function controls(enabled) {
  enabled = enabled && signedIn && online;
  document.querySelectorAll('[data-code]').forEach(el => { el.disabled = !enabled || !available.includes(el.dataset.code) || !(el.dataset.code in state); });
  $('power').disabled = !enabled || !available.includes('switch') || typeof state.switch !== 'boolean';
  for (const id of ['decrease', 'increase']) $(id).disabled = !enabled || !available.includes('temp_set') || !Number.isInteger(state.temp_set) || (id === 'decrease' ? state.temp_set <= 16 : state.temp_set >= 31);
}
function render(data) {
  state = data.state; available = data.available; online = true; failures = 0;
  $('temperature').textContent = Number.isInteger(state.temp_set) ? state.temp_set : '—';
  $('power').setAttribute('aria-pressed', state.switch === true ? 'true' : 'false');
  $('power-label').textContent = state.switch === true ? 'Ar ligado' : state.switch === false ? 'Ar desligado' : 'Funções aguardando configuração';
  document.querySelectorAll('[data-code]').forEach(el => {
    const value = state[el.dataset.code];
    if (el.type === 'checkbox') el.checked = value === true;
    else if (value !== undefined) el.value = value;
  });
  $('dps').textContent = JSON.stringify(data.dps, null, 2);
  $('updated').textContent = 'Lido às ' + new Date(data.timestamp * 1000).toLocaleTimeString('pt-BR');
  $('connection').textContent = '● Conectado na rede';
}
function disconnected(error) {
  online = false; failures++;
  $('connection').textContent = '○ Reconectando…';
  $('power-label').textContent = 'Última leitura · conexão interrompida';
  notice(error.message);
}
async function readStatus() {
  render(await api('status'));
  notice(available.length ? '' : 'Conexão estabelecida. Configure as funções em mapping.json para liberar os controles.');
}
async function refresh() {
  if (busy || !signedIn) return;
  clearTimeout(timer); busy = true; controls(false); $('refresh').disabled = true;
  try { await readStatus(); }
  catch (error) { disconnected(error); }
  finally { busy = false; controls(true); $('refresh').disabled = false; schedule(); }
}
function schedule() {
  clearTimeout(timer);
  const delay = online ? 15000 : Math.min(10000, 2000 * 2 ** Math.max(0, Math.min(failures - 1, 3)));
  if (signedIn) timer = setTimeout(refresh, delay);
}
const pause = milliseconds => new Promise(resolve => setTimeout(resolve, milliseconds));
async function send(code, value) {
  if (busy || !signedIn || !online) return;
  clearTimeout(timer); busy = true; controls(false); $('refresh').disabled = true;
  let commandError;
  try {
    notice('Enviando ao aparelho…');
    await pause(Math.max(0, 1100 - (Date.now() - lastCommand)));
    lastCommand = Date.now();
    try { await api('command', {code, value}); }
    catch (error) { commandError = error; }
    if (!signedIn) return;
    // Confirma pela leitura mesmo se o envio não teve resposta. Não repete escritas.
    notice('Confirmando estado do aparelho…');
    await pause(350);
    await readStatus();
    if (commandError) notice('O envio não foi confirmado. O painel mostra o estado lido agora; confira antes de tentar novamente.');
  } catch (error) { disconnected(error); }
  finally {
    await pause(Math.max(0, 1100 - (Date.now() - lastCommand)));
    busy = false; controls(true); $('refresh').disabled = false; schedule();
  }
}
$('login-form').addEventListener('submit', async event => {
  event.preventDefault(); const button = event.submitter; button.disabled = true;
  try { await api('login', {password: $('password').value}); $('password').value = ''; notice(); showDashboard(); await refresh(); }
  catch (error) { notice(error.message); }
  finally { button.disabled = false; }
});
$('logout').onclick = async () => { try { await api('logout', {}); showLogin(); notice(); } catch (error) { notice(error.message); } };
$('power').onclick = () => send('switch', !state.switch);
$('decrease').onclick = () => send('temp_set', state.temp_set - 1);
$('increase').onclick = () => send('temp_set', state.temp_set + 1);
$('refresh').onclick = refresh;
document.querySelectorAll('[data-code]').forEach(el => el.onchange = () => { const value = el.type === 'checkbox' ? el.checked : el.value; if (el.type === 'checkbox') el.checked = state[el.dataset.code] === true; else el.value = state[el.dataset.code]; send(el.dataset.code, value); });
document.addEventListener('visibilitychange', () => { if (!document.hidden) { if (signedIn) refresh(); else resume(); } });
window.addEventListener('online', () => { if (signedIn) refresh(); else resume(); });
async function resume() {
  if (checkingSession || signedIn) return;
  checkingSession = true;
  try { await api('session'); showDashboard(); await refresh(); }
  catch (error) { if (error.status !== 401) { notice(error.message); clearTimeout(timer); timer = setTimeout(resume, 5000); } }
  finally { checkingSession = false; }
}
resume();
if ('serviceWorker' in navigator && window.isSecureContext) navigator.serviceWorker.register('/sw.js').catch(() => {});
