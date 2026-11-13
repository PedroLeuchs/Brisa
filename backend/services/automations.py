"""Automações locais por horário, persistentes e independentes da interface."""
from __future__ import annotations

import json
import os
import re
import threading
import uuid
import copy
import logging
from functools import wraps
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from controller import validate
from backend.services.routine_model import MAX_ENTRIES, ID_RE, aliases, signature, preserve_entries, upgrade_stored


try:
    TIMEZONE = ZoneInfo("America/Sao_Paulo")
except ZoneInfoNotFoundError:
    # Windows pode não trazer a base IANA. Desde 2019 São Paulo usa UTC-3
    # sem horário de verão; tzdata continua recomendado para manter a zona nomeada.
    TIMEZONE = timezone(timedelta(hours=-3), "America/Sao_Paulo")
TIME_RE = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")


class AutomationError(ValueError):
    pass


class AutomationStore:
    # Um único processo/worker é suportado; todas as instâncias desse processo
    # compartilham o lock do caminho, inclusive durante transações completas.
    _locks = {}
    _locks_guard = threading.Lock()

    def __init__(self, path: Path):
        self.path = path.resolve()
        with self._locks_guard:
            self.lock = self._locks.setdefault(str(self.path).lower(), threading.RLock())
        self.items: list[dict] = []

    def _load(self):
        with self.lock:
            if not self.path.exists():
                self.items = []
                return
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
                if not isinstance(data, list):
                    raise ValueError()
                upgraded=[upgrade_stored(item) for item in data]
                self.items=upgraded
                if upgraded!=data:
                    backup=self.path.with_name(self.path.stem+'.v1-backup.json')
                    if not backup.exists():
                        with backup.open('x',encoding='utf-8') as file:file.write(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
                    self._save()
            except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
                raise RuntimeError("Arquivo de automações inválido; corrija ou restaure antes de iniciar.") from exc

    def _save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(json.dumps(self.items, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(temporary, self.path)

    def list(self):
        with self.lock:
            self._load()
            return copy.deepcopy(self.items)

    def replace(self, items: list[dict]):
        with self.lock:
            previous = self.items
            self.items = copy.deepcopy(items)
            try:
                self._save()
            except Exception:
                self.items = previous
                raise


def serialized(method):
    @wraps(method)
    def transaction(self, *args, **kwargs):
        with self.store.lock:
            return method(self, *args, **kwargs)
    return transaction


class AutomationService:
    """Agenda semanal. Cada ocorrência é tentada uma vez, inclusive quando o aparelho está offline."""
    def __init__(self, store: AutomationStore, devices, *, clock=None, interval=15):
        self.store = store
        self.devices = devices
        self.clock = clock or (lambda: datetime.now(TIMEZONE))
        self.interval = interval
        self.stop_event = threading.Event()
        self.thread: threading.Thread | None = None
        self.last_checked: datetime | None = None
        self.health = {'status': 'starting', 'last_error_at': None, 'last_check_at': None,
                       'message': None, 'failures': 0}

    def diagnostic(self):
        with self.store.lock:
            return {**self.health, 'running': bool(self.thread and self.thread.is_alive()),
                    'worker_scope': 'single_process_single_worker'}

    @staticmethod
    def _validate_payload(payload, devices):
        legacy={"device_id", "code", "value", "time", "days", "enabled"}
        modern={'device_id','entries','days','enabled'}
        if not isinstance(payload, dict) or set(payload)-{'name'} not in (legacy,modern):
            raise AutomationError("Automação inválida.")
        device_id=payload['device_id']
        if not isinstance(device_id, str):
            raise AutomationError("Aparelho ou ação inválidos.")
        try:
            adapter = devices.adapter(device_id)
        except KeyError:
            raise AutomationError("Aparelho não encontrado.") from None
        entries=payload.get('entries') if 'entries' in payload else [{key:payload[key] for key in ('code','value','time')}]
        if not isinstance(entries,list) or not 1<=len(entries)<=MAX_ENTRIES:
            raise AutomationError(f'Adicione entre 1 e {MAX_ENTRIES} horários por rotina.')
        checked=[];ids=set();slots={}
        for entry in entries:
            if not isinstance(entry,dict) or set(entry) not in ({'code','value','time'},{'id','code','value','time'}):
                raise AutomationError('Entrada de horário inválida.')
            code=entry['code']
            if not isinstance(code,str) or code not in adapter.capabilities():
                raise AutomationError('Esta ação não está disponível no aparelho.')
            try:validate(code,entry['value'])
            except ValueError as exc:raise AutomationError(str(exc)) from None
            if not isinstance(entry['time'],str) or not TIME_RE.fullmatch(entry['time']):raise AutomationError('Horário inválido.')
            identity=entry.get('id')
            if identity is not None:
                if not isinstance(identity,str) or not ID_RE.fullmatch(identity) or identity in ids:raise AutomationError('Identificador de horário inválido ou repetido.')
                ids.add(identity)
            slot=(entry['time'],code)
            if slot in slots:
                kind='duplicada' if slots[slot]==entry['value'] else 'conflitante'
                raise AutomationError(f"Ação {kind} às {entry['time']}: edite a entrada existente ou escolha outro horário.")
            slots[slot]=entry['value'];checked.append(dict(entry))
        days = payload["days"]
        if not isinstance(days, list) or not days or any(type(day) is not int or day < 0 or day > 6 for day in days) or len(set(days)) != len(days):
            raise AutomationError("Escolha pelo menos um dia da semana, sem repetições.")
        if type(payload["enabled"]) is not bool:
            raise AutomationError("Estado da automação inválido.")
        name=payload.get('name','Rotina de climatização')
        if not isinstance(name,str) or not 1<=len(name.strip())<=80:raise AutomationError('Informe um nome entre 1 e 80 caracteres.')
        checked.sort(key=lambda entry:entry['time'])
        return {'device_id':device_id,'entries':checked,'days':sorted(days),'enabled':payload['enabled'],'name':name.strip()}

    @staticmethod
    def _signature(item):
        return signature(item)

    def list(self):
        return self.store.list()

    @staticmethod
    def _check_overlap(item,items,exclude=None):
        if not item['enabled']:return
        for other in items:
            if other['id']==exclude or not other['enabled'] or other['device_id']!=item['device_id'] or not set(other['days']).intersection(item['days']):continue
            slots={(entry['time'],entry['code']) for entry in other['entries']}
            for entry in item['entries']:
                if (entry['time'],entry['code']) in slots:
                    raise AutomationError(f"A ação às {entry['time']} já está em outra rotina ativa nos mesmos dias. Edite ou pause essa rotina antes de salvar.")

    @serialized
    def create(self, payload):
        item = self._validate_payload(payload, self.devices)
        items = self.store.list()
        if any(self._signature(existing) == self._signature(item) for existing in items):
            raise AutomationError("Já existe uma automação igual.")
        self._check_overlap(item,items)
        now = self.clock().astimezone(TIMEZONE).isoformat()
        item['entries'],item['retired_entries']=preserve_entries(item['entries'])
        item.update(id=uuid.uuid4().hex, created_at=now, updated_at=now, last_run=None, last_result=None)
        item=aliases(item)
        self.store.replace(items + [item])
        return item

    @serialized
    def update(self, automation_id, payload):
        updated = self._validate_payload(payload, self.devices)
        items = self.store.list()
        current = next((item for item in items if item.get("id") == automation_id), None)
        if current is None:
            raise KeyError(automation_id)
        if 'name' not in payload:updated['name']=current.get('name','Rotina de climatização')
        if 'entries' not in payload and len(current['entries'])>1:
            first={**updated['entries'][0],'id':current['entries'][0]['id']}
            others=[{key:entry[key] for key in ('id','time','code','value')} for entry in current['entries'][1:]]
            updated=self._validate_payload({'device_id':updated['device_id'],'days':updated['days'],'enabled':updated['enabled'],'name':updated['name'],'entries':[first,*others]},self.devices)
        if any(item.get("id") != automation_id and self._signature(item) == self._signature(updated) for item in items):
            raise AutomationError("Já existe uma automação igual.")
        self._check_overlap(updated,items,automation_id)
        updated.update(id=automation_id, created_at=current.get("created_at"), updated_at=self.clock().astimezone(TIMEZONE).isoformat(),
                       last_run=current.get("last_run"), last_result=current.get("last_result"))
        updated['entries'],updated['retired_entries']=preserve_entries(updated['entries'],current)
        updated=aliases(updated)
        self.store.replace([updated if item.get("id") == automation_id else item for item in items])
        return updated

    @serialized
    def delete(self, automation_id):
        items = self.store.list()
        if not any(item.get("id") == automation_id for item in items):
            raise KeyError(automation_id)
        self.store.replace([item for item in items if item.get("id") != automation_id])

    @staticmethod
    def _minute(value: datetime):
        return value.astimezone(TIMEZONE).replace(second=0, microsecond=0)

    @serialized
    def run_pending(self, now: datetime | None = None):
        current = self._minute(now or self.clock())
        # Na inicialização, apenas marca o ponto de partida: reiniciar não executa
        # a ocorrência do minuto atual nem tenta compensar comandos antigos.
        if self.last_checked is None:
            self.last_checked = current
            return []
        start = self.last_checked
        if current <= start:
            return []
        self.last_checked = current
        # Nunca compensa minutos anteriores, mesmo após uma suspensão curta.
        due_minutes = [current]
        results = []
        items = self.store.list()
        for item in items:
            if not item.get("enabled"):
                continue
            for minute in due_minutes:
              occurrence = minute.isoformat()
              for entry in item['entries']:
                if minute.weekday() not in item.get('days',[]) or minute.strftime('%H:%M')!=entry['time'] or entry.get('last_run')==occurrence or any(record.get('occurrence')==occurrence for record in entry['history']):
                    continue
                item['last_run']=entry['last_run']=occurrence
                # Persistir ANTES de enviar: uma falha/crash após envio nunca
                # permite repetir uma ocorrência cujo resultado ficou incerto.
                item['last_result'] = {'status': 'uncertain', 'at': self.clock().astimezone(TIMEZONE).isoformat(),
                                       'message': 'Ocorrência reservada; sem confirmação de conclusão.'}
                entry['last_result']=copy.deepcopy(item['last_result'])
                record={'occurrence':occurrence,'time':entry['time'],'code':entry['code'],'value':entry['value'],'result':copy.deepcopy(entry['last_result'])}
                entry['history'].append(record)
                self.store.replace(items)
                try:
                    self.devices.command(item['device_id'],entry['code'],entry['value'])
                    item["last_result"] = {"status": "success", "at": self.clock().astimezone(TIMEZONE).isoformat()}
                except Exception:
                    item["last_result"] = {"status": "offline", "at": self.clock().astimezone(TIMEZONE).isoformat(),
                                           "message": "O aparelho não respondeu; esta ocorrência não será repetida."}
                entry['last_result']=copy.deepcopy(item['last_result']);record['result']=copy.deepcopy(item['last_result'])
                results.append({'id':item['id'],'entry_id':entry['id'],'occurrence':occurrence,**item['last_result']})
                self.store.replace(items)
        return results

    def start(self):
        if self.thread and self.thread.is_alive():
            return
        self.stop_event.clear()
        self.last_checked = None
        self.run_pending()
        self.thread = threading.Thread(target=self._loop, name="brisa-automations", daemon=True)
        self.thread.start()

    def _loop(self):
        while not self.stop_event.wait(self.interval):
            self.tick()

    def tick(self):
        """Recupera erros de disco sem encerrar a thread ou compensar horários perdidos."""
        try:
            # Também detecta erros de leitura quando nenhum horário está devido.
            with self.store.lock:
                self.store.list()
                if self.health['status'] == 'degraded':
                    # O primeiro ciclo recuperado só restabelece a referência.
                    # Nenhum horário do intervalo indisponível é compensado.
                    minute = self._minute(self.clock())
                    if self.last_checked is None or minute > self.last_checked:
                        self.last_checked = minute
                self.run_pending()
                self.health.update(status='healthy', last_check_at=self.clock().isoformat(), message=None)
        except Exception:
            with self.store.lock:
                now = self.clock()
                minute = self._minute(now)
                if self.last_checked is None or minute > self.last_checked:
                    self.last_checked = minute
                self.health.update(status='degraded', last_error_at=now.isoformat(),
                                   message='Agenda indisponível: falha ao acessar ou salvar rotinas. Verifique o arquivo e as permissões. Horários perdidos não serão repetidos.',
                                   failures=self.health['failures'] + 1)
            logging.getLogger(__name__).error('Falha na agenda local; nova verificação no próximo ciclo.')

    def stop(self):
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=max(1, self.interval + 1))
        self.thread = None
