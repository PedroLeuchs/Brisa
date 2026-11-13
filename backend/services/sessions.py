"""Sessões revogáveis; apenas hashes de tokens são armazenados no computador."""
import hashlib
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path


class SessionStore:
    def __init__(self, path: Path):
        self.path = path

    @contextmanager
    def _connect(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=5)
        try:
            with connection:
                connection.execute('CREATE TABLE IF NOT EXISTS sessions (token TEXT PRIMARY KEY, expires REAL NOT NULL, credential TEXT NOT NULL)')
                yield connection
        finally:
            connection.close()

    @staticmethod
    def _hash(value):
        return hashlib.sha256(value.encode()).hexdigest()

    def issue(self, token, expires, credential):
        with self._connect() as connection:
            connection.execute('DELETE FROM sessions WHERE expires <= ? OR credential != ?', (time.time(), self._hash(credential)))
            connection.execute('INSERT INTO sessions VALUES (?, ?, ?)', (self._hash(token), expires, self._hash(credential)))
            connection.execute('DELETE FROM sessions WHERE token IN (SELECT token FROM sessions ORDER BY expires DESC LIMIT -1 OFFSET 32)')

    def valid(self, token, credential):
        with self._connect() as connection:
            row = connection.execute('SELECT expires, credential FROM sessions WHERE token = ?', (self._hash(token),)).fetchone()
            return bool(row and row[0] > time.time() and row[1] == self._hash(credential))

    def revoke(self, token):
        with self._connect() as connection:
            connection.execute('DELETE FROM sessions WHERE token = ?', (self._hash(token),))

    def clear(self):
        with self._connect() as connection:
            connection.execute('DELETE FROM sessions')
