"""Descoberta LAN sem consultar cloud nem exibir chaves."""
import contextlib
import io
import json
import logging
from pathlib import Path
import tinytuya

TARGET = 'CONFIGURE_TUYA_DEVICE_ID'
MAC = '3c0b599fbfe3'

def discover():
    logging.getLogger('tinytuya').setLevel(logging.CRITICAL)
    with contextlib.redirect_stdout(io.StringIO()):
        found = tinytuya.deviceScan(verbose=False, maxretry=12, color=False, poll=False)
    matches = []
    for ip, info in found.items():
        mac = str(info.get('mac', '')).replace(':', '').replace('-', '').lower()
        if info.get('gwId', info.get('id')) == TARGET or mac == MAC:
            matches.append({'ip': info.get('ip', ip), 'version': info.get('version'), 'id': TARGET})
    Path(__file__).with_name('discovery.json').write_text(json.dumps(matches, indent=2), encoding='utf-8')
    print(json.dumps({'matches': matches, 'devices_seen': len(found)}, indent=2))

if __name__ == '__main__':
    discover()
