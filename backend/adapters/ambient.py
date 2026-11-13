"""Telemetria somente leitura, habilitada apenas por esquema explícito do aparelho."""
import json
import math
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CELSIUS = {'°C', '℃', 'C', 'celsius'}


def unavailable(reason):
    return {'available': False, 'value': None, 'unit': '°C', 'observed_at': None, 'reason': reason}


def ambient_reading(dps, timestamp, report_dir=None, device_id=None):
    """Não infere temperatura por posição, aparência do valor ou DP convencional."""
    directory = Path(report_dir) if report_dir else ROOT / 'reports'
    target = device_id or os.getenv('TUYA_DEVICE_ID', 'CONFIGURE_TUYA_DEVICE_ID')
    for path in sorted(directory.glob('esquema-completo-*.json'), reverse=True)[:20]:
        try:
            report = json.loads(path.read_text(encoding='utf-8'))
            if report.get('device_id') != target or not report.get('cloud_requested'):
                continue
            properties = report.get('properties', [])
            candidates = []
            for row in properties:
                if row.get('code') != 'temp_current':
                    continue
                source = row.get('source')
                if not report.get('queries', {}).get(source, {}).get('ok'):
                    continue
                if source == 'things_model':
                    if row.get('access') not in {'r', 'ro', 'rw'}:
                        continue
                elif source == 'specifications_v11' and row.get('section') == 'status':
                    pass
                else:
                    continue
                dp, scale, unit = row.get('dp_id'), row.get('scale'), row.get('unit')
                if type(dp) is not int or dp < 1 or type(scale) is not int or not 0 <= scale <= 6:
                    continue
                if unit not in CELSIUS or row.get('type') not in {'Integer', 'integer', 'int', 'value'}:
                    continue
                candidates.append((dp, scale, row.get('type_spec', {})))
            if not candidates:
                continue
            if len({(dp, scale) for dp, scale, _ in candidates}) != 1:
                return unavailable('schema_conflict')
            dp, scale, spec = candidates[0]
            raw = dps.get(str(dp))
            if type(raw) not in {int, float} or not math.isfinite(raw):
                return unavailable('reading_missing')
            # Valores ficam na escala inteira definida pelo esquema Tuya.
            if isinstance(spec, dict):
                low, high = spec.get('min'), spec.get('max')
                if type(low) in {int, float} and raw < low:
                    return unavailable('reading_invalid')
                if type(high) in {int, float} and raw > high:
                    return unavailable('reading_invalid')
            value = raw / (10 ** scale)
            return {'available': True, 'value': value, 'unit': '°C',
                    'observed_at': timestamp, 'source': 'device'}
        except (ValueError, OSError, TypeError, AttributeError):
            continue
    return unavailable('schema_unconfirmed')
