"""Relay independente. Sem importação do app doméstico, senha local ou TinyTuya."""
import os
from pathlib import Path
import threading
import time

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware

from remote.protocol import AgentResult, NewCommand
from remote.storage import RelayError, RelayStore


def create_app(store=None):
    store = store or RelayStore(os.getenv('BRISA_RELAY_DB', str(Path(__file__).parent/'runtime'/'relay.sqlite3')))
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=os.getenv('BRISA_RELAY_ALLOWED_HOSTS', 'localhost,127.0.0.1').split(','))
    attempts, lock = {}, threading.Lock()

    @app.exception_handler(RequestValidationError)
    async def invalid_payload(request, error):
        return JSONResponse({'detail':'Pedido inválido.'}, status_code=422)

    @app.exception_handler(RelayError)
    async def relay_error(request, error):
        return JSONResponse({'detail':error.message}, status_code=error.status)

    @app.middleware('http')
    async def headers(request, call_next):
        # API para agentes/BFF com bearer; não aceita a sessão doméstica como login público.
        if request.headers.get('origin'):
            return JSONResponse({'detail':'Use um cliente autorizado do relay.'}, status_code=403)
        length = request.headers.get('content-length', '0')
        if not length.isdigit() or int(length)>4096:
            return JSONResponse({'detail':'Pedido grande demais.'}, status_code=413)
        response = await call_next(request)
        response.headers['Cache-Control']='no-store'
        response.headers['X-Content-Type-Options']='nosniff'
        response.headers['Content-Security-Policy']="default-src 'none'; frame-ancestors 'none'"
        return response

    def principal(request, kind):
        header = request.headers.get('authorization', '')
        token = header[7:] if header.startswith('Bearer ') else ''
        host = request.client.host if request.client else 'unknown'
        now = time.monotonic()
        with lock:
            if len(attempts)>4096:
                attempts.clear()
            count, started = attempts.get(host, (0,now))
            if now-started>60:
                count, started=0,now
            if count>=30:
                raise HTTPException(429,'Muitas tentativas. Aguarde um minuto.')
        try:
            return store.authenticate(token,kind)
        except RelayError:
            with lock:
                attempts[host]=(count+1,started)
            raise

    @app.get('/health')
    def health():
        return {'status':'ok','mode':'relay_api_only'}

    @app.get('/v1/devices')
    def catalog(request:Request):
        return {'devices':store.catalog(principal(request,'operator'))}

    @app.post('/v1/devices/{device_id}/commands')
    def enqueue(device_id:str, body:NewCommand, request:Request):
        caller=principal(request,'operator')
        try:
            return store.enqueue(caller,device_id,body.model_dump(mode='json'))
        except ValueError:
            raise HTTPException(422,'Função ou valor inválido.') from None

    @app.get('/v1/commands/{command_id}')
    def command(command_id:str,request:Request):
        return store.command(principal(request,'operator'),command_id)

    @app.post('/v1/agent/poll')
    def poll(request:Request):
        return store.poll(principal(request,'agent'))

    @app.post('/v1/agent/commands/{command_id}/result')
    def result(command_id:str,body:AgentResult,request:Request):
        return store.acknowledge(principal(request,'agent'),command_id,body.model_dump(mode='json'))

    app.state.relay_store=store
    return app
