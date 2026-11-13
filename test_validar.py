from validar import validate_local


def test_diagnostic_reads_only_and_does_not_include_secrets(monkeypatch):
    monkeypatch.setenv('TUYA_IP', '192.168.1.3')
    monkeypatch.setenv('TUYA_VERSION', '3.4')
    monkeypatch.setenv('TUYA_LOCAL_KEY', 'DO_NOT_EXPOSE')
    class ReadOnly:
        def status(self):
            return {'state': {'switch': False}, 'available': ['switch'], 'timestamp': 123}
        def command(self, *args):
            raise AssertionError('Diagnóstico não pode enviar comandos')
    report = validate_local(ReadOnly())
    assert report['connection'] == 'LAN'
    assert report['state']['switch'] is False
    assert report['ip'] == '192.168.1.3'
    assert 'DO_NOT_EXPOSE' not in str(report)
