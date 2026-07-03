import json
from unittest.mock import MagicMock

from adapters.healthclaw_bridge import (
    load_manifest, to_openai_tools, to_gemini_declarations, HealthClawClient,
)

_MANIFEST = {
    "tools": [
        {"name": "fhir_read", "description": "Read a FHIR resource",
         "inputSchema": {"type": "object",
                         "properties": {"resource_type": {"type": "string"},
                                        "resource_id": {"type": "string"}},
                         "required": ["resource_type", "resource_id"],
                         "additionalProperties": False,
                         "$schema": "https://json-schema.org/draft/2020-12/schema"},
         "annotations": {"readOnlyHint": True}},
    ]
}


def test_manifest_loads_from_repo():
    m = load_manifest()
    names = {t["name"] for t in m["tools"]}
    assert "fhir_read" in names and "fhir_commit_write" in names
    assert m["tool_count"] == len(m["tools"])


def test_to_openai_tools_shape():
    tools = to_openai_tools(_MANIFEST)
    assert tools[0]["type"] == "function"
    fn = tools[0]["function"]
    assert fn["name"] == "fhir_read"
    assert fn["parameters"]["required"] == ["resource_type", "resource_id"]


def test_to_gemini_drops_unsupported_keys():
    decls = to_gemini_declarations(_MANIFEST)
    d = decls[0]
    assert d["name"] == "fhir_read"
    params = d["parameters"]
    # Gemini subset: unsupported JSON-Schema keywords removed
    assert "additionalProperties" not in params
    assert "$schema" not in params
    # meaningful structure preserved
    assert params["type"] == "object"
    assert set(params["properties"].keys()) == {"resource_type", "resource_id"}
    assert params["required"] == ["resource_type", "resource_id"]
    # annotations are not part of a FunctionDeclaration
    assert "annotations" not in d


def test_client_builds_jsonrpc_call_with_headers():
    sess = MagicMock()
    resp = MagicMock()
    resp.json.return_value = {"jsonrpc": "2.0", "id": 1,
                             "result": {"resourceType": "Patient"}}
    sess.post.return_value = resp

    client = HealthClawClient("https://mcp.example", tenant_id="t1",
                              step_up_token="tok", session=sess)
    result = client.call("fhir_read",
                         {"resource_type": "Patient", "resource_id": "p1"})

    assert result == {"resourceType": "Patient"}
    args, kwargs = sess.post.call_args
    assert args[0] == "https://mcp.example/mcp/rpc"
    assert kwargs["headers"]["X-Tenant-Id"] == "t1"
    assert kwargs["headers"]["X-Step-Up-Token"] == "tok"
    sent = json.loads(kwargs["data"])
    assert sent["method"] == "tools/call"
    assert sent["params"]["name"] == "fhir_read"
    assert sent["params"]["arguments"]["resource_id"] == "p1"


def test_client_no_step_up_header_when_absent():
    sess = MagicMock()
    sess.post.return_value = MagicMock(json=lambda: {"result": {}})
    client = HealthClawClient("https://mcp.example", tenant_id="t1", session=sess)
    client.call("fhir_search", {"resource_type": "Observation"})
    _, kwargs = sess.post.call_args
    assert "X-Step-Up-Token" not in kwargs["headers"]


def test_client_surfaces_error():
    sess = MagicMock()
    sess.post.return_value = MagicMock(
        json=lambda: {"error": {"code": -32000, "message": "boom"}})
    client = HealthClawClient("https://mcp.example", tenant_id="t1", session=sess)
    out = client.call("fhir_read", {})
    assert out["error"]["message"] == "boom"
