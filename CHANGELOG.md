# Changelog

All notable changes to HealthClaw Guardrails are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project aims to follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.5.0] — 2026-06-18 — Security Hardening + SDC Forms

### Added
- **HL7 SDC form round-trip.** `POST /r6/fhir/Questionnaire[/<id>]/$populate` pre-fills a
  `QuestionnaireResponse` from a subject; `POST /r6/fhir/QuestionnaireResponse/$extract` turns a
  completed response into a transaction `Bundle`.
  - `$populate` mechanisms: expression-based (`initialExpression` FHIRPath via `fhirpathpy`) and
    observation-based (`item.code` LOINC matched against the subject's Observations).
  - `$extract` mechanisms: observation-based (`observationExtract`) and definition-based
    (`definitionExtract` + item `definition` element paths). `?dryRun=true` previews the Bundle
    without committing.
  - Pure, Flask-free transform engines in `r6/sdc/` (`expressions.py`, `populate.py`, `extract.py`);
    the route layer owns auth, audit, step-up, and store I/O.
- **MCP tools** `questionnaire_populate` (read) and `questionnaire_extract` (write) — 23 tools total.
- **Seeded `healthclaw-intake` demo Questionnaire** showing the populate → complete → extract loop.
- **CI compliance gate `H-SDC`** asserting `$extract` requires a step-up token.
- Community scaffolding: `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `CHANGELOG.md`, `LICENSE` (MIT).

### Changed
- **Reads of non-public tenants are now authenticated**, not just tenant-scoped: a bare
  `X-Tenant-Id` only works for `PUBLIC_TENANTS` or SHARP-on-MCP requests; every other tenant must
  present a tenant-bound `X-Step-Up-Token` or a matching SMART bearer, else `401`. The read-auth
  check was refactored into a reusable `authenticate_tenant_read` helper.
- `/metadata` CapabilityStatement now advertises the SMART OAuth service in its `rest.security` block.
- Dependency security bumps: PyJWT (CVE-2026-48526), npm advisories (form-data, minimatch).

### Security / compliance postures (deliberate, documented)
- `$populate` returns **unredacted** PHI by design — a form must hold real data, and the read-auth
  gate is the compensating control. An optional `?redaction=` opt-in is a tracked follow-up.
- `$extract` commit is treated as an ingest-class operation (like `Bundle/$ingest-context`):
  step-up + `$validate` gate the write; it is exempt from the per-resource `X-Human-Confirmed` gate.

## [1.4.0] — 2026-06-11 — Multi-Connector Health Data Pipeline

### Added
- Five distinct health-data pipelines wired in behind the guardrail stack, surfaced as Telegram
  slash commands: **Fasten TEFCA** (`/connect`), **HealthEx** (`/export`), **Health Bank One**
  (`/hbo-connect`, `/hbo-pull`), **Flexpa** (`/flexpa-connect`), **Health Skillz / Epic**
  (`/epic-connect`), and **MEDENT** (`/medent-connect`, `/medent-pull`).
- `/shc/ingest` SmartHealthConnect bridge endpoint; `/shc/medent/callback` OAuth broker.
- `scripts/medent_oauth.py` (SMART on FHIR DCR + PKCE) and `scripts/export_medent_fhir.py`.

## [1.3.0] — 2026-04-15 — Wearables

### Added
- Wearable device sync (Garmin, Oura, Polar, Suunto, Whoop, Fitbit, Strava, Ultrahuman) into FHIR
  Observations with LOINC/UCUM codes and device Provenance, via the Open Wearables sidecar.
- `r6/wearables/mapper.py`, a daemon poller through `/Bundle/$ingest-context`, the
  `wearables_sync_status` MCP tool, and a Connection Manager MCP App.

## [1.2.0] — 2026-04-15 — Compiled Truth

### Added
- `GET /<type>/<id>/$compiled-truth` and the `fhir_compiled_truth` MCP tool — current redacted
  resource + curation state + quality score + full Provenance timeline.
- Activated `curation_state` and `quality_score` on every resource; `.health-context.yaml`.

## [1.0.0] — 2026-03-28 — Curatr Data Quality Skills

### Added
- Curatr patient-owned data-quality engine: terminology checks against live APIs, patient-approved
  fixes with Provenance tracking, and the `curatr_evaluate` / `curatr_apply_fix` MCP tools.

[1.5.0]: https://github.com/aks129/HealthClawGuardrails/releases/tag/v1.5.0
[1.4.0]: https://github.com/aks129/HealthClawGuardrails/releases/tag/v1.4.0
[1.3.0]: https://github.com/aks129/HealthClawGuardrails/releases/tag/v1.3.0
[1.2.0]: https://github.com/aks129/HealthClawGuardrails/releases/tag/v1.2.0
[1.0.0]: https://github.com/aks129/HealthClawGuardrails/releases/tag/v1.0.0
