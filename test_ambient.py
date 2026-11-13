import json
import pytest
from backend.adapters.ambient import ambient_reading

TARGET='test-device'

def report(directory, *, dp=177, scale=1, unit='°C', device=TARGET, extra=None):
    row={'source':'things_model','code':'temp_current','dp_id':dp,'type':'value',
         'access':'ro','scale':scale,'unit':unit,'type_spec':{'min':-200,'max':800}}
    properties=[row, *([extra] if extra else [])]
    data={'device_id':device,'cloud_requested':True,'queries':{'things_model':{'ok':True}},'properties':properties}
    (directory/'esquema-completo-20261023.json').write_text(json.dumps(data),encoding='utf-8')

def test_unconfirmed_dp3_is_never_presented_as_ambient(tmp_path):
    result=ambient_reading({'3':22},123,tmp_path,TARGET)
    assert result['available'] is False and result['value'] is None

def test_explicit_device_schema_maps_actual_id_and_scale(tmp_path):
    report(tmp_path)
    result=ambient_reading({'3':99,'177':221},123,tmp_path,TARGET)
    assert result=={'available':True,'value':22.1,'unit':'°C','observed_at':123,'source':'device'}

@pytest.mark.parametrize('scale,unit,device',[(None,'°C',TARGET),(True,'°C',TARGET),(1,'°F',TARGET),(1,'°C','different-device')])
def test_incomplete_or_wrong_device_schema_is_not_used(tmp_path,scale,unit,device):
    report(tmp_path,scale=scale,unit=unit,device=device)
    assert ambient_reading({'177':221},123,tmp_path,TARGET)['available'] is False

@pytest.mark.parametrize('raw',[True,'221',None,9999])
def test_invalid_raw_values_do_not_become_temperatures(tmp_path,raw):
    report(tmp_path)
    assert ambient_reading({'177':raw},123,tmp_path,TARGET)['available'] is False

def test_conflicting_associations_are_not_silently_chosen(tmp_path):
    other={'source':'things_model','code':'temp_current','dp_id':178,'type':'value','access':'ro','scale':1,'unit':'°C'}
    report(tmp_path,extra=other)
    assert ambient_reading({'177':221,'178':222},123,tmp_path,TARGET)['reason']=='schema_conflict'
