"""
Tests for flag-gated read authentication and the token-mint oracle lock.

The vulnerability: FHIR reads were gated only by the client-supplied
X-Tenant-Id header — no authentication. With READ_AUTH_ENABLED on, reads of
non-public tenants must present a step-up token bound to that tenant.

Default (flag off) must be a strict no-op: header-only reads keep working,
so deploying this code changes nothing until the flag is flipped.
"""

import pytest

from r6.stepup import generate_step_up_token


# A search GET returns a 200 searchset bundle even with an empty store, so it
# exercises the read path without needing seeded data.
READ_PATH = '/r6/fhir/Patient?_summary=count'


@pytest.fixture(autouse=True)
def _clean_read_auth_env(monkeypatch):
    """Each test starts with the read-auth flag and mint secret cleared.

    conftest sets PUBLIC_TENANTS in os.environ; tests that care about it set
    it explicitly via monkeypatch.
    """
    monkeypatch.delenv('READ_AUTH_ENABLED', raising=False)
    monkeypatch.delenv('INTERNAL_TOKEN_MINT_SECRET', raising=False)


# --- Flag OFF: behavior preserved (default no-op) ---

def test_read_flag_off_header_only_succeeds(client):
    """Flag off (default): header-only read returns 200 — unchanged."""
    resp = client.get(READ_PATH, headers={'X-Tenant-Id': 'private-tenant'})
    assert resp.status_code == 200


def test_read_flag_off_public_tenants_irrelevant(client, monkeypatch):
    """Flag off: even a non-public tenant reads fine without a token."""
    monkeypatch.setenv('PUBLIC_TENANTS', '')
    resp = client.get(READ_PATH, headers={'X-Tenant-Id': 'some-private-tenant'})
    assert resp.status_code == 200


# --- Flag ON ---

def test_read_flag_on_non_public_no_token_401(client, monkeypatch):
    monkeypatch.setenv('READ_AUTH_ENABLED', 'true')
    monkeypatch.setenv('PUBLIC_TENANTS', '')
    resp = client.get(READ_PATH, headers={'X-Tenant-Id': 'private-tenant'})
    assert resp.status_code == 401
    body = resp.get_json()
    assert body['resourceType'] == 'OperationOutcome'
    assert body['issue'][0]['code'] == 'security'
    assert 'requires authentication' in body['issue'][0]['diagnostics']


def test_read_flag_on_non_public_valid_token_200(client, monkeypatch):
    monkeypatch.setenv('READ_AUTH_ENABLED', '1')
    monkeypatch.setenv('PUBLIC_TENANTS', '')
    token = generate_step_up_token('private-tenant')
    resp = client.get(READ_PATH, headers={
        'X-Tenant-Id': 'private-tenant',
        'X-Step-Up-Token': token,
    })
    assert resp.status_code == 200


def test_read_flag_on_bearer_alias_200(client, monkeypatch):
    """Authorization: Bearer <token> is accepted as a token alias."""
    monkeypatch.setenv('READ_AUTH_ENABLED', 'yes')
    monkeypatch.setenv('PUBLIC_TENANTS', '')
    token = generate_step_up_token('private-tenant')
    resp = client.get(READ_PATH, headers={
        'X-Tenant-Id': 'private-tenant',
        'Authorization': f'Bearer {token}',
    })
    assert resp.status_code == 200


def test_read_flag_on_token_wrong_tenant_401(client, monkeypatch):
    """A valid token bound to a DIFFERENT tenant must be rejected."""
    monkeypatch.setenv('READ_AUTH_ENABLED', 'true')
    monkeypatch.setenv('PUBLIC_TENANTS', '')
    token = generate_step_up_token('other-tenant')
    resp = client.get(READ_PATH, headers={
        'X-Tenant-Id': 'private-tenant',
        'X-Step-Up-Token': token,
    })
    assert resp.status_code == 401
    assert resp.get_json()['issue'][0]['code'] == 'security'


def test_read_flag_on_public_tenant_no_token_200(client, monkeypatch):
    monkeypatch.setenv('READ_AUTH_ENABLED', 'true')
    monkeypatch.setenv('PUBLIC_TENANTS', 'desktop-demo,winters-demo')
    resp = client.get(READ_PATH, headers={'X-Tenant-Id': 'desktop-demo'})
    assert resp.status_code == 200


def test_read_flag_on_discovery_metadata_no_token_200(client, monkeypatch):
    """Discovery endpoint reads need no auth even with the flag on."""
    monkeypatch.setenv('READ_AUTH_ENABLED', 'true')
    monkeypatch.setenv('PUBLIC_TENANTS', '')
    resp = client.get('/r6/fhir/metadata')
    assert resp.status_code == 200


# --- Writes are independent of the read flag ---

def test_write_requires_step_up_flag_off(client, monkeypatch, sample_patient):
    monkeypatch.delenv('READ_AUTH_ENABLED', raising=False)
    resp = client.post('/r6/fhir/Patient',
                       json=sample_patient,
                       headers={'X-Tenant-Id': 'private-tenant'})
    assert resp.status_code == 401


def test_write_requires_step_up_flag_on(client, monkeypatch, sample_patient):
    monkeypatch.setenv('READ_AUTH_ENABLED', 'true')
    monkeypatch.setenv('PUBLIC_TENANTS', '')
    resp = client.post('/r6/fhir/Patient',
                       json=sample_patient,
                       headers={'X-Tenant-Id': 'private-tenant'})
    assert resp.status_code == 401


# --- Token-mint oracle lock ---

def test_mint_unset_secret_open(client, monkeypatch):
    """Unset INTERNAL_TOKEN_MINT_SECRET → open (backward-compatible)."""
    monkeypatch.delenv('INTERNAL_TOKEN_MINT_SECRET', raising=False)
    resp = client.post('/r6/fhir/internal/step-up-token',
                       json={'tenant_id': 'private-tenant'})
    assert resp.status_code == 200
    assert 'token' in resp.get_json()


def test_mint_secret_set_missing_header_403(client, monkeypatch):
    monkeypatch.setenv('INTERNAL_TOKEN_MINT_SECRET', 'top-secret')
    resp = client.post('/r6/fhir/internal/step-up-token',
                       json={'tenant_id': 'private-tenant'})
    assert resp.status_code == 403


def test_mint_secret_set_wrong_header_403(client, monkeypatch):
    monkeypatch.setenv('INTERNAL_TOKEN_MINT_SECRET', 'top-secret')
    resp = client.post('/r6/fhir/internal/step-up-token',
                       json={'tenant_id': 'private-tenant'},
                       headers={'X-Internal-Secret': 'wrong'})
    assert resp.status_code == 403


def test_mint_secret_set_correct_header_200(client, monkeypatch):
    monkeypatch.setenv('INTERNAL_TOKEN_MINT_SECRET', 'top-secret')
    resp = client.post('/r6/fhir/internal/step-up-token',
                       json={'tenant_id': 'private-tenant'},
                       headers={'X-Internal-Secret': 'top-secret'})
    assert resp.status_code == 200
    assert 'token' in resp.get_json()
