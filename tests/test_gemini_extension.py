"""Drift guards for the Gemini CLI extension manifest.

gemini-extension.json makes HealthClaw installable via `gemini extensions
install github.com/aks129/HealthClawGuardrails`. It points at the same remote
MCP server as the official MCP registry entry (server.json) and must track the
released version — these tests fail the suite if either drifts (RELEASING.md).
"""

import json
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _ext():
    return json.loads((ROOT / "gemini-extension.json").read_text())


def _version():
    return tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]


def test_version_tracks_release():
    assert _ext()["version"] == _version(), (
        "gemini-extension.json version is stale vs pyproject (RELEASING.md step 2)")


def test_remote_url_matches_registry_server_json():
    ext = _ext()
    server = json.loads((ROOT / "server.json").read_text())
    registry_url = server["remotes"][0]["url"]
    ext_url = ext["mcpServers"]["healthclaw"]["httpUrl"]
    assert ext_url == registry_url, (
        "Gemini extension httpUrl must match the MCP registry remote URL")


def test_context_file_present():
    ext = _ext()
    assert ext.get("contextFileName") == "GEMINI.md"
    assert (ROOT / "GEMINI.md").exists()


def test_default_tenant_is_public_demo():
    # The extension ships with the synthetic public demo tenant, never a real one.
    headers = _ext()["mcpServers"]["healthclaw"].get("headers", {})
    assert headers.get("X-Tenant-Id") == "desktop-demo"
