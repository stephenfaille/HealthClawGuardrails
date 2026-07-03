"""Framework-neutral bridge for HealthClaw's MCP tools.

Lets an agent on ANY framework (OpenAI Agents SDK / Responses API, Google
Gemini function-calling, LangChain, or plain HTTP) use the HealthClaw guardrailed
tools without an MCP client library. Two pieces:

  1. Pure schema transforms from the tool manifest (adapters/tools.manifest.json,
     generated from the MCP server's `tools/list`) into each framework's tool
     format.
  2. A thin relay (`HealthClawClient`) that forwards a tool call to the MCP
     server's `/mcp/rpc` JSON-RPC bridge, carrying tenant + step-up headers.

Guardrails are enforced server-side regardless of the calling framework, so this
adds no trust surface — it's a format shim.
"""

import json
import os

_DEFAULT_MANIFEST = os.path.join(os.path.dirname(__file__), "tools.manifest.json")

# JSON-Schema keywords Gemini's FunctionDeclaration schema subset accepts.
_GEMINI_SCHEMA_KEYS = {
    "type", "description", "enum", "format", "items", "properties",
    "required", "nullable",
}


def load_manifest(path=None):
    """Load the tool manifest (list of {name, description, inputSchema, ...})."""
    with open(path or _DEFAULT_MANIFEST) as f:
        return json.load(f)


def _tools(manifest):
    return manifest["tools"] if isinstance(manifest, dict) else manifest


def to_openai_tools(manifest):
    """Manifest -> OpenAI function tools (Chat Completions / Assistants shape).

    inputSchema is already valid JSON Schema, which OpenAI consumes directly.
    """
    out = []
    for t in _tools(manifest):
        out.append({
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t.get("description", ""),
                "parameters": t.get("inputSchema", {"type": "object"}),
            },
        })
    return out


def _clean_gemini_schema(schema):
    """Recursively reduce a JSON Schema to Gemini's accepted subset."""
    if not isinstance(schema, dict):
        return schema
    cleaned = {}
    for k, v in schema.items():
        if k not in _GEMINI_SCHEMA_KEYS:
            continue
        if k == "properties" and isinstance(v, dict):
            cleaned[k] = {pk: _clean_gemini_schema(pv) for pk, pv in v.items()}
        elif k == "items":
            cleaned[k] = _clean_gemini_schema(v)
        else:
            cleaned[k] = v
    return cleaned


def to_gemini_declarations(manifest):
    """Manifest -> Gemini FunctionDeclaration list (annotations dropped, schema
    reduced to Gemini's accepted subset)."""
    out = []
    for t in _tools(manifest):
        out.append({
            "name": t["name"],
            "description": t.get("description", ""),
            "parameters": _clean_gemini_schema(
                t.get("inputSchema", {"type": "object"})),
        })
    return out


class HealthClawClient:
    """Relay tool calls to the MCP server's /mcp/rpc JSON-RPC bridge.

    Guardrail context travels as headers: X-Tenant-Id (+ X-Step-Up-Token for
    write-tier tools). The server enforces redaction / audit / step-up.
    """

    def __init__(self, mcp_base_url, tenant_id, step_up_token=None,
                 agent_id=None, session=None):
        self.rpc_url = mcp_base_url.rstrip("/") + "/mcp/rpc"
        self.tenant_id = tenant_id
        self.step_up_token = step_up_token
        self.agent_id = agent_id
        self._session = session  # inject for testing; else lazy `requests`

    def _headers(self):
        h = {"Content-Type": "application/json", "X-Tenant-Id": self.tenant_id}
        if self.step_up_token:
            h["X-Step-Up-Token"] = self.step_up_token
        if self.agent_id:
            h["X-Agent-Id"] = self.agent_id
        return h

    def call(self, tool_name, arguments=None, request_id=1):
        payload = {
            "jsonrpc": "2.0", "id": request_id, "method": "tools/call",
            "params": {"name": tool_name, "arguments": arguments or {}},
        }
        sess = self._session
        if sess is None:
            import requests
            sess = requests
        resp = sess.post(self.rpc_url, headers=self._headers(),
                         data=json.dumps(payload))
        body = resp.json()
        if "error" in body:
            return {"error": body["error"]}
        return body.get("result")

    def list_tools(self):
        payload = {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
        sess = self._session
        if sess is None:
            import requests
            sess = requests
        resp = sess.post(self.rpc_url, headers=self._headers(),
                         data=json.dumps(payload))
        return resp.json().get("result", {}).get("tools", [])
