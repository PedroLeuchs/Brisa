import copy
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import pytest
from backend.services.automations import AutomationError, AutomationService, AutomationStore, TIMEZONE
from test_automations import FakeDevices

def at(value):return datetime.fromisoformat(value).replace(tzinfo=TIMEZONE)
def entry(time,value=True,code='switch',id=None):
    result={'time':time,'code':code,'value':value}
    if id is not None:result['id']=id
    return result
def routine(entries=None,**changes):
    return {'name':'Dia confortável','device_id':'home-ac','days':[0],'enabled':True,
            'entries':entries or [entry('08:00'),entry('10:00',False),entry('14:00'),entry('16:00',False)],**changes}
@pytest.fixture
def setup(tmp_path):
    devices=FakeDevices();clock=[at('2026-10-19T07:59:00')]
    service=AutomationService(AutomationStore(tmp_path/'automations.json'),devices,clock=lambda:clock[0])
    return service,devices,clock

def test_four_daily_occurrences_share_one_routine_and_persist_separate_history(setup):
    service,devices,clock=setup;created=service.create(routine());service.tick()
    for hour in ['08:00','10:00','14:00','16:00']:
        clock[0]=at('2026-10-19T'+hour+':00');service.tick();service.tick()
    assert devices.calls==[('home-ac','switch',True),('home-ac','switch',False),('home-ac','switch',True),('home-ac','switch',False)]
    saved=service.list();assert len(saved)==1 and saved[0]['id']==created['id']
    assert len({e['id'] for e in saved[0]['entries']})==4
    assert all(len(e['history'])==1 for e in saved[0]['entries'])
    service.run_pending(at('2026-10-19T08:00:00'));assert len(devices.calls)==4

def test_legacy_migration_preserves_paused_state_identity_history_and_backup(tmp_path):
    legacy={'id':'legacy','device_id':'home-ac','code':'switch','value':True,'time':'08:00','days':[0],
            'enabled':False,'created_at':'old','updated_at':'old','last_run':'2026-10-19T08:00:00-03:00',
            'last_result':{'status':'success','at':'old'}}
    path=tmp_path/'automations.json';path.write_text(json.dumps([legacy]),encoding='utf-8')
    service=AutomationService(AutomationStore(path),FakeDevices());migrated=service.list()[0]
    assert migrated['enabled'] is False and migrated['id']=='legacy'
    assert migrated['last_result']==legacy['last_result'] and migrated['entries'][0]['last_run']==legacy['last_run']
    assert migrated['entries'][0]['history'][0]['result']==legacy['last_result']
    assert json.loads((tmp_path/'automations.v1-backup.json').read_text())==[legacy]
    assert AutomationStore(path).list()[0]['entries'][0]['id']==migrated['entries'][0]['id']

def test_edit_remove_and_restore_entry_retains_history_and_enabled(setup):
    service,devices,clock=setup;created=service.create(routine(enabled=False));identity=created['entries'][0]['id']
    current=service.update(created['id'],routine([entry('08:00',id=identity)],enabled=True))
    service.tick();clock[0]=at('2026-10-19T08:00:00');service.tick()
    saved=service.list()[0];oldhistory=copy.deepcopy(saved['entries'][0]['history'])
    removed=service.update(created['id'],routine([entry('12:00',id='new-entry')],enabled=False))
    assert next(e for e in removed['retired_entries'] if e['id']==identity)['history']==oldhistory and removed['enabled'] is False
    restored=service.update(created['id'],routine([entry('09:00',False,id=identity)],enabled=False))
    assert restored['entries'][0]['history']==oldhistory and restored['enabled'] is False

@pytest.mark.parametrize('items',[ [entry('08:00'),entry('08:00')], [entry('08:00'),entry('08:00',False)] ])
def test_duplicate_or_conflicting_same_action_time_is_explicit(setup,items):
    service,devices,_=setup
    with pytest.raises(AutomationError,match='duplicada|conflitante'):service.create(routine(items))
    assert service.list()==[] and devices.calls==[]

def test_distinct_same_minute_actions_run_in_declared_order(setup):
    service,devices,clock=setup;service.create(routine([entry('08:00'),entry('08:00',23,'temp_set')]));service.tick()
    clock[0]=at('2026-10-19T08:00:00');service.tick()
    assert devices.calls==[('home-ac','switch',True),('home-ac','temp_set',23)]

def test_old_client_edit_does_not_delete_other_entries_or_change_name(setup):
    service,_,_=setup;created=service.create(routine())
    updated=service.update(created['id'],{'device_id':'home-ac','code':'switch','value':True,'time':'08:00','days':[0],'enabled':False})
    assert len(updated['entries'])==4 and updated['enabled'] is False and updated['name']==created['name']
    assert [e['id'] for e in updated['entries']]==[e['id'] for e in created['entries']]

def test_no_previous_minute_catchup_after_short_gap(setup):
    service,devices,clock=setup;service.create(routine([entry('08:00')]));service.tick()
    clock[0]=at('2026-10-19T08:01:00');service.tick();assert devices.calls==[]

def test_failed_occurrence_does_not_block_later_entry_and_is_not_retried(setup):
    service,devices,clock=setup;service.create(routine([entry('08:00'),entry('08:01',False)]));service.tick()
    devices.fail=True;clock[0]=at('2026-10-19T08:00:00');service.tick();service.tick()
    devices.fail=False;clock[0]=at('2026-10-19T08:01:00');service.tick()
    entries=service.list()[0]['entries'];assert len(devices.calls)==2
    assert entries[0]['last_result']['status']=='offline' and entries[1]['last_result']['status']=='success'

def test_pause_is_group_wide_and_resume_conflict_does_not_silently_enable(setup):
    service,_,_=setup;service.create(routine([entry('08:00')]))
    paused=service.create(routine([entry('08:00',False)],enabled=False))
    with pytest.raises(AutomationError,match='outra rotina ativa'):service.update(paused['id'],routine([entry('08:00',False)],enabled=True))
    assert next(r for r in service.list() if r['id']==paused['id'])['enabled'] is False

def test_concurrent_duplicate_groups_are_serialized(setup):
    service,_,_=setup
    def create(_):
        try:service.create(routine());return True
        except AutomationError:return False
    with ThreadPoolExecutor(max_workers=6) as pool:assert sum(pool.map(create,range(6)))==1
    assert len(service.list())==1

def test_cannot_inject_history_or_duplicate_entry_identity(setup):
    service,_,_=setup
    for items in [[{**entry('08:00'),'history':[]}],[entry('08:00',id='same'),entry('09:00',id='same')]]:
        with pytest.raises(AutomationError):service.create(routine(items))
