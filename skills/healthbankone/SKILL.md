---
name: healthbankone
description: >
  Pull verified medical records and digital-identity context from Health Bank
  One (https://www.healthbankone.com) via their MCP server. HBO uses OAuth 2.x
  with per-consumer authorization, so this skill drives an authorization-code
  grant first, then runs the MCP pull, then ingests the redacted bundle into a
  HealthClaw tenant. Use when the user wants to add HBO as a source alongside
  HealthEx and Fasten Connect. Triggers on prompts like "connect Health Bank
  One", "pull from HBO", "verify identity through Health Bank One".
version: 0.1.0-scaffold
author: Eugene Vestel (fhiriq.com)
license: MIT
status: scaffold — endpoints + scopes + tool names TBD after 2026-06-04 call
references:
  hbo_home: https://www.healthbankone.com
  hbo_developer_program: https://www.healthbankone.com/MCP
  hbo_launch_announcement: https://www.prweb.com/releases/health-bank-one-gives-ai-applications-access-to-trusted-digital-identity-and-verified-medical-records-through-mcp-302770638.html
  call_prep: https://github.com/aks129/HealthClawGuardrails/blob/main/docs/healthbankone-call-prep.md
  healthex_skill: https://github.com/aks129/HealthClawGuardrails/tree/main/skills/healthex-export-redacted
  fasten_skill: https://github.com/aks129/HealthClawGuardrails/tree/main/skills/fasten-connect
---

# Health Bank One — pull verified records via MCP

> **Status:** scaffold. Endpoints, scopes, and tool names will be filled in
> after the 2026-06-04 developer call. See
> [`docs/healthbankone-call-prep.md`](../../docs/healthbankone-call-prep.md)
> for what we already know and the call agenda.

HBO sits in our health-data source matrix as the **OAuth-pulled, identity-verified** equivalent of:

- **HealthEx** (token-pulled, no per-consumer consent — see `healthex-export-redacted`)
- **Fasten Connect** (webhook-pushed, TEFCA-verified — see `fasten-connect`)

## What HBO gives us that HealthEx and Fasten don't

- **Digital Identity verification baked in.** IAL2 / AAL2 / PSD2-grade. Once a consumer authorizes HealthClaw, we get identity attributes alongside the clinical bundle — no separate CLEAR / ID.me step.
- **Paper-record retrieval.** HBO's pipeline includes mail-based requests for records that aren't yet digital. Useful for older patients with significant pre-2015 history.
- **Writebacks.** The Engagement service exposes authorized writebacks; HealthClaw can publish curatr fixes or annotated documents back to the consumer's HBO account.
- **Insurance Context.** Verified payer details — possibly the strongest case for HBO over the other two sources.

## Setup (post-call)

> The bracketed values are placeholders until the call.

### 1. Register HealthClaw as an HBO client

`<TODO: developer portal URL>`. Probably requires:
- Business name + use case description
- Redirect URIs: `https://app.healthclaw.io/hbo/callback` (Railway) and `http://localhost:5000/hbo/callback` (local dev)
- Scopes requested: `<TODO: list from call>` — likely something like `identity.read patient.read patient.write offline_access`

Store `HBO_CLIENT_ID` and `HBO_CLIENT_SECRET` on the Railway HealthClawGuardrails service.

### 2. Run the authorization dance

```bash
# Will be invoked from Telegram as /hbo-connect
python scripts/healthbankone_oauth.py authorize \
  --tenant-id ev-personal-hbo \
  --client-id "$HBO_CLIENT_ID" \
  --scopes "<TODO>"
```

Opens the HBO authorize URL in a browser; consumer logs in + grants; HBO redirects back to our callback with an `authorization_code`; we exchange for `access_token` + `refresh_token`; tokens cached in Redis (Railway) or macOS Keychain (Mac mini).

### 3. Pull the records

```bash
python scripts/export_healthbankone_mcp.py \
  --tenant-id ev-personal-hbo \
  --output ~/.healthclaw/exports/hbo-$(date +%Y-%m-%d).json
```

What the script does (mirrors `export_healthex_mcp.py`):

1. Loads access token from cache; refreshes if expired
2. Opens an MCP Streamable HTTP session to `<TODO: HBO MCP URL>` with `Authorization: Bearer <access_token>`
3. Calls each tool in the Health Context category (`<TODO: health.summary, health.medications, …>`)
4. Optionally calls Digital Identity tools (`<TODO: identity.verify, …>`) for the identity bundle
5. Redacts PHI in-process via `scripts/healthclaw_redact.py` — raw MCP response never touches disk
6. Writes the redacted snapshot to disk

### 4. Ingest into HealthClaw

```bash
python scripts/import_healthex.py \
  --bundle-file ~/.healthclaw/exports/hbo-2026-06-04.json \
  --tenant-id ev-personal-hbo \
  --step-up-secret "$STEP_UP_SECRET"
```

The `import_healthex.py` script is source-agnostic — it just POSTs a FHIR Bundle to `/Bundle/$ingest-context`. Works for HBO output unchanged.

## OpenClaw slash commands (to be added)

| Command | What it does |
|---|---|
| `/hbo-connect` | Returns the HBO authorization URL; user clicks, logs in, grants; webhook callback persists the tokens |
| `/hbo-pull` | Runs the export + redact + ingest pipeline; pings the chat when records arrive |
| `/hbo-revoke` | Calls HBO's revoke endpoint to terminate the grant; deletes cached tokens |

## Environment variables (to add)

| Variable | Required | Notes |
|---|---|---|
| `HBO_CLIENT_ID` | Yes | From HBO developer portal |
| `HBO_CLIENT_SECRET` | Yes | Same |
| `HBO_AUTHORIZATION_ENDPOINT` | Yes | `<TODO from call>` |
| `HBO_TOKEN_ENDPOINT` | Yes | `<TODO from call>` |
| `HBO_MCP_URL` | Yes | `<TODO from call>` |
| `HBO_REDIRECT_URI` | Yes | Defaults to `https://app.healthclaw.io/hbo/callback` |
| `HBO_SCOPES` | Optional | Space-separated scope list; default from call |

## SHARP-on-MCP compatibility check

If HBO's MCP server advertises SHARP (`capabilities.experimental.fhir_context_required`) or the PromptOpinion FHIR Extension, HealthClaw can also act as a *forwarding* layer — an MCP client that pulls from HBO using SHARP headers on every call instead of pre-pulling a snapshot. This eliminates the export-to-disk step entirely and matches the pattern PromptOpinion uses with us today. **Ask on the call whether they advertise either spec.** If yes, we can offer to demo HealthClaw + HBO as a SHARP-compliant pair.

## Comparison to existing skills

| Aspect | HealthEx | Fasten Connect | Health Bank One |
|---|---|---|---|
| Source skill | `healthex-export-redacted` | `fasten-connect` | `healthbankone` (this one) |
| Auth | Bearer token in env | Stitch widget public key + webhook HMAC | OAuth 2.x per-consumer |
| Identity verification | Done by HealthEx | CLEAR / ID.me via TEFCA | HBO Digital Identity (IAL2/AAL2) |
| Transport | MCP Streamable HTTP pull | Webhook push | MCP Streamable HTTP pull |
| Data freshness | On-demand via `update_records` | Push on EHR change | On-demand via pull (refresh cadence TBD) |
| FHIR format | R4 + US Core | R4 NDJSON | R4 (per their materials) |
| Writebacks | No | No | Yes — Engagement service |
| Pricing | Free / paid tiers | Paid keys (test_ / live_) | Bootstrap free, post-launch TBD |
