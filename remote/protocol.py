"""Contrato remoto sem endereços LAN, DPS ou credenciais Tuya."""
import hashlib
import json
import math
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, StrictStr

RULES = {
    'switch': bool, 'temp_set': (16, 31),
    'mode': ('auto', 'cold', 'hot', 'wet', 'wind'),
    'fan_speed_enum': ('auto', 'high', 'middle', 'low'),
    **{key: bool for key in ('mode_eco', 'sleep', 'cleaning', 'switch_vertical', 'switch_horizontal')},
}
TERMINAL = {'confirmed', 'uncertain', 'expired', 'rejected', 'failed'}


def validate_value(code, value):
    if code not in RULES:
        raise ValueError('unknown_control')
    rule = RULES[code]
    if rule is bool:
        valid = type(value) is bool
    elif code == 'temp_set':
        valid = type(value) is int and rule[0] <= value <= rule[1]
    else:
        valid = type(value) is str and value in rule
    if not valid:
        raise ValueError('invalid_value')


def canonical(data):
    return json.dumps(data, sort_keys=True, separators=(',', ':'), allow_nan=False)


def fingerprint(data):
    return hashlib.sha256(canonical(data).encode()).hexdigest()


def safe_observation(reply):
    """Só valores de controles conhecidos; respostas brutas nunca atravessam a ponte."""
    if not isinstance(reply, dict):
        return None
    state = {}
    raw_state=reply.get('state', {})
    if not isinstance(raw_state,dict):
        return None
    for code, value in raw_state.items():
        try:
            validate_value(code, value)
            state[code] = value
        except ValueError:
            pass
    stamp = reply.get('timestamp')
    if type(stamp) not in (int, float) or not 0<stamp<1e12 or not math.isfinite(stamp):
        return None
    return {'state': state, 'timestamp': stamp}


class NewCommand(BaseModel):
    model_config = ConfigDict(extra='forbid')
    request_id: UUID
    code: StrictStr
    value: StrictBool | StrictInt | StrictStr
    ttl_seconds: StrictInt = Field(default=30, ge=1, le=120)


class Envelope(BaseModel):
    model_config = ConfigDict(extra='forbid')
    version: Literal[1]
    command_id: UUID
    home_id: StrictStr
    agent_id: StrictStr
    device_id: StrictStr
    code: StrictStr
    value: StrictBool | StrictInt | StrictStr
    issued_at: float = Field(allow_inf_nan=False)
    expires_at: float = Field(allow_inf_nan=False)


class AgentResult(BaseModel):
    model_config = ConfigDict(extra='forbid')
    status: Literal['confirmed', 'uncertain', 'expired', 'rejected', 'failed']
    reason: Literal['observed', 'send_uncertain', 'read_failed', 'state_mismatch', 'expired',
                    'clock_skew', 'unmapped', 'restart_uncertain', 'invalid_command']
    observation: dict | None = None
