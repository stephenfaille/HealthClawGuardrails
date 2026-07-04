# Consumer directory submission package — Claude Connectors + ChatGPT Apps

Everything copy-paste ready for the two consumer directories. The account-level
gates are human-only (see the checklist at the bottom); all technical
prerequisites are DONE (tool titles + annotations shipped v1.6.x, remote MCP
live, OAuth 2.1 + SMART, public demo tenant).

---

## Listing copy (shared)

**Name:** HealthClaw Guardrails
**Tagline (≤80 chars):** Safe AI access to your health records — redacted, audited, human-approved.
**Short description:**
> Connect AI to FHIR health records through an open-source guardrail layer.
> Every read is PHI-redacted and audit-logged; every write needs step-up
> authorization and explicit human confirmation. Interpret labs, check quality
> measures, fill intake forms, and share records via encrypted SMART Health
> Links — with decision-support framing, never diagnosis.

**Category:** Health & Fitness / Productivity
**Website:** https://healthclaw.io · **Privacy:** https://healthclaw.io/privacy
**Support contact:** eugene.vestel@gmail.com (until a support@ alias exists — see checklist)

## Claude Connectors Directory — stage-by-stage answers

1. **Connection check:** `https://mcp-server-production-5112.up.railway.app/mcp` (Streamable HTTP, HTTPS).
2. **Tool sync:** 24 tools; ALL carry `title`, `readOnlyHint`, `destructiveHint`, `openWorldHint` (enforced by jest test).
3. **Listing copy:** above.
4. **Use cases (3):**
   - "Explain my latest lab results in plain language" → `fhir_interpret_labs` (flags + consumer summary + disclaimer)
   - "Fill out my intake form from my records" → `questionnaire_populate` (SDC)
   - "Is my blood pressure controlled?" → `fhir_lastn` + quality measure context
5. **Company info:** HealthClaw (healthclaw.io), open-source project, MIT; maintainer Eugene Vestel.
6. **Auth:** OAuth 2.1 + PKCE (SMART-on-FHIR profile) at `/r6/fhir/oauth/*`; discovery at `/.well-known/oauth-authorization-server`. Public demo tenant works header-only for evaluation.
7. **Data handling (answer honestly, this is our strength):**
   - Health data: **YES** (FHIR clinical records). PHI is redacted on every read (Safe-Harbor-style + patient-controlled profiles); full identifiers never reach the model by default.
   - Storage: tenant-isolated FHIR store (or pass-through proxy to the user's own FHIR server — we store nothing in SHARP mode). Immutable audit trail of every access.
   - No selling, no ads, no training on user data. Writes are proposals until a human confirms (HTTP 428 otherwise).
8. **Test credentials:** tenant `desktop-demo` (public synthetic data — Maria Rivera demo patient with conditions/labs/meds/BP). No password needed; header `X-Tenant-Id: desktop-demo`. Reviewer walkthrough: call `fhir_search` → see redaction; call `fhir_interpret_labs` on the seeded A1c → see flag + consumer summary + disclaimer; attempt `fhir_commit_write` without confirmation → observe the 428 human-in-the-loop refusal.
9. **Compliance acknowledgments:** decision-support positioning (never diagnosis/treatment); medical disclaimers injected on all clinical reads; human-in-the-loop for all writes and real-world actions.
10. **Domain proof:** healthclaw.io DNS (Vercel-managed).
11. **Escalation if stuck:** mcp-review@anthropic.com.

## ChatGPT Apps Directory — deltas from the above

- Same MCP server; add the ChatGPT-connector `search`/`fetch` tool pair
  (NOTE: we already built this pattern for Medplum #9616 — port it to our own
  server as a small follow-up so the app works with ChatGPT's built-in
  retrieval UX).
- Manifest + optional inline UI component via Apps SDK.
- Framing for health review: "information access + decision support with
  disclaimers; no tailored medical advice; no diagnosis/treatment claims" —
  our disclaimer layer already emits exactly this on every clinical response.
- Age gating: content suitable 13–17 (synthetic demo data is fine; real-tenant
  onboarding language should say 18+).

## Privacy-policy additions needed (Eugene approves before publishing — legal page)

Current /privacy covers third parties, HIPAA posture, children, retention,
no-selling. Two reviewer-checklist gaps to add:

**Draft §"What we collect" (data categories):**
> When you connect a health data source, we process: identity and demographic
> data (name, birth date, contact details), clinical data (conditions,
> medications, lab results, vital signs, immunizations, documents), coverage
> data, and device/wearable observations. Operational data: tenant identifiers,
> access logs (who/what/when — never clinical values), and OAuth tokens.

**Draft §"Your rights and controls":**
> You can disconnect any data source at any time; export your data as standard
> FHIR; request deletion of your tenant and all stored records (support
> contact below — deletion completes within 30 days and is confirmed to you);
> and review the audit trail of every access to your records. We never sell
> your data or use it to train AI models.

---

## HUMAN-ONLY checklist (not doable via CLI/API/agent)

| # | Action | Where | Why / notes |
| --- | --- | --- | --- |
| 1 | **Buy Claude Team plan** (or Enterprise) | claude.ai → upgrade | The connector-directory submission portal only exists in Team/Enterprise admin settings. ~$25-30/seat/mo, 1 seat suffices |
| 2 | **Walk the connector submission portal** | claude.ai admin → connectors | Paste the stage answers above; I can't click through a logged-in claude.ai session |
| 3 | **OpenAI verified developer account** | platform.openai.com → settings → verification | Identity/org verification (government ID or org docs) gates ChatGPT app submission |
| 4 | **Approve + publish the privacy additions** | this doc → templates/privacy.html | It's a legal page — your sign-off, then I ship it |
| 5 | **Create support@healthclaw.io** (or alias) | your email/domain provider | Both directories want a support contact that isn't a personal gmail |
| 6 | **Post LinkedIn Draft A** | linkedin.com | docs/articles/2026-07-v1.6.0-announcement-plan.md — only you can post as you |
| 7 | **Substack piece** | substack | Outline ready; say the word and I write the full draft for your edit |
| 8 | **Send Dr. Magan the range-table review ask** | email/text | LOINC_RANGES clinical sign-off — the "credible" principle's last mile; personal relationship |
| 9 | **HL7 Jira account** (+ chat.fhir.org Zulip) | jira.hl7.org | SDC implementer feedback → IG credits; account creation is human (CAPTCHA/approval) |
| 10 | **Join Medplum Discord** | discord.gg (link on medplum.com) | Their community lives there; a hello + "we opened #9746/#9616" from a human converts PRs into relationships |
| 11 | **Bo Holland / HBO + Fasten founder nudges** | email/DM | When PRs/comments get responses, a personal note lands the partnership conversation |

Everything else — code, listings prep, PR watching/responding, registry
publishing, deploys — stays on the agent side.
