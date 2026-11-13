"""Sessões persistentes com credenciais e relógio de teste, sem acessar o aparelho."""
from backend.services.sessions import SessionStore


def test_persistence_expiry_revocation_and_password_change(tmp_path, monkeypatch):
    import backend.services.sessions as module
    monkeypatch.setattr(module.time, 'time', lambda: 1000)
    path = tmp_path / 'sessions.sqlite3'
    first = SessionStore(path)
    first.issue('test-token', 2000, 'test-password-hash')
    restarted = SessionStore(path)
    assert restarted.valid('test-token', 'test-password-hash')
    assert not restarted.valid('wrong-token', 'test-password-hash')
    assert not restarted.valid('test-token', 'changed-password-hash')
    assert b'test-token' not in path.read_bytes()
    monkeypatch.setattr(module.time, 'time', lambda: 2000)
    assert not restarted.valid('test-token', 'test-password-hash')
    restarted.issue('new-token', 3000, 'test-password-hash')
    restarted.revoke('new-token')
    assert not SessionStore(path).valid('new-token', 'test-password-hash')
