import pytest
from mapear import extract_ids, safe_error, DiagnosticCloud

def test_explicit_ids_only():
    assert extract_ids({'functions': [{'code': 'switch'}, {'code': 'temp_set'}]}) == {}
    assert extract_ids({'properties': [{'code': 'switch', 'dp_id': 1}, {'code': 'temp_set', 'dpId': 2}, {'code': 'local_key', 'dp_id': 3}]}) == {'switch': 1, 'temp_set': 2}

def test_conflicting_ids_rejected():
    with pytest.raises(ValueError):
        extract_ids([{'code': 'switch', 'dp_id': 1}, {'code': 'switch', 'dp_id': 2}])
    with pytest.raises(ValueError):
        extract_ids([{'code': 'switch', 'dp_id': 1}, {'code': 'sleep', 'dp_id': 1}])

def test_errors_do_not_expose_credentials():
    assert safe_error({'code': 1004, 'msg': 'sign invalid'}) == 'código 1004: assinatura rejeitada'
    assert 'SECRET' not in safe_error({'code': 'SECRET', 'msg': 'SECRET', 'result': {'access_token': 'SECRET'}})
    assert 'SECRET' not in safe_error({'code': 1004, 'msg': {'nested': 'SECRET'}})

def test_token_failure_captured_without_raw_reply(monkeypatch):
    import tinytuya
    monkeypatch.setattr(tinytuya.Cloud, '_tuyaplatform', lambda *a, **kw: {'success': False, 'code': 1004, 'msg': 'sign invalid'})
    cloud = DiagnosticCloud(apiRegion='us', apiKey='test-id', apiSecret='test-secret')
    assert not cloud.token
    assert cloud.last_failure == 'código 1004: assinatura rejeitada'
