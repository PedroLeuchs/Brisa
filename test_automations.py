"""Testes da agenda com relógio e aparelho simulados; nenhum comando físico é enviado."""
from datetime import datetime

import pytest

from backend.services.automations import AutomationError, AutomationService, AutomationStore, TIMEZONE


class FakeAdapter:
    def capabilities(self):
        return {
            "switch": {"type": "bool", "values": None},
            "temp_set": {"type": "int", "values": (16, 31), "step": 1},
            "mode": {"type": "enum", "values": ["auto", "cold", "hot", "wet", "wind"]},
        }


class FakeDevices:
    def __init__(self):
        self.calls = []
        self.fail = False
        self.device = FakeAdapter()

    def adapter(self, device_id):
        if device_id != "home-ac":
            raise KeyError(device_id)
        return self.device

    def command(self, device_id, code, value):
        self.calls.append((device_id, code, value))
        if self.fail:
            raise OSError("offline secret")


@pytest.fixture
def service(tmp_path):
    devices = FakeDevices()
    scheduler = AutomationService(AutomationStore(tmp_path / "automations.json"), devices)
    return scheduler, devices


def payload(**changes):
    base = {"device_id": "home-ac", "code": "switch", "value": True,
            "time": "08:30", "days": [0, 2, 4], "enabled": True}
    return {**base, **changes}


def at(value):
    return datetime.fromisoformat(value).replace(tzinfo=TIMEZONE)


def test_create_update_pause_delete_and_persist(service):
    scheduler, _ = service
    created = scheduler.create(payload())
    assert created["enabled"] is True
    assert AutomationStore(scheduler.store.path).list()[0]["id"] == created["id"]
    edited = scheduler.update(created["id"], payload(value=False, enabled=False))
    assert edited["value"] is False and edited["enabled"] is False
    scheduler.delete(created["id"])
    assert scheduler.list() == []


def test_rejects_duplicate_invalid_time_days_action_and_value(service):
    scheduler, _ = service
    scheduler.create(payload())
    with pytest.raises(AutomationError, match="igual"):
        scheduler.create(payload(enabled=False))
    for invalid in [payload(time="25:00"), payload(days=[]), payload(days=[0, 0]),
                    payload(code="unknown"), payload(value="true")]:
        with pytest.raises(AutomationError):
            scheduler.create(invalid)


def test_runs_due_minute_once_and_never_retries_offline_occurrence(service):
    scheduler, devices = service
    created = scheduler.create(payload(time="08:31", days=[0]))
    scheduler.run_pending(at("2026-10-19T08:30:20"))  # segunda-feira; inicializa somente
    devices.fail = True
    result = scheduler.run_pending(at("2026-10-19T08:31:01"))
    assert devices.calls == [("home-ac", "switch", True)]
    assert result[0]["status"] == "offline"
    assert "secret" not in str(result)
    scheduler.run_pending(at("2026-10-19T08:31:50"))
    scheduler.run_pending(at("2026-10-19T08:32:00"))
    assert len(devices.calls) == 1
    assert scheduler.list()[0]["id"] == created["id"]


def test_restart_and_long_clock_jump_do_not_replay_old_commands(service):
    scheduler, devices = service
    scheduler.create(payload(time="08:30", days=[0]))
    scheduler.run_pending(at("2026-10-19T08:30:45"))
    assert devices.calls == []
    scheduler.run_pending(at("2026-10-19T10:00:00"))
    assert devices.calls == []


def test_clock_regression_does_not_duplicate_an_occurrence(service):
    scheduler, devices = service
    scheduler.create(payload(time="08:31", days=[0]))
    scheduler.run_pending(at("2026-10-19T08:30:00"))
    scheduler.run_pending(at("2026-10-19T08:31:00"))
    scheduler.run_pending(at("2026-10-19T08:29:00"))
    scheduler.run_pending(at("2026-10-19T08:31:00"))
    assert len(devices.calls) == 1


def test_executes_each_distinct_due_automation(service):
    scheduler, devices = service
    scheduler.create(payload(time="08:31", days=[0]))
    scheduler.create(payload(code="temp_set", value=23, time="08:31", days=[0]))
    scheduler.run_pending(at("2026-10-19T08:30:00"))
    scheduler.run_pending(at("2026-10-19T08:31:00"))
    assert devices.calls == [("home-ac", "switch", True), ("home-ac", "temp_set", 23)]


def test_concurrent_creates_keep_all_changes_and_reject_duplicates(service):
    from concurrent.futures import ThreadPoolExecutor
    import threading
    scheduler, _ = service
    barrier = threading.Barrier(8)
    def create(index):
        barrier.wait()
        return scheduler.create(payload(time=f'09:{index:02d}'))
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(create, range(8)))
    assert len(scheduler.list()) == 8
    barrier = threading.Barrier(8)
    def duplicate(_):
        barrier.wait()
        try:
            scheduler.create(payload(time='10:00'))
            return True
        except AutomationError:
            return False
    with ThreadPoolExecutor(max_workers=8) as pool:
        assert sum(pool.map(duplicate, range(8))) == 1


@pytest.mark.parametrize('mutation', ['delete', 'pause', 'edit'])
def test_crud_during_dispatch_never_gets_overwritten(service, mutation):
    from concurrent.futures import ThreadPoolExecutor
    import threading
    scheduler, devices = service
    item = scheduler.create(payload(time='08:31', days=[0]))
    scheduler.run_pending(at('2026-10-19T08:30:00'))
    entered, release = threading.Event(), threading.Event()
    original = devices.command
    def command(*args):
        entered.set()
        assert release.wait(3)
        original(*args)
    devices.command = command
    def change():
        if mutation == 'delete':
            scheduler.delete(item['id'])
        else:
            scheduler.update(item['id'], payload(time='08:31' if mutation == 'pause' else '09:00', days=[0], enabled=mutation != 'pause'))
    with ThreadPoolExecutor(max_workers=2) as pool:
        running = pool.submit(scheduler.run_pending, at('2026-10-19T08:31:00'))
        assert entered.wait(3)
        changing = pool.submit(change)
        release.set()
        running.result(timeout=3)
        changing.result(timeout=3)
    items = scheduler.list()
    if mutation == 'delete':
        assert items == []
    elif mutation == 'pause':
        assert items[0]['enabled'] is False
    else:
        assert items[0]['time'] == '09:00'
    assert len(devices.calls) == 1


@pytest.mark.parametrize('mutation', ['delete', 'pause'])
def test_committed_pause_or_delete_prevents_dispatch(service, mutation):
    scheduler, devices = service
    item = scheduler.create(payload(time='08:31', days=[0]))
    scheduler.run_pending(at('2026-10-19T08:30:00'))
    if mutation == 'delete':
        scheduler.delete(item['id'])
    else:
        scheduler.update(item['id'], payload(time='08:31', days=[0], enabled=False))
    scheduler.run_pending(at('2026-10-19T08:31:00'))
    assert devices.calls == []


def test_failure_to_persist_claim_never_sends_and_next_tick_recovers(service, monkeypatch):
    scheduler, devices = service
    now = [at('2026-10-19T08:30:00')]
    scheduler.clock = lambda: now[0]
    scheduler.create(payload(time='08:31', days=[0]))
    scheduler.tick()
    original = scheduler.store._save
    monkeypatch.setattr(scheduler.store, '_save', lambda: (_ for _ in ()).throw(OSError('secret')))
    now[0] = at('2026-10-19T08:31:00')
    scheduler.tick()
    assert devices.calls == []
    assert scheduler.diagnostic()['status'] == 'degraded'
    assert 'secret' not in str(scheduler.diagnostic())
    monkeypatch.setattr(scheduler.store, '_save', original)
    scheduler.tick()
    assert scheduler.diagnostic()['status'] == 'healthy'
    assert devices.calls == []


def test_result_write_failure_preserves_claim_and_does_not_resend(service, monkeypatch):
    scheduler, devices = service
    now = [at('2026-10-19T08:30:00')]
    scheduler.clock = lambda: now[0]
    scheduler.create(payload(time='08:31', days=[0]))
    scheduler.tick()
    original = scheduler.store._save
    writes = []
    def save():
        writes.append(True)
        if len(writes) == 2:
            raise OSError('result write failed')
        original()
    monkeypatch.setattr(scheduler.store, '_save', save)
    now[0] = at('2026-10-19T08:31:00')
    scheduler.tick()
    assert len(devices.calls) == 1
    assert scheduler.list()[0]['last_result']['status'] == 'uncertain'
    scheduler.tick()
    assert len(devices.calls) == 1


def test_corrupt_file_keeps_loop_alive_and_recovers_without_replay(service):
    scheduler, devices = service
    now = [at('2026-10-19T08:30:00')]
    scheduler.clock = lambda: now[0]
    scheduler.create(payload(time='08:31', days=[0]))
    saved = scheduler.store.path.read_text(encoding='utf-8')
    scheduler.store.path.write_text('{broken', encoding='utf-8')
    class Steps:
        def __init__(self): self.count = 0
        def wait(self, _):
            self.count += 1
            if self.count == 2:
                assert scheduler.diagnostic()['status'] == 'degraded'
                scheduler.store.path.write_text(saved, encoding='utf-8')
                now[0] = at('2026-10-19T08:32:00')
            return self.count > 2
    scheduler.stop_event = Steps()
    scheduler._loop()
    assert scheduler.diagnostic()['status'] == 'healthy'
    assert scheduler.diagnostic()['failures'] == 1
    assert devices.calls == []
