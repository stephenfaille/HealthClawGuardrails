# Health Bank One — call prep

**Call date:** today (2026-06-04)
**Goal:** review HBO's MCP server, get developer access, scope a HealthClaw connection that mirrors the HealthEx and Fasten patterns we already ship

## What we know going in

Source: [healthbankone.com](https://www.healthbankone.com), [PR Web launch announcement](https://www.prweb.com/releases/health-bank-one-gives-ai-applications-access-to-trusted-digital-identity-and-verified-medical-records-through-mcp-302770638.html), [Eugene's substack review](https://evestel.substack.com/p/comparing-consumer-health-data-apps)

- **Launched MCP:** 2026-05-13, ~3 weeks ago. Technical docs were promised for "June 2026" — i.e. now. Bootstrap Developer Program at `healthbankone.com/MCP` (returns 404 today; probably invite-gated).
- **Three service categories:**
  - **Digital Identity** — IAL2 / AAL2 / PSD2-grade identity verification (mobile-based, "consumer onboarding, authentication, authorization, digital signature")
  - **Health Context** — verified, consolidated medical records + insurance details, normalized + deduplicated, stored in FHIR. Covers medications, conditions, allergies, lab results, immunizations, procedures, visits/encounters, vitals, care plans, clinical documents.
  - **Engagement** — secure consumer communication + writebacks ("write back authorized outputs to the consumer's Health Bank One account")
- **Auth model:** OAuth 2.x. Access is "tokenized, purpose-scoped, auditable, revocable." Implies SMART-style scope strings and per-consumer authorization grants.
- **Data sources:** unknown which EHRs/QHINs they aggregate from. They mention "modern digital (FHIR) records" alongside paper-record retrieval via mail. No public TEFCA / Carequality / CommonWell affiliations confirmed.
- **Eugene's prior review:** 7.5/10 — strongest on hands-off authentication and record retrieval (including paper), weakest on UI. Paid subscription required.

## How HBO would fit alongside our existing sources

| Source | Transport to HealthClaw | Auth | Identity verification | Currently wired |
|---|---|---|---|---|
| **HealthEx** | MCP Streamable HTTP pull (`scripts/export_healthex_mcp.py`) | Bearer token (`HEALTHEX_AUTH_TOKEN`) | Done by HealthEx via claude.ai integration | ✅ |
| **Fasten Connect** | Webhook push → `/fasten/webhook` → stream_ingest | Standard-Webhooks HMAC + Stitch widget public key | CLEAR / ID.me via TEFCA mode | ✅ |
| **Health Bank One** | MCP Streamable HTTP pull (planned) | **OAuth 2.x authorization-code grant per consumer** | HBO Digital Identity (IAL2 / AAL2) | ⏳ pending this call |

The **shape that fits cleanest** is a new pull script `scripts/export_healthbankone_mcp.py` modeled on the HealthEx one, plus an OAuth dance to mint the consumer-scoped access token before each pull. The downstream pipe (redact in-process → write to disk → `$ingest-context` → Curatr → Telegram push) is unchanged.

## Architecture sketch — where HBO slots in

```
                 ┌────────────────────────────────────────┐
                 │  HBO OAuth Authorization Endpoint      │
                 │  (consumer grants HealthClaw access)   │
                 └───────────────┬────────────────────────┘
                                 │ authorization_code
                                 ▼
                 ┌────────────────────────────────────────┐
                 │  HBO Token Endpoint                    │
                 │  → access_token + refresh_token        │
                 └───────────────┬────────────────────────┘
                                 │
   ┌─────────────────────────────┴─────────────────────────────┐
   │ scripts/export_healthbankone_mcp.py                       │
   │   MCP Streamable HTTP → https://<hbo>/mcp                 │
   │   Authorization: Bearer <access_token>                    │
   │   Calls: identity.verify, health.summary,                 │
   │          health.medications, health.conditions, …         │
   │   Redacts in-process via scripts/healthclaw_redact.py     │
   └─────────────────────────────┬─────────────────────────────┘
                                 │ redacted FHIR Bundle
                                 ▼
   ┌─────────────────────────────────────────────────────────┐
   │  HealthClaw Flask (app.healthclaw.io)                   │
   │    POST /r6/fhir/Bundle/$ingest-context                 │
   │    → tenant ev-personal-hbo                             │
   │    → Curatr scan if FASTEN_CURATR_SCAN=true             │
   │    → r6.telegram_push.notify_tenant fires               │
   └─────────────────────────────────────────────────────────┘
```

## Top questions to ask on the call (ranked)

### Must answer to start integration

1. **What is the public MCP endpoint URL?** Streamable HTTP `/mcp`? SSE? stdio?
2. **What's the OAuth dance?** Authorization code with PKCE? Device code? Client credentials? Where are the `authorize` and `token` endpoints?
3. **How do we register HealthClaw as a client?** Manual ticket, self-service portal, dynamic client registration (RFC 7591)?
4. **What scopes exist?** SMART-style (`patient/*.read`, `patient/*.write`, `offline_access`) or proprietary? Which scopes gate which tool categories?
5. **What's the exact tool catalog?** Names + input schemas under each of Digital Identity, Health Context, Engagement. Especially: which tool returns a FHIR Bundle vs. a single resource.

### Important for production reliability

6. **What FHIR version + profile?** R4 with US Core? R5? R6?
7. **Rate limits / quotas** during Bootstrap and after?
8. **Refresh token lifetime** + rotation policy? Do they support `offline_access`?
9. **Webhook events** when records change, or pull-only?
10. **Sandbox tenant?** A test consumer with synthetic data so we can wire integration before having a real patient flow through it.

### Strategic / business

11. **Pricing post-Bootstrap.** Are we still free as a developer once docs ship?
12. **Insurance Context separately licensed?** Sometimes payer data is the gate to revenue.
13. **Writebacks (Engagement service)** — what does the consumer authorize, and does the writeback also get audited at HBO?
14. **Identity verification surface** — can HBO Digital Identity replace CLEAR/ID.me in our Fasten flow? Single onboarding for everything?
15. **QHIN affiliations** — eHealth Exchange / Carequality / CommonWell / TEFCA. Does HBO pull through any of these, or is it bilateral with EHRs?

## Comparison points to raise

These come from our HealthEx and Fasten experience and signal we know what we're talking about:

- HealthEx ships a bearer-token MCP server we hit at `https://api.healthex.io/mcp`. The auth is centralized at HealthEx (they own the user-EHR linkage), so HealthClaw just needs the token. The downside is HealthEx owns the per-EHR consent — if HBO is OAuth per-consumer instead, it's *better* for portability but more setup for the developer.
- Fasten Connect uses a webhook + Stitch widget. The patient verifies once via CLEAR/ID.me in TEFCA mode and Fasten streams records to our `/fasten/webhook`. That's a push model. HBO sounds more like a pull model (MCP + OAuth), so we'd write a script that polls / refreshes on demand rather than a webhook receiver. Either pattern works in HealthClaw's tenant-scoped store; the in-process redaction pipeline is the same.
- HealthClaw already speaks **SHARP-on-MCP** + **PromptOpinion FHIR Extension** — when an MCP client (e.g. PromptOpinion, Hermes) forwards `X-FHIR-Server-URL` / `X-FHIR-Access-Token` headers to *us*, we route to that upstream and apply the guardrail stack. HBO could be on the *other* side of that contract too: if HBO advertises SHARP, our MCP server can act as a SHARP-compliant agent host that uses HBO as the upstream, with HealthClaw's PHI redaction + audit + step-up layered on top. Worth confirming whether HBO's MCP is itself SHARP-aware.

## After the call — what we'd build

Order of work assuming we get the MCP URL, OAuth endpoints, scopes, and a client_id / client_secret today:

1. **`scripts/export_healthbankone_mcp.py`** — modeled on `export_healthex_mcp.py`. ~200 lines.
2. **`scripts/healthbankone_oauth.py`** — handles authorization-code grant, refresh token rotation, secure token storage (keychain on Mac mini, Redis on Railway). New file.
3. **`skills/healthbankone-export/SKILL.md`** — companion to the HealthEx and Fasten skills, so OpenClaw can invoke it as `/hbo-pull`.
4. **OpenClaw `/hbo-connect` and `/hbo-pull` commands** — `cmd_hbo_connect` returns the HBO authorization URL with our callback; `cmd_hbo_pull` runs the export.
5. **`r6/healthbankone/` Flask blueprint** if HBO has a webhook for the Engagement service writeback confirmations — mirroring `r6/fasten/` shape. Skip if HBO is pull-only.
6. **CLAUDE.md update** — new "Health Bank One" section under Fasten / HealthEx.
7. **Tests** — `tests/test_healthbankone_oauth.py` + `tests/test_export_healthbankone.py` modeled on the existing pair.

## Skeleton already in repo for the call

`skills/healthbankone/SKILL.md` exists with TODO markers ready to fill in once you have the answers. After the call, edit it in place with the real endpoints, scopes, and tool names.

## One thing to flag during the call

If they want a design partner / case study, HealthClaw is a strong fit: vendor-neutral guardrail layer, open source, already speaks MCP + SHARP + PromptOpinion's extension, deployed on Railway, has a Telegram conversational surface with personas. Worth mentioning briefly — at minimum it earns us faster-than-default Bootstrap onboarding.
