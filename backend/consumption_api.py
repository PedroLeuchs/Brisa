"""Rotas autenticadas de histórico de uso; nunca enviam comandos ao aparelho."""
from datetime import datetime

from fastapi import APIRouter, HTTPException, Request

from backend.services.automations import TIMEZONE


def consumption_router(collector, devices, authorize):
    router = APIRouter()

    def check(request, device_id):
        authorize(request)
        try:
            devices.adapter(device_id)
        except KeyError:
            raise HTTPException(404, 'Aparelho não encontrado.') from None

    @router.get('/api/consumption/{device_id}')
    def dashboard(device_id: str, request: Request, start: str | None = None, end: str | None = None):
        check(request, device_id)
        now = collector.clock()
        today = datetime.fromtimestamp(now, TIMEZONE).date().isoformat()
        try:
            result = collector.store.dashboard(device_id, start or today, end or today, now)
            return {**result, 'collector': collector.diagnostic()}
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None
        except Exception:
            raise HTTPException(503, 'Histórico temporariamente indisponível. Verifique o armazenamento local.') from None

    @router.post('/api/consumption/{device_id}/settings')
    async def settings(device_id: str, request: Request):
        check(request, device_id)
        try:
            body = await request.json()
        except ValueError:
            raise HTTPException(400, 'Pedido inválido.') from None
        try:
            return collector.store.configure(device_id, body)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None
        except Exception:
            raise HTTPException(503, 'Não foi possível salvar as referências de consumo.') from None

    return router
