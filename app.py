import hashlib
import hmac
import os
import secrets
import threading
import time
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware
from controller import Controller, ControllerError
from backend.adapters.tuya_local import TuyaLocalAdapter
from backend.adapters.tuya_cloud import TuyaCloudController, TuyaCloudAdapter
from backend.services.devices import DeviceService
from backend.services.automations import AutomationError, AutomationService, AutomationStore
from backend.services.sessions import SessionStore
from backend.services.consumption import ConsumptionCollector, ConsumptionStore
from backend.consumption_api import consumption_router

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / '.env')
app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1,192.168.1.5').split(','))
if os.getenv('TUYA_TRANSPORT', 'local').lower() == 'cloud':
    controller = TuyaCloudController()
    devices = DeviceService(TuyaCloudAdapter(controller))
else:
    controller = Controller()
    devices = DeviceService(TuyaLocalAdapter(controller))
automations = AutomationService(AutomationStore(ROOT / 'data' / 'automations.json'), devices)
consumption = ConsumptionCollector(ConsumptionStore(ROOT / 'data' / 'consumption.sqlite3'), devices)
sessions = SessionStore(ROOT / 'data' / 'sessions.sqlite3')
attempts = []
auth_lock = threading.Lock()
TTL = 60 * 60 * 12
REMEMBER_TTL = 60 * 60 * 24 * 30

@app.on_event('startup')
def start_automations():
    automations.start()
    consumption.start()

@app.on_event('shutdown')
def stop_automations():
    consumption.stop()
    automations.stop()

@app.middleware('http')
async def protect(request: Request, call_next):
    if request.method not in ('GET', 'HEAD'):
        origin = request.headers.get('origin')
        expected = f'{request.url.scheme}://{request.headers.get("host", "")}'
        if origin != expected or request.headers.get('x-ar-request') != '1':
            return JSONResponse({'detail': 'Origem inválida.'}, status_code=403)
        length = request.headers.get('content-length', '0')
        if not length.isdigit() or int(length) > 4096:
            return JSONResponse({'detail': 'Pedido grande demais.'}, status_code=413)
    response = await call_next(request)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'no-referrer'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
    if request.url.path.startswith('/api/'):
        response.headers['Cache-Control'] = 'no-store'
    return response

def authorized(request):
    token = request.cookies.get('ar_session', '')
    with auth_lock:
        if not sessions.valid(token, os.getenv('APP_PASSWORD_HASH', '')):
            raise HTTPException(401, 'Entre com a senha do controlador.')

@app.post('/api/login')
async def login(request: Request):
    with auth_lock:
        now = time.time()
        attempts[:] = [t for t in attempts if t > now - 60]
        if len(attempts) >= 5:
            raise HTTPException(429, 'Aguarde um minuto para tentar novamente.')
        attempts.append(now)
    try:
        body = await request.json()
    except ValueError:
        raise HTTPException(400, 'Pedido inválido.') from None
    if not isinstance(body, dict):
        raise HTTPException(400, 'Pedido inválido.')
    password = body.get('password', '')
    remember = body.get('remember', False)
    if type(remember) is not bool:
        raise HTTPException(400, 'Preferência de acesso inválida.')
    if not isinstance(password, str) or len(password) > 256:
        raise HTTPException(400, 'Senha inválida.')
    stored = os.getenv('APP_PASSWORD_HASH', '')
    try:
        salt, expected = stored.split(':')
        actual = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()
    except (ValueError, TypeError):
        raise HTTPException(503, 'Execute setup.py no computador para configurar sua senha.') from None
    if not hmac.compare_digest(actual, expected):
        raise HTTPException(401, 'Senha incorreta.')
    token = secrets.token_urlsafe(32)
    ttl = REMEMBER_TTL if remember else TTL
    with auth_lock:
        sessions.revoke(request.cookies.get('ar_session', ''))
        sessions.issue(token, time.time() + ttl, stored)
    response = JSONResponse({'ok': True, 'expires_at': time.time() + ttl, 'remembered': remember})
    response.set_cookie('ar_session', token, httponly=True, samesite='strict',
                        secure=os.getenv('COOKIE_SECURE', 'false').lower() == 'true', max_age=ttl)
    return response

@app.post('/api/logout')
def logout(request: Request):
    with auth_lock:
        sessions.revoke(request.cookies.get('ar_session', ''))
    response = JSONResponse({'ok': True})
    response.delete_cookie('ar_session')
    return response

@app.get('/api/status')
def status(request: Request):
    authorized(request)
    try:
        return controller.status()
    except ControllerError as exc:
        raise HTTPException(503, str(exc)) from None
    except Exception:
        raise HTTPException(503, 'Falha na comunicação local. Revise a configuração no computador.') from None

@app.get('/api/session')
def session(request: Request):
    authorized(request)
    return {'ok': True}

@app.post('/api/command')
async def command(request: Request):
    authorized(request)
    try:
        body = await request.json()
    except ValueError:
        raise HTTPException(400, 'Pedido inválido.') from None
    if not isinstance(body, dict) or set(body) != {'code', 'value'} or not isinstance(body['code'], str):
        raise HTTPException(422, 'Comando inválido.')
    from starlette.concurrency import run_in_threadpool
    try:
        return await run_in_threadpool(controller.command, body['code'], body['value'])
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    except ControllerError as exc:
        raise HTTPException(503, str(exc)) from None
    except Exception:
        raise HTTPException(503, 'Falha ao enviar comando local.') from None

@app.get('/')
def index():
    path = ROOT / 'frontend' / 'dist' / 'index.html'
    return FileResponse(path if path.exists() else ROOT / 'static' / 'index.html', headers={'Cache-Control':'no-cache'})

@app.get('/sw.js')
def worker():
    path = ROOT / 'frontend' / 'dist' / 'sw.js'
    return FileResponse(path if path.exists() else ROOT / 'static' / 'sw.js', media_type='application/javascript', headers={'Cache-Control': 'no-cache'})

@app.get('/api/devices')
def catalog(request: Request):
    authorized(request)
    try:
        return {'devices': devices.list()}
    except Exception:
        raise HTTPException(503, 'Não foi possível carregar os aparelhos configurados.') from None

@app.get('/api/devices/{device_id}/status')
def device_status(device_id: str, request: Request):
    authorized(request)
    try:
        return devices.status(device_id)
    except KeyError:
        raise HTTPException(404, 'Aparelho não encontrado.') from None
    except ControllerError as exc:
        raise HTTPException(503, str(exc)) from None
    except Exception:
        raise HTTPException(503, 'Sem resposta do aparelho. Tentando reconectar.') from None

@app.post('/api/devices/{device_id}/command')
async def device_command(device_id: str, request: Request):
    authorized(request)
    try:
        devices.adapter(device_id)
    except KeyError:
        raise HTTPException(404, 'Aparelho não encontrado.') from None
    try:
        body = await request.json()
    except ValueError:
        raise HTTPException(400, 'Pedido inválido.') from None
    if not isinstance(body, dict) or set(body) != {'code','value'} or not isinstance(body['code'],str):
        raise HTTPException(422, 'Comando inválido.')
    from starlette.concurrency import run_in_threadpool
    try:
        return await run_in_threadpool(devices.command, device_id, body['code'], body['value'])
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    except ControllerError as exc:
        raise HTTPException(503, str(exc)) from None
    except Exception:
        raise HTTPException(503, 'Envio sem confirmação. Consulte o estado antes de tentar novamente.') from None

@app.get('/api/automations')
def list_automations(request: Request):
    authorized(request)
    try:
        items = automations.list()
    except Exception:
        raise HTTPException(503, 'Não foi possível ler as rotinas. Consulte o diagnóstico da agenda.') from None
    return {'automations': items, 'timezone': 'America/Sao_Paulo', 'scheduler': automations.diagnostic()}

@app.get('/api/automations/health')
def automation_health(request: Request):
    authorized(request)
    return automations.diagnostic()

async def automation_payload(request: Request):
    try:
        body = await request.json()
    except ValueError:
        raise HTTPException(400, 'Pedido inválido.') from None
    if not isinstance(body, dict):
        raise HTTPException(422, 'Automação inválida.')
    return body

@app.post('/api/automations')
async def create_automation(request: Request):
    authorized(request)
    try:
        return automations.create(await automation_payload(request))
    except AutomationError as exc:
        status = 409 if str(exc).startswith('Já existe') else 422
        raise HTTPException(status, str(exc)) from None
    except (OSError, RuntimeError):
        raise HTTPException(503, 'Não foi possível salvar a rotina. Verifique o armazenamento local.') from None

@app.post('/api/automations/{automation_id}')
async def update_automation(automation_id: str, request: Request):
    authorized(request)
    try:
        return automations.update(automation_id, await automation_payload(request))
    except KeyError:
        raise HTTPException(404, 'Automação não encontrada.') from None
    except AutomationError as exc:
        status = 409 if str(exc).startswith('Já existe') else 422
        raise HTTPException(status, str(exc)) from None
    except (OSError, RuntimeError):
        raise HTTPException(503, 'Não foi possível salvar a rotina. Verifique o armazenamento local.') from None

@app.post('/api/automations/{automation_id}/delete')
def delete_automation(automation_id: str, request: Request):
    authorized(request)
    try:
        automations.delete(automation_id)
        return {'ok': True}
    except KeyError:
        raise HTTPException(404, 'Automação não encontrada.') from None
    except (OSError, RuntimeError):
        raise HTTPException(503, 'Não foi possível excluir a rotina. Verifique o armazenamento local.') from None

app.include_router(consumption_router(consumption, devices, authorized))
app.mount('/assets', StaticFiles(directory=ROOT / 'static'), name='assets')
app.mount('/ui', StaticFiles(directory=ROOT / 'frontend' / 'dist', check_dir=False), name='frontend')
