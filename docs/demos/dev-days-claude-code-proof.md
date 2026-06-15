# Dev Days — Claude Code as the "Proof Terminal" + driven demo flow

The move: **Telegram shows the patient experience; Claude Code shows the proof.**
While Sally runs the flow in Telegram, a second screen — your Claude Code session —
streams the live guardrail telemetry: every FHIR read, redaction, step-up write,
and real-world action landing in the immutable audit trail in real time. That is
the dev-cred shot — the agent isn't a black box, every move is audited and visible.

---

## How to run the telemetry in Claude Code

`scripts/demo_telemetry.py` tails the audit trail + record inventory for a tenant.
It shells out to `curl` (system CA store) so it works on any machine regardless of
the local Python SSL config. Reads use the tenant header only — nothing it does can
mutate data; you're watching the same redacted, audited surface an agent sees.

**Option A — stream it INTO Claude Code (recommended).** In your stage Claude Code
session, ask Claude to run it via the **Monitor** tool so each audit event arrives
as a live line in the conversation:

> "Monitor the demo telemetry: `python3 scripts/demo_telemetry.py --tenant ev-personal`
>  — emit each audit line, keep running until I stop it."

Claude starts the watcher as a persistent monitor; as Sally acts in Telegram, the
events stream into the session. This is the most "live coding" presentation — the
audit trail scrolling in the same tool you built the system with.

**Option B — a terminal split.** Just run it directly next to Claude Code:

```bash
python3 scripts/demo_telemetry.py --tenant ev-personal
# desktop-demo (synthetic) needs no token; ev-personal works with the tenant header for reads
```

What a line looks like:
```
  14:02:11  👁  read      Condition/abc123        sally-pcp              ✅
  14:02:14  ✏️  create    ProposedAction/9f..     sally-pcp              ✅      ← phone call proposed
  14:02:20  ✎  update     ProposedAction/9f..     sally-pcp              ✅      ← step-up + human confirm → executing
  📊 ev-personal: 315 resources  |  Observation:140  Condition:57  ...
```

Pre-flight: print one snapshot to prove it's wired before you walk on:
```bash
python3 scripts/demo_telemetry.py --tenant ev-personal --snapshot-every 1 --interval 3   # Ctrl-C after the first line
```

---

## The driven flow (Telegram, narrated by the Claude Code feed)

Run these as natural prompts to Sally. Each step produces audit telemetry that
appears in the Claude Code proof terminal.

### 1. Connect — walk every source
> "Connect my health data. Go through each source."

Sally offers the connect links (Fasten TEFCA, Health Bank One, MEDENT, Flexpa,
Epic/Health Skillz) and confirms what's already connected. Then:

> "Now check all my connected services for data."

Sally calls `fhir_get_token` → `sources_check` (one call) → "Connected N/7; 315 records
(57 Conditions, 140 Observations, …)." **Telemetry:** the `sources_check` read +
per-source reads stream in Claude Code.

### 2. Review & report using the skills
> "Review my record and tell me what stands out."

Sally uses the FHIR read tools + Curatr (`curatr_evaluate`) + clinical-context skills
to summarize conditions/meds/trends and flag data-quality issues — administrative
framing, no diagnosis. **Telemetry:** a burst of `read` + `validate` events.

### 3. Phone call — dial the (simulated) doctor's office
> "Call the doctor's office to follow up. Here's the number: <YOUR PHONE>."

(You play the doctor's office — give your own number.) Sally drafts the call script,
shows it, you confirm; she runs `action_propose` → `fhir_get_token` →
`action_commit` (step-up + human-confirm). **Telemetry:** `ProposedAction` create
then update — the propose→confirm→execute lifecycle, audited. Your phone rings.

> ⚠️ **A real dial requires `BLAND_AI_API_KEY` on the Flask service.** Without it the
> action completes in **simulation mode** (full propose→commit→audit telemetry, but
> no actual call). To ring your phone on stage, set it the morning of:
> `railway variables --service HealthClawGuardrails --set BLAND_AI_API_KEY=<key>`
> (`ACTIONS_WEBHOOK_SECRET` is already set, so callbacks/outcome will record too.)

### 4. Fill the 40-page intake form
> "The new clinic needs this intake form filled out: <FORM URL>."

(Supply any dummy patient-intake page/PDF.) Sally fetches the form, pulls your
demographics, insurance, medications, and allergies from FHIR (via the MCP tools),
fills the fields, and returns the completed form for your review. **Telemetry:** the
FHIR reads that populate the form stream in Claude Code — visible proof the answers
came from your actual record, not invented.

> Note: form-fill here is **agent-driven** (Sally fetches + maps + fills). A
> first-class `form-fill` *action* (audited propose/commit + AcroForm PDF output)
> is the planned executor — not required for this demo; the FHIR-read telemetry is
> the proof either way.

---

## One-glance stage layout

| Screen | Shows | Source |
|---|---|---|
| Telegram | Sally + the patient (you) | phone / web.telegram.org |
| Claude Code | live audit telemetry feed | `demo_telemetry.py` via Monitor |
| Browser tab A | Command Center (live stats) | signed link (`generate-link`) |
| Browser tab B | FHIR Control Panel | `/fhir-control-panel?tenant=ev-personal` |

The story: *patient talks to Sally (Telegram) → every guarded move proves out in the
audit feed (Claude Code) → the same data and conformance are inspectable (Control
Panel) and the whole system's health is live (Command Center).*

## The one thing to set for a real phone call
`BLAND_AI_API_KEY` on the `HealthClawGuardrails` Flask service. Everything else
(MCP tools, step-up, audit, signed link, control panel) is already live.
