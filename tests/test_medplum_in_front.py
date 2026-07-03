"""HealthClaw-in-front-of-Medplum: proves the guardrail stack (PHI redaction,
audit, step-up) wraps a real MedplumProxy. Only the upstream HTTP + OAuth token
are mocked — the MedplumProxy logic and the FHIR route guardrails are real.
"""
import json
from unittest.mock import patch, MagicMock

from r6.fhir_proxy import MedplumProxy
from r6.models import AuditEventRecord


UNREDACTED_MEDPLUM_PATIENT = {
    "resourceType": "Patient", "id": "pt-medplum",
    "name": [{"family": "Hernandez", "given": ["Rosa"]}],
    "identifier": [{"system": "http://hl7.org/fhir/sid/us-ssn",
                    "value": "123-45-6789"}],
    "telecom": [{"system": "phone", "value": "617-555-0199"}],
    "address": [{"line": ["42 Real St"], "city": "Boston"}],
    "contact": [{"name": {"family": "Hernandez", "given": ["Miguel"]},
                 "telecom": [{"system": "phone", "value": "617-555-0142"}]}],
    "birthDate": "1980-07-04",
}


def _medplum_proxy_returning(resource, status=200):
    proxy = MedplumProxy("https://api.medplum.com/fhir/R4", "cid", "secret")
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = resource
    proxy._client.get = MagicMock(return_value=resp)
    proxy._client.post = MagicMock(return_value=resp)
    return proxy


def test_guardrails_redact_and_audit_medplum_read(client, tenant_headers,
                                                  tenant_id, app):
    proxy = _medplum_proxy_returning(UNREDACTED_MEDPLUM_PATIENT)
    with patch("r6.routes.get_proxy_for_request", return_value=proxy):
        resp = client.get("/r6/fhir/Patient/pt-medplum", headers=tenant_headers)
    assert resp.status_code == 200
    body = resp.get_json()
    blob = json.dumps(body)

    # PHI redaction applied to the Medplum-returned resource
    assert body["name"][0]["family"] == "H."                 # name truncated
    assert body["telecom"][0]["value"] == "[Redacted]"       # phone masked
    ident = body["identifier"][0]["value"]
    assert ident.startswith("***") and ident.endswith("6789")  # SSN masked
    assert "42 Real St" not in blob                          # address line gone
    assert "617-555-0142" not in blob                        # emergency contact gone
    assert body.get("_source") == "upstream"                 # came from Medplum

    # Immutable audit recorded for the Medplum-backed read
    with app.app_context():
        n = AuditEventRecord.query.filter_by(
            tenant_id=tenant_id, resource_type="Patient",
            event_type="read").count()
        assert n >= 1

    proxy._client.get.assert_called_once()


def test_medplum_write_gated_by_step_up_before_upstream(client, tenant_headers):
    proxy = _medplum_proxy_returning({"resourceType": "Patient", "id": "x"}, 201)
    with patch("r6.routes.get_proxy_for_request", return_value=proxy):
        resp = client.post("/r6/fhir/Patient", headers=tenant_headers,
                           json={"resourceType": "Patient",
                                 "name": [{"family": "Test"}]})
    # No step-up token -> blocked by the guardrail BEFORE any Medplum call
    assert resp.status_code == 401
    proxy._client.post.assert_not_called()
