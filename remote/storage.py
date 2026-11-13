"""Fila durável e credenciais de máquina; um banco SQLite por relay."""
import contextlib
import hashlib
import json
from pathlib import Path
import secrets
import sqlite3
import time
import uuid

from remote.protocol import RULES, TERMINAL, canonical, fingerprint, safe_observation, validate_value


class RelayError(Exception):
    def __init__(self, status, message):
        self.status, self.message = status, message
        super().__init__(message)


class Database:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    @contextlib.contextmanager
    def transaction(self):
        db = sqlite3.connect(self.path, timeout=5, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA synchronous=FULL')
        db.execute('PRAGMA busy_timeout=5000')
        try:
            db.execute('BEGIN IMMEDIATE')
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()


class RelayStore(Database):
    def __init__(self, path, clock=time.time):
        super().__init__(path)
        self.clock = clock
        with self.transaction() as db:
            db.execute('CREATE TABLE IF NOT EXISTS devices(home TEXT, device TEXT, agent TEXT, controls TEXT, PRIMARY KEY(home,device))')
            db.execute('CREATE TABLE IF NOT EXISTS credentials(hash TEXT PRIMARY KEY, kind TEXT, home TEXT, subject TEXT, scope TEXT, revoked INTEGER NOT NULL DEFAULT 0)')
            db.execute('''CREATE TABLE IF NOT EXISTS commands(
                id TEXT PRIMARY KEY, home TEXT, device TEXT, agent TEXT, request_id TEXT,
                fingerprint TEXT, envelope TEXT, created REAL, expires REAL,
                state TEXT, lease_until REAL, result TEXT, UNIQUE(home,request_id))''')

    def provision_agent(self, home, agent, devices):
        token = secrets.token_urlsafe(32)
        with self.transaction() as db:
            for device, controls in devices.items():
                if not controls or not set(controls).issubset(RULES):
                    raise ValueError('invalid_controls')
                existing = db.execute('SELECT agent FROM devices WHERE home=? AND device=?', (home, device)).fetchone()
                if existing and existing['agent'] != agent:
                    raise ValueError('device_already_assigned')
                db.execute('INSERT OR REPLACE INTO devices VALUES(?,?,?,?)', (home, device, agent, canonical(controls)))
            db.execute('INSERT INTO credentials(hash,kind,home,subject,scope) VALUES(?,?,?,?,?)',
                       (hashlib.sha256(token.encode()).hexdigest(), 'agent', home, agent, canonical(list(devices))))
        return token

    def provision_operator(self, home, subject, devices):
        token = secrets.token_urlsafe(32)
        with self.transaction() as db:
            for device in devices:
                if not db.execute('SELECT 1 FROM devices WHERE home=? AND device=?', (home, device)).fetchone():
                    raise ValueError('unknown_device')
            db.execute('INSERT INTO credentials(hash,kind,home,subject,scope) VALUES(?,?,?,?,?)',
                       (hashlib.sha256(token.encode()).hexdigest(), 'operator', home, subject, canonical(devices)))
        return token

    def authenticate(self, token, kind):
        if not isinstance(token, str) or not 32 <= len(token) <= 256:
            raise RelayError(401, 'Credencial inválida.')
        with self.transaction() as db:
            row = db.execute('SELECT * FROM credentials WHERE hash=? AND revoked=0 AND kind=?',
                             (hashlib.sha256(token.encode()).hexdigest(), kind)).fetchone()
        if not row:
            raise RelayError(401, 'Credencial inválida.')
        return {**dict(row), 'scope': json.loads(row['scope'])}

    def revoke(self, token):
        with self.transaction() as db:
            db.execute('UPDATE credentials SET revoked=1 WHERE hash=?', (hashlib.sha256(token.encode()).hexdigest(),))

    def catalog(self, principal):
        with self.transaction() as db:
            rows = db.execute('SELECT device,controls FROM devices WHERE home=?', (principal['home'],)).fetchall()
        return [{'id': row['device'], 'controls': json.loads(row['controls'])} for row in rows if row['device'] in principal['scope']]

    def enqueue(self, principal, device, request):
        validate_value(request['code'], request['value'])
        if device not in principal['scope']:
            raise RelayError(404, 'Aparelho não encontrado.')
        signature = fingerprint({'device': device, **request})
        now = self.clock()
        with self.transaction() as db:
            row = db.execute('SELECT * FROM devices WHERE home=? AND device=?', (principal['home'], device)).fetchone()
            if not row or request['code'] not in json.loads(row['controls']):
                raise RelayError(422, 'Função indisponível.')
            prior = db.execute('SELECT * FROM commands WHERE home=? AND request_id=?', (principal['home'], request['request_id'])).fetchone()
            if prior:
                if prior['fingerprint'] != signature:
                    raise RelayError(409, 'Identificador já usado por outro comando.')
                return self._public(prior, now)
            count = db.execute('SELECT COUNT(*) FROM commands WHERE home=? AND created>?', (principal['home'], now-60)).fetchone()[0]
            if count >= 30:
                raise RelayError(429, 'Aguarde antes de enviar novos comandos.')
            pending = db.execute("SELECT COUNT(*) FROM commands WHERE home=? AND device=? AND state IN ('queued','delivered') AND expires>?", (principal['home'], device, now)).fetchone()[0]
            if pending >= 16:
                raise RelayError(429, 'Há pedidos pendentes para este aparelho.')
            envelope = {'version':1, 'command_id':str(uuid.uuid4()), 'home_id':principal['home'],
                        'agent_id':row['agent'], 'device_id':device, 'code':request['code'], 'value':request['value'],
                        'issued_at':now, 'expires_at':now+request['ttl_seconds']}
            db.execute('INSERT INTO commands VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',
                       (envelope['command_id'], principal['home'], device, row['agent'], request['request_id'],
                        signature, canonical(envelope), now, envelope['expires_at'], 'queued', 0, None))
            return self._public(db.execute('SELECT * FROM commands WHERE id=?', (envelope['command_id'],)).fetchone(), now)

    @staticmethod
    def _public(row, now):
        state = row['state']
        if state in {'queued','delivered'} and row['expires'] <= now:
            state = 'expired'
        return {'id':row['id'], 'device_id':row['device'], 'status':state,
                'expires_at':row['expires'], 'result':json.loads(row['result']) if row['result'] else None}

    def command(self, principal, command_id):
        with self.transaction() as db:
            row = db.execute('SELECT * FROM commands WHERE id=? AND home=?', (command_id, principal['home'])).fetchone()
        if not row or row['device'] not in principal['scope']:
            raise RelayError(404, 'Comando não encontrado.')
        return self._public(row, self.clock())

    def poll(self, principal):
        now = self.clock()
        with self.transaction() as db:
            db.execute("UPDATE commands SET state='expired' WHERE state IN ('queued','delivered') AND expires<=?", (now,))
            rows = db.execute("SELECT * FROM commands WHERE home=? AND agent=? AND state IN ('queued','delivered') AND lease_until<=? AND expires>? ORDER BY created,id", (principal['home'], principal['subject'], now, now)).fetchall()
            row = next((item for item in rows if item['device'] in principal['scope']), None)
            if not row:
                return {'server_time':now, 'command':None}
            db.execute("UPDATE commands SET state='delivered', lease_until=? WHERE id=?", (min(row['expires'], now+10), row['id']))
            return {'server_time':now, 'command':json.loads(row['envelope'])}

    def acknowledge(self, principal, command_id, result):
        clean = {'status':result['status'], 'reason':result['reason'], 'observation':safe_observation(result.get('observation'))}
        if clean['status'] == 'confirmed' and clean['observation'] is None:
            raise RelayError(422, 'Confirmação exige leitura válida.')
        with self.transaction() as db:
            row = db.execute('SELECT * FROM commands WHERE id=? AND home=? AND agent=?', (command_id, principal['home'], principal['subject'])).fetchone()
            if not row or row['device'] not in principal['scope']:
                raise RelayError(404, 'Comando não encontrado.')
            if row['state'] in TERMINAL and row['result']:
                if row['result'] != canonical(clean):
                    raise RelayError(409, 'Resultado já registrado.')
                return {'ok':True}
            envelope = json.loads(row['envelope'])
            if clean['status']=='confirmed' and clean['observation']['state'].get(envelope['code']) != envelope['value']:
                raise RelayError(422, 'Leitura não confirma o valor solicitado.')
            if clean['status']=='confirmed' and clean['observation']['timestamp'] < envelope['issued_at']:
                raise RelayError(422, 'Leitura anterior ao comando não confirma execução.')
            db.execute('UPDATE commands SET state=?,result=? WHERE id=?', (clean['status'], canonical(clean), command_id))
        return {'ok':True}
