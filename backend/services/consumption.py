"""Histórico local de uso observado. Não representa medição elétrica."""
from __future__ import annotations

import logging
import math
import sqlite3
import threading
import time
import uuid
from contextlib import contextmanager
from datetime import date, datetime, time as day_time, timedelta
from decimal import Decimal
from pathlib import Path

from backend.services.automations import TIMEZONE

REFERENCE_TARIFF = 1.056961  # Conta Copel convencional, Toledo/PR, set/26; sem créditos solares.
MAX_GAP = 90
RETENTION_DAYS = 730


def daily_timeline(intervals, start, end, retained_from):
    """Particiona somente o tempo decorrido, sem transformar lacunas em desligado."""
    segments = []
    cursor = start

    def append(lo, hi, state):
        if hi <= lo:
            return
        if segments and segments[-1]['state'] == state and segments[-1]['end'] == lo:
            segments[-1]['end'] = hi
        else:
            segments.append({'start': lo, 'end': hi, 'state': state})

    for interval in intervals:
        lo = max(start, interval['start'], retained_from, cursor)
        hi = min(end, interval['end'])
        if hi <= lo:
            continue
        append(cursor, lo, 'unknown')
        append(lo, hi, 'on' if interval['power'] else 'off')
        cursor = hi
    append(cursor, end, 'unknown')
    return segments


def observed_transitions(readings, start, end):
    """Mudança entre leituras válidas próximas do mesmo ciclo, nunca através de offline."""
    changes = []
    for previous, current in zip(readings, readings[1:]):
        if (previous['power'] is not None and current['power'] is not None
                and previous['power'] != current['power'] and previous['run'] == current['run']
                and 0 < current['at'] - previous['at'] <= MAX_GAP
                and start < current['at'] <= end):
            changes.append({'start': max(start, previous['at']), 'end': current['at'],
                            'from': 'on' if previous['power'] else 'off',
                            'to': 'on' if current['power'] else 'off'})
    return changes


class ConsumptionStore:
    """SQLite v1; transações curtas, intervalo só entre leituras do mesmo ciclo de coleta."""
    def __init__(self, path: Path):
        self.path = path
        self.lock = threading.RLock()

    @contextmanager
    def connect(self):
        with self.lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            connection = sqlite3.connect(self.path, timeout=5)
            connection.row_factory = sqlite3.Row
            try:
                with connection:
                    connection.execute('BEGIN IMMEDIATE')
                    version = connection.execute('PRAGMA user_version').fetchone()[0]
                    if version > 1:
                        raise RuntimeError('Versão de histórico não suportada.')
                    if version == 0:
                        connection.execute('CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
                        connection.execute('CREATE TABLE settings (device TEXT PRIMARY KEY, watts REAL, tariff REAL NOT NULL)')
                        connection.execute('CREATE TABLE observations (id INTEGER PRIMARY KEY, device TEXT NOT NULL, at REAL NOT NULL, power INTEGER, run TEXT NOT NULL)')
                        connection.execute('CREATE INDEX observations_device_at ON observations(device, at)')
                        connection.execute('CREATE INDEX observations_at ON observations(at)')
                        connection.execute('CREATE TABLE intervals (id INTEGER PRIMARY KEY, device TEXT NOT NULL, start REAL NOT NULL, end REAL NOT NULL, power INTEGER NOT NULL, run TEXT NOT NULL, CHECK(end > start))')
                        connection.execute('CREATE INDEX intervals_device_end ON intervals(device, end)')
                        connection.execute('CREATE INDEX intervals_end ON intervals(end)')
                        connection.execute('PRAGMA user_version = 1')
                    yield connection
            finally:
                connection.close()

    def begin(self, at: float):
        with self.connect() as db:
            db.execute('INSERT OR IGNORE INTO meta VALUES (?, ?)', ('collection_started_at', str(at)))

    @staticmethod
    def _settings(db, device):
        row = db.execute('SELECT watts, tariff FROM settings WHERE device = ?', (device,)).fetchone()
        return {'reference_watts': row['watts'] if row else None,
                'tariff_per_kwh': row['tariff'] if row else REFERENCE_TARIFF,
                'tariff_source': 'Referência da conta Copel · Toledo/PR · convencional · set/26',
                'solar_credits_included': False}

    def configure(self, device, body):
        if not isinstance(body, dict) or set(body) != {'reference_watts', 'tariff_per_kwh'}:
            raise ValueError('Configuração de consumo inválida.')
        watts, tariff = body['reference_watts'], body['tariff_per_kwh']
        if watts is not None and (type(watts) not in {float, int} or not math.isfinite(watts) or not 0 < watts <= 100000):
            raise ValueError('Informe potência elétrica entre 0 e 100.000 W, ou deixe em branco.')
        if type(tariff) not in {float, int} or not math.isfinite(tariff) or not 0 <= tariff <= 100:
            raise ValueError('Informe tarifa entre R$ 0 e R$ 100 por kWh.')
        with self.connect() as db:
            db.execute('INSERT INTO settings VALUES (?, ?, ?) ON CONFLICT(device) DO UPDATE SET watts=excluded.watts, tariff=excluded.tariff', (device, watts, tariff))
            return self._settings(db, device)

    def record(self, device, at, power, run, previous):
        """Retorna o novo ponto anterior somente depois de confirmar a gravação."""
        with self.connect() as db:
            latest = db.execute('SELECT at FROM observations WHERE device = ? ORDER BY at DESC LIMIT 1', (device,)).fetchone()
            if latest and at <= latest['at']:
                # Inclui regressão do relógio entre reinícios do servidor.
                return (latest['at'], None)
            db.execute('INSERT OR IGNORE INTO meta VALUES (?, ?)', ('collection_started_at', str(at)))
            db.execute('INSERT INTO observations(device, at, power, run) VALUES (?, ?, ?, ?)', (device, at, power, run))
            if previous is not None:
                before_at, before_power = previous
                if power is not None and before_power == power and 0 < at - before_at <= MAX_GAP:
                    # Leituras coincidentes delimitam tempo observado, com resolução
                    # de 60 s. Mudança de estado e lacunas permanecem desconhecidas.
                    updated = db.execute('UPDATE intervals SET end = ? WHERE id = (SELECT id FROM intervals WHERE device = ? AND run = ? AND power = ? AND end = ? ORDER BY id DESC LIMIT 1)', (at, device, run, power, before_at)).rowcount
                    if not updated:
                        db.execute('INSERT INTO intervals(device, start, end, power, run) VALUES (?, ?, ?, ?, ?)', (device, before_at, at, power, run))
            db.execute('DELETE FROM observations WHERE at < ?', (at - 90 * 86400,))
            db.execute('DELETE FROM intervals WHERE end < ?', (at - RETENTION_DAYS * 86400,))
        return (at, power)

    def dashboard(self, device, start_date: str, end_date: str, now: float):
        try:
            first, last = date.fromisoformat(start_date), date.fromisoformat(end_date)
        except (ValueError, TypeError):
            raise ValueError('Informe datas válidas.') from None
        today = datetime.fromtimestamp(now, TIMEZONE).date()
        if first > last or last > today or (last - first).days >= 366:
            raise ValueError('Escolha até 366 dias, sem datas futuras.')
        start = datetime.combine(first, day_time(), TIMEZONE).timestamp()
        end = min(now, datetime.combine(last + timedelta(days=1), day_time(), TIMEZONE).timestamp())
        if start >= end:
            raise ValueError('O período ainda não começou.')
        retained_from = now - RETENTION_DAYS * 86400
        with self.connect() as db:
            settings = self._settings(db, device)
            began = db.execute("SELECT value FROM meta WHERE key = 'collection_started_at'").fetchone()
            latest = db.execute('SELECT at, power FROM observations WHERE device = ? ORDER BY at DESC, id DESC LIMIT 1', (device,)).fetchone()
            intervals = db.execute('SELECT start, end, power FROM intervals WHERE device = ? AND end > ? AND start < ? ORDER BY start', (device, max(start, retained_from), end)).fetchall()
            readings = db.execute('SELECT at, power, run FROM observations WHERE device = ? AND at >= ? AND at <= ? ORDER BY at, id', (device, start - MAX_GAP, end)).fetchall() if first == last else []
        days = []
        cursor = first
        while cursor <= last:
            lo = datetime.combine(cursor, day_time(), TIMEZONE).timestamp()
            hi = min(end, datetime.combine(cursor + timedelta(days=1), day_time(), TIMEZONE).timestamp())
            days.append({'date': cursor.isoformat(), 'start': lo, 'end': hi, 'on_seconds': 0.0, 'off_seconds': 0.0})
            cursor += timedelta(days=1)
        for interval in intervals:
            cursor_at = max(start, interval['start'], retained_from)
            stop_at = min(end, interval['end'])
            while cursor_at < stop_at:
                index = (datetime.fromtimestamp(cursor_at, TIMEZONE).date() - first).days
                day = days[index]
                until = min(stop_at, day['end'])
                day['on_seconds' if interval['power'] else 'off_seconds'] += until - cursor_at
                cursor_at = until
        for day in days:
            observed = day['on_seconds'] + day['off_seconds']
            duration = max(0, day.pop('end') - day.pop('start'))
            day['unknown_seconds'] = max(0, duration - observed)
            day['coverage_percent'] = round(100 * observed / duration, 1) if duration else 0
        on = sum(day['on_seconds'] for day in days)
        off = sum(day['off_seconds'] for day in days)
        unknown = max(0, end - start - on - off)
        watts = settings['reference_watts']
        kwh = Decimal(str(on)) / Decimal(3600) * Decimal(str(watts)) / Decimal(1000) if watts is not None and on + off > 0 else None
        return {'device_id': device, 'start_date': start_date, 'end_date': end_date, 'timezone': 'America/Sao_Paulo',
                'collection_started_at': float(began['value']) if began else None, 'retained_from': retained_from,
                'last_observation': dict(latest) if latest else None, 'settings': settings, 'days': days,
                'timeline': {'date': first.isoformat(), 'start': start, 'end': end,
                             'ends_at_now': last == today, 'sampling_seconds': 60,
                             'transitions': observed_transitions(readings, start, end),
                             'segments': daily_timeline(intervals, start, end, retained_from)} if first == last else None,
                'totals': {'on_seconds': on, 'off_seconds': off, 'unknown_seconds': unknown,
                           'coverage_percent': round(100 * (on + off) / (end - start), 1),
                           'estimated_kwh': round(float(kwh), 6) if kwh is not None else None,
                           'estimated_cost': round(float(kwh * Decimal(str(settings['tariff_per_kwh']))), 2) if kwh is not None else None},
                'energy_source': 'reference_estimate' if watts is not None else 'unavailable',
                'measured_energy_available': False,
                'method': 'Intervalos entre leituras consecutivas concordantes, a até 90 segundos. Transições, falhas e reinícios ficam sem observação. Tempo ligado não mede o tempo do compressor.',
                'estimate_note': 'Referências atuais aplicadas ao período inteiro: potência × tempo observado ligado. Não mede variação de carga nem standby. Sem créditos solares e sem adicionar tributos.'}


class ConsumptionCollector:
    """Somente leituras, um coletor por processo servidor/worker (intervalo de 60 s)."""
    def __init__(self, store, devices, *, clock=None, interval=60):
        self.store, self.devices = store, devices
        self.clock, self.interval = clock or time.time, interval
        self.stop_event = threading.Event()
        self.thread = None
        self.previous = {}
        self.run = uuid.uuid4().hex
        self.health = {'status': 'waiting', 'last_check_at': None, 'failures': 0}

    def start(self):
        if self.thread and self.thread.is_alive():
            return
        self.previous = {}
        self.run = uuid.uuid4().hex
        self.stop_event.clear()
        # Inicialização de disco é recuperável; não impede login/controle.
        try:
            self.store.begin(self.clock())
        except Exception:
            self.health.update(status='storage_error')
        self.thread = threading.Thread(target=self._loop, name='brisa-consumption', daemon=True)
        self.thread.start()

    def collect(self):
        status = 'healthy'
        # O registro explícito não exige consulta LAN ao listar IDs.
        for device in tuple(self.devices.adapters):
            try:
                reply = self.devices.status(device)
                raw = reply.get('state', {}).get('switch')
                power = int(raw) if type(raw) is bool else None
                if power is None:
                    status = 'offline'
            except Exception:
                power, status = None, 'offline'
            at = self.clock()
            try:
                previous = self.previous.get(device)
                # Se o relógio voltar, descarta até alcançar a última leitura,
                # evitando sobreposição e contagem duplicada de intervalos.
                if previous and at <= previous[0]:
                    continue
                self.previous[device] = self.store.record(device, at, power, self.run, previous)
            except Exception:
                self.previous.pop(device, None)
                status = 'storage_error'
                self.health['failures'] += 1
                logging.getLogger(__name__).error('Falha ao persistir histórico de uso; próxima coleta tentará novamente.')
        self.health.update(status=status, last_check_at=self.clock())

    def _loop(self):
        while not self.stop_event.wait(self.interval):
            try:
                self.collect()
            except Exception:
                self.previous.clear()
                self.health.update(status='storage_error', failures=self.health['failures'] + 1)
                logging.getLogger(__name__).error('Falha no coletor de uso; próxima coleta tentará novamente.')

    def diagnostic(self):
        return {**self.health, 'running': bool(self.thread and self.thread.is_alive()), 'interval_seconds': self.interval}

    def stop(self):
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=10)
        self.thread = None
