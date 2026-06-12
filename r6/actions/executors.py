"""
Action executors — Bland.ai (phone calls) and Twilio (SMS).

SIMULATION MODE: when the relevant API keys are absent, executors return a
successful simulated result instead of making network calls. This keeps
local dev, CI, and the demo stack fully functional with zero credentials,
matching the contract careagents.cloud used before this module existed.

No retries by design: a double-placed phone call is worse than a failed one.
"""

import base64
import logging
import os
import secrets
from dataclasses import dataclass

import requests

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = 30  # seconds


@dataclass
class ExecutionResult:
    ok: bool
    simulated: bool
    external_ref: str | None = None
    error: str | None = None


def _webhook_url(provider, action_id):
    base = os.environ.get('PUBLIC_BASE_URL', 'https://app.healthclaw.io')
    secret = os.environ.get('ACTIONS_WEBHOOK_SECRET', '')
    url = '%s/r6/actions/callback/%s?action_id=%s' % (base, provider, action_id)
    if secret:
        url += '&secret=%s' % secret
    return url


def _execute_call(payload, action_id):
    phone = payload.get('phone')
    if not phone:
        return ExecutionResult(ok=False, simulated=False,
                               error='phone number is required')
    api_key = os.environ.get('BLAND_AI_API_KEY')
    if not api_key:
        return ExecutionResult(ok=True, simulated=True,
                               external_ref='sim-' + secrets.token_hex(6))
    resp = requests.post(
        'https://api.bland.ai/v1/calls',
        headers={'Authorization': api_key,
                 'Content-Type': 'application/json'},
        json={
            'phone_number': phone,
            'task': payload.get('body', ''),
            'voice': 'maya',
            'webhook': _webhook_url('bland', action_id),
        },
        timeout=REQUEST_TIMEOUT,
    )
    if resp.status_code != 200:
        logger.error('Bland.ai error %s', resp.status_code)
        return ExecutionResult(ok=False, simulated=False,
                               error='Call provider error (HTTP %s)' % resp.status_code)
    return ExecutionResult(ok=True, simulated=False,
                           external_ref=resp.json().get('call_id'))


def _execute_sms(payload, action_id):
    phone = payload.get('phone')
    if not phone:
        return ExecutionResult(ok=False, simulated=False,
                               error='phone number is required')
    sid = os.environ.get('TWILIO_ACCOUNT_SID')
    token = os.environ.get('TWILIO_AUTH_TOKEN')
    from_num = os.environ.get('TWILIO_FROM_NUMBER')
    if not (sid and token and from_num):
        return ExecutionResult(ok=True, simulated=True,
                               external_ref='sim-' + secrets.token_hex(6))
    auth = base64.b64encode(('%s:%s' % (sid, token)).encode()).decode()
    resp = requests.post(
        'https://api.twilio.com/2010-04-01/Accounts/%s/Messages.json' % sid,
        headers={'Authorization': 'Basic ' + auth},
        data={'To': phone, 'From': from_num, 'Body': payload.get('body', '')},
        timeout=REQUEST_TIMEOUT,
    )
    if resp.status_code not in (200, 201):
        logger.error('Twilio error %s', resp.status_code)
        return ExecutionResult(ok=False, simulated=False,
                               error='SMS provider error (HTTP %s)' % resp.status_code)
    return ExecutionResult(ok=True, simulated=False,
                           external_ref=resp.json().get('sid'))


_EXECUTORS = {
    'phone-call': _execute_call,
    'insurance-call': _execute_call,   # same transport, different script source
    'sms': _execute_sms,
}


def execute_action(kind, payload, action_id=None):
    """Dispatch to the executor for this action kind."""
    executor = _EXECUTORS.get(kind)
    if executor is None:
        return ExecutionResult(ok=False, simulated=False,
                               error='No executor for kind: %s' % kind)
    try:
        return executor(payload, action_id)
    except requests.RequestException as exc:
        logger.error('Executor network failure: %s', exc)
        return ExecutionResult(ok=False, simulated=False,
                               error='Provider unreachable')
