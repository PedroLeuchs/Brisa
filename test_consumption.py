"""Histórico com relógio/aparelho simulados; nenhum comando ou leitura LAN real."""
from datetime import datetime

import pytest

from backend.services.automations import TIMEZONE
from backend.services.consumption import ConsumptionCollector, ConsumptionStore, REFERENCE_TARIFF


def stamp(value):
    return datetime.fromisoformat(value).replace(tzinfo=TIMEZONE).timestamp()


BASE = stamp('2026-10-23T10:00:00')


class FakeDevices:
    adapters = {'home-ac': object()}
    def __init__(self):
        self.power = True
        self.reads = 0
    def status(self, device):
        self.reads += 1
        if isinstance(self.power, Exception):
            raise self.power
        return {'state': {'switch': self.power}}
    def command(self, *args):
        pytest.fail('O consumo nunca deve enviar comandos.')


@pytest.fixture
def setup(tmp_path):
    store = ConsumptionStore(tmp_path / 'consumption.sqlite3')
    devices = FakeDevices()
    now = [BASE]
    collector = ConsumptionCollector(store, devices, clock=lambda: now[0])
    return store, devices, collector, now


def dashboard(store, now=BASE + 3600):
    return store.dashboard('home-ac', '2026-10-23', '2026-10-23', now)


def test_empty_history_does_not_invent_energy_or_past(setup):
    store, _, _, _ = setup
    result = dashboard(store)
    assert result['collection_started_at'] is None
    assert result['totals']['on_seconds'] == 0
    assert result['totals']['coverage_percent'] == 0
    assert result['totals']['estimated_kwh'] is None
    assert result['totals']['estimated_cost'] is None
    assert result['settings']['reference_watts'] is None
    assert result['settings']['tariff_per_kwh'] == REFERENCE_TARIFF
    assert result['measured_energy_available'] is False


def test_observed_hour_estimate_and_settings_survive_restart(setup):
    store, _, collector, now = setup
    store.configure('home-ac', {'reference_watts': 1000, 'tariff_per_kwh': REFERENCE_TARIFF})
    for minute in range(61):
        now[0] = BASE + minute * 60
        collector.collect()
    restarted = ConsumptionStore(store.path)
    result = dashboard(restarted)
    assert result['totals']['on_seconds'] == 3600
    assert result['totals']['estimated_kwh'] == 1
    assert result['totals']['estimated_cost'] == 1.06
    assert result['energy_source'] == 'reference_estimate'
    assert result['settings']['solar_credits_included'] is False
    with restarted.connect() as db:
        assert db.execute('PRAGMA user_version').fetchone()[0] == 1
        assert db.execute('SELECT count(*) FROM intervals').fetchone()[0] == 1
        assert db.execute('SELECT count(*) FROM observations').fetchone()[0] == 61
    # A referência atual recalcula o período; limpar potência retira kWh/custo.
    restarted.configure('home-ac', {'reference_watts': None, 'tariff_per_kwh': 2})
    assert dashboard(restarted)['totals']['estimated_kwh'] is None


def test_offline_transition_missing_state_and_restart_do_not_bridge_gaps(setup):
    store, devices, collector, now = setup
    for offset, power in [(0, True), (60, True), (120, OSError('secret')), (180, True), (240, True), (300, False), (360, False), (420, None), (480, False)]:
        now[0], devices.power = BASE + offset, power
        collector.collect()
    # Novo processo de coleta não continua o intervalo anterior, mesmo com mesmo estado.
    other = ConsumptionCollector(ConsumptionStore(store.path), devices, clock=lambda: now[0])
    now[0] = BASE + 500
    other.collect()
    now[0] = BASE + 560
    other.collect()
    result = dashboard(store, BASE + 560)
    assert result['totals']['on_seconds'] == 120
    assert result['totals']['off_seconds'] == 120
    assert result['totals']['unknown_seconds'] == (10 * 3600 + 560) - 240
    assert 'secret' not in str(result)


def test_clock_jump_and_regression_never_overlap_history(setup):
    store, _, collector, now = setup
    collector.collect()
    now[0] += 60
    collector.collect()
    now[0] -= 30
    collector.collect()
    now[0] = BASE + 3600
    collector.collect()
    # Reiniciar com relógio voltando também não cria intervalos sobrepostos.
    other = ConsumptionCollector(store, collector.devices, clock=lambda: now[0])
    now[0] = BASE + 30
    other.collect()
    now[0] = BASE + 60
    other.collect()
    assert dashboard(store)['totals']['on_seconds'] == 60


def test_storage_failure_recovers_without_filling_gap(setup, monkeypatch):
    store, _, collector, now = setup
    collector.collect()
    original = store.record
    monkeypatch.setattr(store, 'record', lambda *args: (_ for _ in ()).throw(OSError('secret')))
    now[0] += 60
    collector.collect()
    assert collector.diagnostic()['status'] == 'storage_error'
    assert 'secret' not in str(collector.diagnostic())
    monkeypatch.setattr(store, 'record', original)
    now[0] += 60
    collector.collect()
    now[0] += 60
    collector.collect()
    assert dashboard(store)['totals']['on_seconds'] == 60
    assert collector.diagnostic()['status'] == 'healthy'


def test_midnight_is_split_using_brasilia_not_utc(setup):
    store, _, collector, now = setup
    now[0] = stamp('2026-10-22T23:59:30')
    collector.collect()
    now[0] += 60
    collector.collect()
    result = store.dashboard('home-ac', '2026-10-22', '2026-10-23', now[0])
    assert [day['on_seconds'] for day in result['days']] == [30, 30]


@pytest.mark.parametrize('body', [[], {}, {'reference_watts': 0, 'tariff_per_kwh': 1}, {'reference_watts': True, 'tariff_per_kwh': 1}, {'reference_watts': -10, 'tariff_per_kwh': 1}, {'reference_watts': None, 'tariff_per_kwh': float('nan')}, {'reference_watts': None, 'tariff_per_kwh': -1}])
def test_invalid_reference_is_rejected(setup, body):
    with pytest.raises(ValueError):
        setup[0].configure('home-ac', body)


@pytest.mark.parametrize('start,end', [('oops', '2026-10-23'), ('2026-10-24', '2026-10-24'), ('2026-10-23', '2026-10-22'), ('2025-01-01', '2026-10-23')])
def test_period_validation(setup, start, end):
    with pytest.raises(ValueError):
        setup[0].dashboard('home-ac', start, end, BASE)


def test_retention_preserves_settings_and_collection_start(setup):
    store, _, collector, now = setup
    store.configure('home-ac', {'reference_watts': 500, 'tariff_per_kwh': 1})
    collector.collect()
    now[0] += 60
    collector.collect()
    now[0] += 731 * 86400
    collector.collect()
    with store.connect() as db:
        assert db.execute('SELECT count(*) FROM observations').fetchone()[0] == 1
        assert db.execute('SELECT count(*) FROM intervals').fetchone()[0] == 0
        assert float(db.execute("SELECT value FROM meta WHERE key='collection_started_at'").fetchone()[0]) == BASE
        assert db.execute('SELECT watts FROM settings').fetchone()[0] == 500


def test_background_loop_collects_without_browser_and_start_has_no_initial_lan_request(setup):
    store, devices, collector, now = setup
    collector.start()
    collector.stop()
    assert devices.reads == 0  # Primeira leitura só no intervalo, sem corrida com startup.
    assert dashboard(store)['collection_started_at'] == BASE
    class Steps:
        def __init__(self): self.count = 0
        def wait(self, interval):
            assert interval == 60
            self.count += 1
            now[0] = BASE + self.count * 60
            return self.count > 2
    collector.stop_event = Steps()
    collector._loop()
    assert devices.reads == 2
    assert dashboard(store)['totals']['on_seconds'] == 60


def test_today_timeline_partitions_elapsed_day_without_fabricating_transitions(setup):
    store, devices, collector, now = setup
    for offset, power in [(0, True), (60, True), (120, False), (180, False), (240, OSError('offline')), (300, True), (360, True)]:
        now[0], devices.power = BASE + offset, power
        collector.collect()
    result = dashboard(store, BASE + 400)
    chart = result['timeline']
    midnight = stamp('2026-10-23T00:00:00')
    assert chart['start'] == midnight and chart['end'] == BASE + 400
    assert chart['ends_at_now'] is True
    assert chart['sampling_seconds'] == 60
    assert chart['segments'] == [
        {'start': midnight, 'end': BASE, 'state': 'unknown'},
        {'start': BASE, 'end': BASE+60, 'state': 'on'},
        {'start': BASE+60, 'end': BASE+120, 'state': 'unknown'},
        {'start': BASE+120, 'end': BASE+180, 'state': 'off'},
        {'start': BASE+180, 'end': BASE+300, 'state': 'unknown'},
        {'start': BASE+300, 'end': BASE+360, 'state': 'on'},
        {'start': BASE+360, 'end': BASE+400, 'state': 'unknown'}]
    segments = chart['segments']
    assert all(left['end'] == right['start'] for left, right in zip(segments, segments[1:]))
    assert sum(s['end']-s['start'] for s in segments if s['state']=='on') == result['totals']['on_seconds']
    assert sum(s['end']-s['start'] for s in segments if s['state']=='unknown') == result['totals']['unknown_seconds']
    assert all(segment['end'] <= BASE+400 for segment in segments)


def test_timeline_clips_midnight_historical_day_and_retention_without_changing_database(setup):
    store, _, collector, now = setup
    now[0] = stamp('2026-10-22T23:59:30')
    collector.collect()
    now[0] += 60
    collector.collect()
    previous = store.dashboard('home-ac','2026-10-22','2026-10-22',now[0])['timeline']
    assert previous['ends_at_now'] is False
    assert previous['segments'][-1] == {'start':stamp('2026-10-22T23:59:30'),'end':stamp('2026-10-23T00:00:00'),'state':'on'}
    current = dashboard(store, now[0])['timeline']
    assert current['segments'] == [{'start':stamp('2026-10-23T00:00:00'),'end':now[0],'state':'on'}]
    with store.connect() as db:
        assert db.execute('SELECT count(*) FROM observations').fetchone()[0] == 2
        assert db.execute('PRAGMA user_version').fetchone()[0] == 1
    assert store.dashboard('home-ac','2026-10-22','2026-10-23',now[0])['timeline'] is None


def test_no_readings_is_one_unknown_segment_only_until_now(setup):
    result=dashboard(setup[0],BASE)
    assert result['timeline']['segments'] == [{'start':stamp('2026-10-23T00:00:00'),'end':BASE,'state':'unknown'}]


def test_transitions_require_adjacent_valid_readings_same_run_and_short_gap(setup):
    store, devices, collector, now = setup
    for offset, power in [(0,False),(60,False),(120,True),(180,True),(240,OSError('offline')),(300,False),(360,False)]:
        now[0],devices.power=BASE+offset,power
        collector.collect()
    other=ConsumptionCollector(store,devices,clock=lambda:now[0])
    now[0],devices.power=BASE+400,True
    other.collect()  # Reinício: não cria uma transição falsa.
    result=dashboard(store,BASE+450)['timeline']
    assert result['transitions']==[{'start':BASE+60,'end':BASE+120,'from':'off','to':'on'}]
    # A transição incerta não altera os totais persistidos.
    assert dashboard(store,BASE+450)['totals']['on_seconds']==60


def test_transition_near_midnight_is_clipped_and_never_includes_future(setup):
    store,devices,collector,now=setup
    now[0],devices.power=stamp('2026-10-22T23:59:40'),False
    collector.collect()
    now[0],devices.power=stamp('2026-10-23T00:00:40'),True
    collector.collect()
    chart=dashboard(store,now[0])['timeline']
    assert chart['transitions']==[{'start':stamp('2026-10-23T00:00:00'),'end':now[0],'from':'off','to':'on'}]
    assert dashboard(store,now[0]-10)['timeline']['transitions']==[]
