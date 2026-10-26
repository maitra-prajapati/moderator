# MODERATOR — MASTER BUILD BLUEPRINT

**Team:** PINEAPPLE  
**Members:** Maitra Prajapati (backend, governance, integration) · Vismay Godhani (frontend, workflows, experience)  
**Project:** Moderator — *Verify before you publish*  
**Status:** Round 1 qualified; this is the Round 2 implementation plan and Round 3 hardening roadmap.  
**Version:** 1.0 · **Source of scope:** `Problem_statement.pdf` and the submitted `Moderator_Round1_Pineapple_Clean.pdf`.

> **How to use this one file:** The Main Brain owns the architecture, freezes shared contracts, and updates checkboxes. A worker takes one *subdivision* at a time, follows its numbered **build order**, and returns its outputs and tests. Do not mark a task finished because code was generated; mark it finished only after its acceptance check passes. `- [ ]` = pending; `- [x]` = completed. No implementation is assumed complete at the time this blueprint is written.

---

## A. Non-negotiable decisions and independence rule

### A.1 Product scope (frozen until MVP acceptance)
- **One fictional brand:** FlowPilot Demo, a fictional project-management SaaS company.
- **Text only:** English promotional copy entered/pasted in the browser; channels can include LinkedIn, website and email text.
- **Users:** creator, reviewer, administrator. The *team* has two developers; the demo may use seeded fictional user accounts for the roles.
- **Core value:** check terminology, prohibited wording and structured product claims against approved, versioned sources; explain, suggest, review, log.
- **No paid API dependency.** Deterministic checking must work with AI disabled. Optional Ollama suggestions are strictly non-authoritative.
- **Not in MVP:** OCR, PDFs as review inputs, image/logo analysis, scraping, external fact verification, auto-publishing, third-party SSO, multi-tenancy, model training.
- **Three Round 2 improvements promised in Round 1:** (I) Evidence-linked Claim Passport; (II) Context-preserving corrections; (III) Traceable human approval with revisions, overrides and recurring issue counts.

### A.2 Independent major modules — hard boundary
1. Each **major module M1–M6** owns its own code, tests and storage/tables (where applicable).
2. **No direct import of Python functions/classes, React components, SQLAlchemy models, or database sessions from any other major module.** No cross-module SQL joins or table writes.
3. Information exchange happens **only via versioned JSON request/response contracts** defined in Section B. HTTP endpoints are the outward contract; local adapters may fulfill them when assembled by M7.
4. **M7 Integration is the only composition root** permitted to import module entrypoints, wire adapters, implement API gateway calls, perform cross-module transaction/consistency checks, and run end-to-end tests.
5. A module can be implemented and tested **without another module running**, using recorded fixture JSON and mocks. Do not create a second copy of another module's logic.
6. For the two-person MVP, **one FastAPI deployment with separately owned packages** is preferable to multiple production microservices. Independence is an internal design discipline, not a requirement to run six servers.
7. Shared runtime libraries are permitted (FastAPI, Pydantic, SQLite, React, testing libraries), but **no shared custom business-logic package**. Shared JSON schemas live in the *documentation/contracts*, not as imports between feature modules.

**Diagram — permitted dependencies only:**

```text
                              +----------------------+
                              | M5 WEB UI            |
                              | HTTP + mock fixtures |
                              +-----------+----------+
                                          |
                              versioned /api/v1 JSON
                                          v
                              +----------------------+
                              | M7 INTEGRATION       |
                              | auth/gateway/wiring  |
                              +---+---+---+---+-----+
                                  |   |   |   |    |
                            JSON  |   |   |   |    |  JSON
                                  v   v   v   v    v
                                 M1  M2  M3  M4   M6
                              Knowledge Identity Workflow Engine Analytics
                                  ^           |       ^
                                  +-----------+-------+
                             information flows ONLY via M7
```

> **Important limitation:** All modules cannot be independent *at runtime* in an integrated product. The requirement here means **no code-level coupling across major modules**; runtime information dependencies are explicitly handled by M7 with stable contracts.

### A.3 Final repository layout (ownership is by directory)

```text
moderator/
├── README.md
├── MODERATOR_MASTER_BUILD_BLUEPRINT.md        # this one-file source of plan and gates
├── docs/
│   └── contracts/                              # frozen JSON schemas/examples; docs only
├── backend/
│   ├── modules/
│   │   ├── knowledge/                          # M1 OWNED CODE + tests + own tables
│   │   ├── identity/                           # M2 OWNED CODE + tests + own tables
│   │   ├── workflow/                           # M3 OWNED CODE + tests + own tables
│   │   ├── analysis/                           # M4 OWNED CODE; stateless
│   │   └── insights/                           # M6 OWNED CODE; stateless/read-only
│   ├── integration/                            # M7 composition root, adapter wiring, routes
│   ├── tests/e2e/                              # M7 black-box integration tests
│   ├── requirements.txt
│   └── app.py                                  # M7 bootstraps the app
├── frontend/                                   # M5 OWNED CODE
│   ├── src/
│   ├── tests/
│   └── package.json
└── demo/
    └── fixtures/                              # synthetic demo input datasets and expected outputs
```

**Suggested module-local storage:** `knowledge.sqlite`, `identity.sqlite`, `workflow.sqlite` (or distinct owned tables in one SQLite database if the owner maintains strict isolation). Do not optimize distribution before integration works.

---

## B. Freeze data contracts before parallel coding

**B is not a feature module.** It defines interoperable information and identifiers so independent modules cannot disagree. All example data is fictional.

### B.1 Contract-wide rules
- [ ] **B.1.1** Freeze public API base prefix `/api/v1`; internal engine/analytics interfaces are distinct from public endpoints.
- [ ] **B.1.2** Freeze IDs as opaque strings (e.g., `brand_flowpilot`, `src_001`, `claim_trial`, `sub_001`, `rev_001`). All timestamps use ISO-8601 UTC.
- [ ] **B.1.3** Freeze enums: role = `creator|reviewer|admin`; severity = `info|warning|blocker`; evidence status = `supported|contradicted|needs_verification|not_applicable`.
- [ ] **B.1.4** Freeze workflow states = `DRAFT|ANALYZING|ANALYSIS_FAILED|REVIEW_REQUIRED|CHANGES_REQUESTED|APPROVED|REJECTED`.
- [ ] **B.1.5** Standardize API failures: HTTP status, `error.code`, `error.message`, optional `error.details`; no HTML stack traces.
- [ ] **B.1.6** Standardize content offsets as Python **Unicode code-point** start/end for backend contracts; M5 must map correctly to JavaScript text highlighting (UTF-16) or display quote-based fallback. Never silently highlight the wrong span.
- [ ] **B.1.7** Agree content channels (`linkedin|website|email`), title ≤ 200 chars, text 1–10,000 chars and exact accepted encodings.
- [ ] **B.1.8** Store and publish contract changes through a versioned change request; no unilateral breaking change.

### B.2 Brand Knowledge Snapshot — M1 output to M4 via M7

```json
{
  "brand_id": "brand_flowpilot",
  "knowledge_version_id": "kv_001",
  "version_no": 1,
  "activated_at": "2026-10-25T00:00:00Z",
  "voice_traits": ["friendly", "professional", "precise"],
  "sources": [
    {"id": "src_trial", "title": "Demo Trial Policy", "excerpt": "FlowPilot offers a 14-day free trial.", "valid_until": null},
    {"id": "src_names", "title": "Demo Brand Guide", "excerpt": "Official product spelling: FlowPilot.", "valid_until": null}
  ],
  "rules": [
    {"id": "rule_name", "type": "terminology", "pattern": "Flow Pilot", "replacement": "FlowPilot", "severity": "warning", "source_id": "src_names"},
    {"id": "rule_guarantee", "type": "restricted_phrase", "pattern": "100% guaranteed", "replacement": null, "severity": "blocker", "source_id": null}
  ],
  "claims": [
    {"id": "claim_trial", "fact_key": "free_trial_days", "value": 14, "unit": "days", "approved_text": "14-day free trial", "source_id": "src_trial"}
  ]
}
```

**Invariant:** Activated knowledge version cannot be overwritten. A source ID must resolve to a source in that version before being called “verified.” A policy rule may itself be valid without a factual source, but the system must not fabricate a citation for it.

### B.3 Analysis Request — M7 input to M4

```json
{
  "request_id": "req_001",
  "submission_id": "sub_001",
  "revision_id": "rev_001",
  "channel": "linkedin",
  "text": "Flow Pilot offers a 30-day free trial. Security is 100% guaranteed!",
  "knowledge": {"$ref": "B.2 complete snapshot"},
  "ai_enabled": false
}
```

**Invariant:** `knowledge` is the immutable snapshot, **not a database connection**. M4 must not query M1 tables or accept executable instructions embedded in the submitted text.

### B.4 Analysis Finding — M4 output to M3 via M7

```json
{
  "finding_id": "find_001",
  "category": "claim_mismatch",
  "severity": "blocker",
  "evidence_status": "contradicted",
  "span": {"start": 20, "end": 37, "quote": "30-day free trial"},
  "rule_id": null,
  "claim_id": "claim_trial",
  "source_id": "src_trial",
  "knowledge_version_id": "kv_001",
  "explanation": "The approved trial is 14 days, not 30 days.",
  "suggested_replacement": "14-day free trial",
  "confidence_kind": "deterministic"
}
```

**Invariant:** Span offsets and quote must match the input exactly. Missing evidence => `needs_verification`, not an invented contradiction. Suggested replacement must never silently overwrite user text.

### B.5 Workflow Submission — M3 output to M5/M6 via M7

```json
{
  "submission_id": "sub_001",
  "brand_id": "brand_flowpilot",
  "author_id": "user_creator",
  "title": "Launch copy",
  "channel": "linkedin",
  "state": "REVIEW_REQUIRED",
  "current_revision_id": "rev_001",
  "revision_no": 1,
  "knowledge_version_id": "kv_001",
  "finding_counts": {"blocker": 1, "warning": 1, "info": 0},
  "updated_at": "2026-10-25T00:00:00Z"
}
```

### B.6 Minimal API contract ownership (M7 exposes, modules implement functionality)

| API / information boundary | Owner | Required data |
|---|---|---|
| `POST /auth/login`, `GET /auth/me` | M2 | role-bearing authenticated identity |
| `GET /brands/{id}/knowledge` | M1 | latest activated snapshot |
| `POST /brands/{id}/knowledge` | M1 | draft version creation (admin only at M7) |
| `POST /brands/{id}/knowledge/{version}/activate` | M1 | validation + immutable activation |
| `POST /submissions`, `GET /submissions`, `GET /submissions/{id}` | M3 | draft create/list/detail |
| `POST /submissions/{id}/submit` | M3 + M7 | freeze revision, run analysis, persist findings |
| `GET /submissions/{id}/findings` | M3 | exact revision and findings |
| `POST /submissions/{id}/revisions` | M3 | new editable revision |
| `POST /submissions/{id}/reviews` | M3 + M7 | approve / reject / request changes / override |
| `GET /submissions/{id}/history` | M3 | decisions + revision audit |
| `GET /analytics/summary` | M6 | counts derived only from authorised public read models |
| Internal `analyse(text, snapshot)` JSON contract | M4 | zero database/API imports from M1/M3 |

### B.7 Cross-module event contract (optional but useful for logs/analytics)

```json
{
  "event_id": "evt_001",
  "event_type": "review.approved",
  "occurred_at": "2026-10-25T00:00:00Z",
  "actor_id": "user_reviewer",
  "submission_id": "sub_001",
  "revision_id": "rev_001",
  "knowledge_version_id": "kv_001",
  "metadata": {"override": false}
}
```

**B completion gate:** all contracts above are agreed and checked into Git **before** M1–M6 begin their implementation; one owner approves each schema and both members sign off on the frozen endpoints.

---

## C. Build sequencing at a glance

**Order dependencies are information/contract dependencies, NOT code imports.** “Ready” means other modules can start using a fixture or mock; not that all connected features are implemented.

| Gate | Prerequisite | Work that can run in parallel | Integration demonstration / exit check |
|---|---|---|---|
| G0 — Scope & contracts | Round 1 documents read | B, seeded demo truth set, Git conventions | Both members approve B; examples validate |
| G1 — Isolated shells | G0 | M1, M2, M3, M4, M5, M6 scaffolds | Every module passes its **own** smoke test without others |
| G2 — First useful check | M1 snapshot fixture + M4 | M5 mocked editor, M3 draft creation | Engine detects terminology and 30/14-day mismatch offline |
| G3 — Core loop | M1–M5 contracts implemented | M6 analytics fixture tests | Create → submit → analyse → findings visible |
| G4 — Human control | G3 + M2 identity + M3 review | M5 reviewer UI | Creator denied approval; reviewer approves exact revision |
| G5 — Promised improvements | G4 | M4 corrections, M3 audits, M6 counts | Claim Passport + corrections + traceable approval work end-to-end |
| G6 — MVP acceptance | G5 | M7 E2E, negative tests, docs | Full demo from clean local setup; no paid model needed |
| G7 — Round 2 evidence | G6 | repo/documentation/demo proof | Judge-accessible repo, real test logs, contribution record |
| G8 — Round 3 hardening | Round 2 feedback | accessibility, error handling, reliability | polished demo, evidence, future roadmap, known limits |

**Critical path:** B → M1 sample knowledge + M4 rule checker → M3 persistence/orchestration → M5 findings view → M2 permissions + M3 reviewer actions → M7 E2E.

---

## M1. BRAND KNOWLEDGE & FACTS — isolated ownership

**Owner:** Maitra  
**Owned code:** `backend/modules/knowledge/`  
**Owned data:** `brands`, `knowledge_versions`, `sources`, `brand_rules`, `approved_claims`  
**Consumes:** admin identity/permission decision **supplied by M7**; no direct M2 imports  
**Publishes:** immutable Brand Knowledge Snapshot (B.2) and knowledge endpoints (B.6)

### M1.1 Synthetic evidence foundation
- [ ] **M1.1.1 — Build first:** Create the fictional FlowPilot Demo brand profile (industry, audience, voice, approved product spelling).
- [ ] **M1.1.2 — After 1.1.1:** Draft ≥ 2 explicitly fictional approved source records (trial policy; brand/name guide) with excerpt and optional expiry.
- [ ] **M1.1.3 — After 1.1.2:** Draft controlled terminology and restricted-phrase rules, including severity, match behavior and replacement.
- [ ] **M1.1.4 — After 1.1.3:** Draft structured factual claims such as `free_trial_days = 14`, linking them to valid sources.
- [ ] **M1.1.5 — Check:** No real organisation is implied; each claim has a valid source; conflicting duplicates are rejected.

### M1.2 Own storage and validations
- [ ] **M1.2.1 — Build first:** Define M1-only ORM models/tables and migration/bootstrap logic; never reference another module's ORM models.
- [ ] **M1.2.2 — After 1.2.1:** Implement draft knowledge creation, version increment, source/rule/claim validation.
- [ ] **M1.2.3 — After 1.2.2:** Implement immutable `activate(version)` operation and `get_active_snapshot(brand_id)`.
- [ ] **M1.2.4 — After 1.2.3:** Implement source validity handling (expired sources cannot substantiate new factual claims).
- [ ] **M1.2.5 — Check:** Changing an activated version is rejected; a new version is permitted; snapshot contains exactly the approved records.

### M1.3 Public interface and tests
- [ ] **M1.3.1 — Build first:** Expose module factory and M1 routes/adapters without importing M2–M6.
- [ ] **M1.3.2 — After 1.3.1:** Implement `GET /brands/{id}/knowledge`, `POST /brands/{id}/knowledge`, activation endpoint contract.
- [ ] **M1.3.3 — After 1.3.2:** Seed deterministic fixture and emit a B.2-compliant snapshot.
- [ ] **M1.3.4 — Check:** Tests pass for missing source, expired source, unknown brand, read-only activated version, and version bump.

**M1 handoff packet:** snapshot JSON, endpoints, seed command, passing tests, known constraints. **Independent done:** all M1 tests run without M3, M4 or frontend installed.

---

## M2. IDENTITY & ACCESS — isolated ownership

**Owner:** Maitra  
**Owned code:** `backend/modules/identity/`  
**Owned data:** `users` (and optional sessions)  
**Consumes:** credentials and login JSON only  
**Publishes:** authenticated `{user_id, role}`; the M7 gateway applies the resulting access policy

### M2.1 Identity model
- [ ] **M2.1.1 — Build first:** Define roles `creator`, `reviewer`, `admin`; write a permission table for every protected action.
- [ ] **M2.1.2 — After 2.1.1:** Seed three separate fictional demo identities with safe non-production credentials; NEVER commit live passwords or secrets.
- [ ] **M2.1.3 — After 2.1.2:** Implement password hashing and a simple signed session/token; store signing secret outside git.
- [ ] **M2.1.4 — Check:** Invalid credentials are rejected; no plaintext password stored; identity carries canonical role.

### M2.2 Authorization rules as an interface
- [ ] **M2.2.1 — Build first:** Define policy function from JSON `actor`, `action`, `resource` → `allow|deny` and reason.
- [ ] **M2.2.2 — After 2.2.1:** Implement creator own-draft editing; reviewer reviewing other people; administrator brand knowledge activation.
- [ ] **M2.2.3 — After 2.2.2:** Explicitly deny creator approving their **own** submission, including a reviewer account acting on its own authored submission.
- [ ] **M2.2.4 — Check:** Every privileged operation requires a server-side permission decision; UI state is never sufficient.

### M2.3 Public interface and tests
- [ ] **M2.3.1 — Build first:** Implement `POST /auth/login` and `GET /auth/me` response schemas.
- [ ] **M2.3.2 — After 2.3.1:** Implement expiry, invalid signature, missing token and unauthorised response cases.
- [ ] **M2.3.3 — Check:** Test matrices for creator/reviewer/admin roles; permission bypass attempts return 403; unauthenticated requests return 401.

**M2 handoff packet:** login contract, demo accounts procedure, permission matrix, failure responses, tests. **Independent done:** permission and authentication tests run without M1/M3 database imports.

---

## M3. CONTENT, REVISION & REVIEW WORKFLOW — isolated ownership

**Owner:** Maitra (logic) with Vismay consulted on states and messages  
**Owned code:** `backend/modules/workflow/`  
**Owned data:** `submissions`, `revisions`, `findings`, `reviews`, `audit_events`  
**Consumes via M7:** actor identity, active knowledge version ID, B.4 findings JSON  
**Publishes:** B.5 submission, findings, review decisions, history, optional B.7 audit events

### M3.1 Submission and revision lifecycle
- [ ] **M3.1.1 — Build first:** Create models for submission, immutable saved revision, and submitted text validation.
- [ ] **M3.1.2 — After 3.1.1:** Support create `DRAFT`, list and detail; bind author and brand as strings, not cross-module database relationships.
- [ ] **M3.1.3 — After 3.1.2:** Implement state transition table exactly as B.1.4; all illegal transitions fail with a clear error.
- [ ] **M3.1.4 — After 3.1.3:** On submit, freeze a specific text revision and the supplied knowledge version ID; set `ANALYZING`.
- [ ] **M3.1.5 — After 3.1.4:** Accept analysis findings B.4 from M7 and atomically persist them before entering `REVIEW_REQUIRED`; handle `ANALYSIS_FAILED` and retry without losing prior audit.
- [ ] **M3.1.6 — Check:** No submission can be approved without recorded findings/analysis state; errors never leave phantom approvals.

### M3.2 Finding management and revision policy
- [ ] **M3.2.1 — Build first:** Persist finding quote, offsets, severity, evidence status, claim/rule/source IDs, revision and knowledge version.
- [ ] **M3.2.2 — After 3.2.1:** Store user action on findings (acknowledge, accept suggested wording manually, dismiss with reason).
- [ ] **M3.2.3 — After 3.2.2:** Save a new revision for edits; invalidate any approval for the new revision (do NOT alter prior revision's approved state/history).
- [ ] **M3.2.4 — Check:** Analysis results and reviewer decisions remain attached to the correct revision, including after brand policy updates.

### M3.3 Reviewer decisions and audit
- [ ] **M3.3.1 — Build first:** Support decision types `approve`, `request_changes`, `reject`; require comments for reasons where appropriate.
- [ ] **M3.3.2 — After 3.3.1:** Deny creator self-approval using the actor authorization result supplied by M7.
- [ ] **M3.3.3 — After 3.3.2:** Block approval of open blocker findings unless **authorized override with explicit reason** is supplied and recorded.
- [ ] **M3.3.4 — After 3.3.3:** Append audit events for draft/revision/analyse/decision/override with actor, timestamp, exact revision.
- [ ] **M3.3.5 — Check:** Unauthorized action = 403; valid reviewer decision = revision-specific immutable audit entry; history shows all transitions.

### M3.4 Public interface and tests
- [ ] **M3.4.1 — Build first:** Implement B.6 submissions/revisions/findings/review/history endpoints using fixture identities and fixture findings.
- [ ] **M3.4.2 — After 3.4.1:** Unit test all state transitions and idempotent retries (repeat submit or review must not duplicate critical records).
- [ ] **M3.4.3 — Check:** Runs using JSON fixture findings with M4 entirely absent. No imports of `knowledge`, `identity`, or `analysis` code.

**M3 handoff packet:** transition diagram, endpoints, audit sample, test results, idempotency and override rules. **Independent done:** workflow tests pass with mocked identities/analysis JSON.

---

## M4. ANALYSIS ENGINE & CLAIM PASSPORT — isolated ownership

**Owner:** Maitra  
**Owned code:** `backend/modules/analysis/`  
**Storage:** none for MVP (pure input JSON → output JSON; no database access)  
**Consumes:** B.3 complete request, including snapshot  
**Publishes:** array of B.4 findings and engine status

### M4.1 Deterministic analysis kernel — required before AI
- [ ] **M4.1.1 — Build first:** Define `analyse(request_json) -> result_json` and validate B.3 with Pydantic or equivalent local schema.
- [ ] **M4.1.2 — After 4.1.1:** Implement exact/regex terminology detection with safe escaping, predictable case behavior and correct offsets.
- [ ] **M4.1.3 — After 4.1.2:** Implement restricted phrases (e.g., `100% guaranteed`) separately from provably false factual claims.
- [ ] **M4.1.4 — After 4.1.3:** Implement structured trial duration comparison for recognized patterns (`14-day`, `30 day`, `30-day`); map mismatches to approved `free_trial_days`.
- [ ] **M4.1.5 — After 4.1.4:** Implement evidence-status logic: approved match = `supported`, recognized contradiction = `contradicted`, unapproved/expired/ambiguous = `needs_verification`.
- [ ] **M4.1.6 — After 4.1.5:** Return stable category, severity, matching quote/offset, IDs, explanation, narrow suggested change; deduplicate overlapping identical findings.
- [ ] **M4.1.7 — Check:** T01–T08 (Section E) pass offline; AI process never needed.

### M4.2 Explainable Claim Passport — promised improvement I
- [ ] **M4.2.1 — Build first:** Attach claim/rule/source/version IDs to every applicable fact finding.
- [ ] **M4.2.2 — After 4.2.1:** Validate evidence belongs to the supplied immutable knowledge version and is not expired.
- [ ] **M4.2.3 — After 4.2.2:** For unsupported absolute claims, return `needs_verification` and an explanation rather than invented evidence.
- [ ] **M4.2.4 — Check:** Every factual “supported/contradicted” verdict resolves to approved non-expired evidence; unsupported claims do not get fake citations.

### M4.3 Context-preserving corrections — promised improvement II
- [ ] **M4.3.1 — Build first:** Implement narrow replacements for unambiguous rule/fact mismatches (replace phrase, not full paragraph).
- [ ] **M4.3.2 — After 4.3.1:** Refuse to automatically rewrite unknown claims into invented product facts.
- [ ] **M4.3.3 — After 4.3.2:** Preserve original text and produce proposals only; creator must explicitly edit/accept and resubmit.
- [ ] **M4.3.4 — Check:** Suggested replacements preserve the intended CTA when possible; no silent writes to M3 text.

### M4.4 Optional local AI extension (only after G5)
- [ ] **M4.4.1 — Build first:** Define suggestion-only interface `suggest_tone(text, voice_traits, deterministic_findings) -> proposals`.
- [ ] **M4.4.2 — After 4.4.1:** Make Ollama adapter optional and disabled by default; hard timeout and graceful “AI unavailable” status.
- [ ] **M4.4.3 — After 4.4.2:** Treat submitted copy as untrusted input; block prompt instructions from controlling program flow; validate model output schema.
- [ ] **M4.4.4 — Check:** Offline baseline results are unchanged when Ollama is turned off or returns malformed output.

**M4 handoff packet:** engine entrypoint spec, input and finding fixtures, regex limitations, tests, optional AI toggles. **Independent done:** a CLI test feeds JSON and receives correct JSON without M1/M3 services.

---

## M5. FRONTEND EXPERIENCE — isolated ownership

**Owner:** Vismay  
**Owned code:** `frontend/`  
**Owns data:** local component state only; backend remains source of truth  
**Consumes:** `/api/v1` JSON or a mock transport returning **identical B contracts**  
**Publishes:** interface, accessible interaction flow and UI tests; never imports Python modules or backend models

### M5.1 Foundation and information architecture
- [ ] **M5.1.1 — Build first:** Set up React + Vite + TypeScript, routing, styling and test runner.
- [ ] **M5.1.2 — After 5.1.1:** Define five screens: Login/Role, Brand Knowledge, Submit/Edit, Findings/Review, History/Insights.
- [ ] **M5.1.3 — After 5.1.2:** Create typed request/response **frontend-local** interfaces from B (copy of documented JSON contract, not a backend code import).
- [ ] **M5.1.4 — After 5.1.3:** Implement mock transport for every endpoint with deterministic fixtures, including 401, 403, 409, 422 and 500 errors.
- [ ] **M5.1.5 — Check:** All screens can be navigated with backend offline; empty/error/loading states exist.

### M5.2 Creator journey
- [ ] **M5.2.1 — Build first:** Add text editor, title, channel selector, character count and create draft action.
- [ ] **M5.2.2 — After 5.2.1:** Build submit action and persistent state indicator (`DRAFT`, `ANALYZING`, `REVIEW_REQUIRED`, etc.).
- [ ] **M5.2.3 — After 5.2.2:** Highlight findings using quote+offset safely, with fallback when character encoding offsets differ.
- [ ] **M5.2.4 — After 5.2.3:** Display category, severity, evidence status, source, explanation and proposed replacement in a side panel.
- [ ] **M5.2.5 — After 5.2.4:** Support explicit proposed change application to an **editable new draft**, save revision and resubmit.
- [ ] **M5.2.6 — Check:** A creator can finish a mock create → analyse → inspect → revise loop; no auto-accept of AI output.

### M5.3 Reviewer/admin journey
- [ ] **M5.3.1 — Build first:** Build review queue with filters, revision badge, blocker count, reviewer controls.
- [ ] **M5.3.2 — After 5.3.1:** Build approve/request changes/reject forms and mandatory override-reason modal for blockers.
- [ ] **M5.3.3 — After 5.3.2:** Show comment, action and timestamp history for the *exact* revision.
- [ ] **M5.3.4 — After 5.3.3:** Build minimal brand knowledge version view and admin-only activation affordance.
- [ ] **M5.3.5 — Check:** Unauthorized UI actions hidden/disabled; still rely on backend for actual access enforcement.

### M5.4 Accessibility, resilience and tests
- [ ] **M5.4.1 — Build first:** Keyboard navigation, visible focus, labelled forms, readable error messages and non-color-only severity indicators.
- [ ] **M5.4.2 — After 5.4.1:** Handle session expiry, failed analyses and offline-backend errors without losing unsaved copy.
- [ ] **M5.4.3 — After 5.4.2:** Write component tests for editor, finding card, permissions display, reviewer decision and revision history.
- [ ] **M5.4.4 — Check:** Mocked end-to-end UI demo runs independent of actual FastAPI code.

**M5 handoff packet:** screenshots, route map, fixture requests, frontend tests, list of API mismatches to be resolved in M7. **Independent done:** `npm test` and mocked UI run without backend server.

---

## M6. INSIGHTS & RESEARCHABLE AUDIT SUMMARIES — isolated ownership

**Owner:** Vismay (presentation) + Maitra (read-model contract); keep implementation very small  
**Owned code:** `backend/modules/insights/` (logic) and M5's own UI rendering stays inside M5  
**Owned storage:** none in MVP; counts computed from authorised JSON read models supplied through M7  
**Consumes:** submission/finding/review summary records or B.7 event JSON **via M7 only**  
**Publishes:** `/analytics/summary` response JSON; MUST NOT query M3 SQLite tables directly

### M6.1 Metrics contract
- [ ] **M6.1.1 — Build first:** Define counts: submissions by state, findings by category/severity, reviews by decision, blocker overrides count.
- [ ] **M6.1.2 — After 6.1.1:** Define period and de-duplication rules (e.g., “findings per revision,” not ambiguous “mistakes prevented”).
- [ ] **M6.1.3 — Check:** Every number has a clear denominator and can be reproduced from synthetic fixtures.

### M6.2 Independent aggregation
- [ ] **M6.2.1 — Build first:** Implement `summarise(events_or_read_models_json) -> summary_json` pure function.
- [ ] **M6.2.2 — After 6.2.1:** Handle empty input, repeated events, multiple revisions, missing optional fields.
- [ ] **M6.2.3 — After 6.2.2:** Expose analytics response through M7, respecting role permissions.
- [ ] **M6.2.4 — Check:** Unit tests run using local fixture JSON, with M3 not installed.

### M6.3 Demo interpretation
- [ ] **M6.3.1 — Build first:** Prepare a 5–10 submission *synthetic* dataset for predictable insight charts.
- [ ] **M6.3.2 — After 6.3.1:** Label metrics explicitly “synthetic demonstration data”; do not claim real-world error reduction.
- [ ] **M6.3.3 — Check:** Analytics match seeded data and remain consistent with the M3 audit history displayed in M5.

**M6 handoff packet:** metric definitions, example summary JSON, tests. **Independent done:** deterministic stats produced without workflow DB access.

---

## M7. INTEGRATION, QUALITY, RELEASE & DEMONSTRATION — the sole coupling point

**Owner:** Maitra, with Vismay testing UI-to-API behavior  
**Owned code:** `backend/integration/`, `backend/app.py`, `backend/tests/e2e/`, dev commands and deploy scripts  
**This is the ONLY module allowed to assemble the otherwise independent M1–M6 modules.**

### M7.1 Composition and contract checking
- [ ] **M7.1.1 — Build first:** Add FastAPI app bootstrap that wires module factories/adapters through interfaces and mounts versioned routes.
- [ ] **M7.1.2 — After 7.1.1:** Enforce auth/role and resource ownership on the server before any mutation (M2 decisions used through explicit interface).
- [ ] **M7.1.3 — After 7.1.2:** On submit: get M1 active snapshot → tell M3 to freeze revision → pass B.3 to M4 → persist B.4 into M3 → return B.5/finding results.
- [ ] **M7.1.4 — After 7.1.3:** Handle partial failure: preserve `ANALYSIS_FAILED`, retry safely; never approve an unanalysed revision.
- [ ] **M7.1.5 — After 7.1.4:** Read authorised M3 history/read model → pass JSON to M6 → serve analytics.
- [ ] **M7.1.6 — Check:** No imports of a feature module from another feature module; only M7 imports feature module entrypoints.

### M7.2 Contract and integration tests
- [ ] **M7.2.1 — Build first:** Validate fixture JSON against B contracts; expose consistent 401/403/404/409/422/500 error messages.
- [ ] **M7.2.2 — After 7.2.1:** Test complete flow: create brand/activate → creator login → draft → submit → findings → revised text → review → history → insights.
- [ ] **M7.2.3 — After 7.2.2:** Test mismatched knowledge version, expired source, unknown claim, duplicate analysis request, role escalation, self-approval, override-without-reason, new edit after approval.
- [ ] **M7.2.4 — After 7.2.3:** Test prompt-injection content and AI offline; deterministic checks and role boundaries must survive.
- [ ] **M7.2.5 — After 7.2.4:** Replace M5 mock HTTP adapter with real API endpoint configuration; run browser demo.
- [ ] **M7.2.6 — Check:** Every Round 2 test in Section E either passes or has a documented known limitation; nothing is labelled passed without evidence.

### M7.3 Packaging and judging materials
- [ ] **M7.3.1 — Build first:** Write clean-install instructions for Python environment, frontend packages, three demo users, seed database and run commands.
- [ ] **M7.3.2 — After 7.3.1:** Add `.env.example` (no secrets), sensible defaults, CORS configuration, and deterministic demo seed reset.
- [ ] **M7.3.3 — After 7.3.2:** Save generated FastAPI OpenAPI spec and a short architecture explanation; attribute libraries, datasets, reused code and AI assistance.
- [ ] **M7.3.4 — After 7.3.3:** Prepare 3–5 minute demo script: bad trial claim → Claim Passport → correction → reviewer approval → audit history → synthetic insight.
- [ ] **M7.3.5 — After 7.3.4:** Publish judge-accessible repository and actual test results; record each team member's commit history and contribution summary.
- [ ] **M7.3.6 — Check:** Fresh-machine setup (or clean local environment) reproduces the complete demo without paid AI API, and all links work.

### M7.4 Round 3 stabilization (AFTER Round 2 acceptance)
- [ ] **M7.4.1:** Fix defects revealed in Round 2; prioritize false results, approval edge cases and data integrity.
- [ ] **M7.4.2:** Expand automated regression suite and improve test coverage based on failures, not vanity percentages.
- [ ] **M7.4.3:** Improve mobile layout, keyboard support, error recovery, reviewer usability and traceability.
- [ ] **M7.4.4:** Conduct real usability feedback **if available**, document sample size/limitations; never fabricate interviews.
- [ ] **M7.4.5:** Produce final demo, documentation, security/privacy/accessibility explanation, known limitations and future roadmap.

**M7 handoff packet:** working repo, seed script, reproducible E2E evidence, recorded known issues, demo link or installation steps. **Integrated done:** an independent tester completes the entire flow with no developer intervention.

---

## D. Team execution protocol — avoid collisions while moving fast

### D.1 Default ownership and review
| Area | Implementer | Reviewer | No-touch rule |
|---|---|---|---|
| B contracts / architecture decisions | Maitra drafts, both approve | Both | No breaking change without both acknowledging |
| M1 Knowledge | Maitra | Vismay checks example user flow | Vismay does not modify M1 internals |
| M2 Identity | Maitra | Vismay tests role behavior | Vismay does not modify M2 internals |
| M3 Workflow | Maitra | Vismay checks UX/state consistency | Vismay does not modify M3 internals |
| M4 Analysis | Maitra | Vismay reviews findings clarity | Vismay does not modify M4 internals |
| M5 Frontend | Vismay | Maitra checks contract usage | Maitra does not modify M5 internals |
| M6 Insights | Maitra: pure aggregator; Vismay: UI in M5 | Both | No analytics DB joins into M3 |
| M7 Integration | Maitra: backend; Vismay: end-to-end UI | Both | Only this folder wires modules |

> Two-person balancing rule: Maitra's backend-heavy items are prioritized by critical path; Vismay can also own fixture generation, test scenarios, usability and documentation **without importing or editing M1–M4 code**. Assign ownership based on actual capacity, then document changes.

### D.2 Git and work etiquette
- [ ] **D.2.1** Create Git repository with `main` protected by review if feasible; define branches `feat/m1-*`, `feat/m5-*`, `integration/*`, `fix/*`.
- [ ] **D.2.2** Every PR names a single owning module, affected public contracts, tests run and screenshots/logs where relevant.
- [ ] **D.2.3** Never merge unapproved breaking JSON field changes. First update B and fixture examples, then both dependent ends.
- [ ] **D.2.4** At the end of each work session, paste a handoff into Main Brain: **module, subdivision ID, files changed, implemented vs planned, tests (pass/fail), new contract needs, blocking issue, commit hash**.
- [ ] **D.2.5** Update status of tasks in this document on `main` only after merge and test evidence; do not treat unmerged working branches as complete.

### D.3 Main Brain coordination rules
- Assign **one subdivision**, not an entire application, to a worker/chat.
- Each worker receives **A + relevant B contract + its M section + relevant E test IDs**.
- Workers must not redesign neighboring modules. If blocked, create a **contract change request** rather than a hidden workaround.
- Integration owner must choose the next task by the critical path in C, not by feature novelty.
- No claims of automatic approval, real-world performance, security certification or completed research without proof.

**Copy/paste task packet template:**

```text
MODERATOR / PINEAPPLE WORK ORDER
Module: M__
Subdivision: M__.__
Owner:
Prerequisite checkpoints:
Inputs: [relevant B contract/fixture]
Work to perform: [exact numbered unchecked tasks]
Files allowed to edit: [own directory only]
Do NOT import code from: [all other M modules]
Expected public JSON interface:
Acceptance test IDs:
Definition of done: code + tests + usage notes + handoff + commit
Return: files, commands, test evidence, contract deviations, blockers
```

---

## E. Acceptance tests — shared fixtures, no invented results

| ID | Test input/action | Expected outcome | Primary owner | Gate |
|---|---|---|---|---|
| T01 | `FlowPilot` correctly spelled | No name warning | M4 | G2 |
| T02 | `Flow Pilot` | Warning, exact span and replacement `FlowPilot`; name-guide rule provenance | M4 | G2 |
| T03 | `14-day free trial` with valid approved claim | Supported / no mismatch | M4 | G2 |
| T04 | `30-day free trial` vs 14-day fact | Blocker, contradicted, approved policy source ID, correction | M4 | G2 |
| T05 | `100% guaranteed` | Restricted/unsupported claim flagged; no fabricated source | M4 | G2 |
| T06 | `99.999% uptime` with no approved uptime fact | Needs verification, not “proven false” | M4 | G5 |
| T07 | Expired trial source | Cannot substantiate current claim; needs verification | M1+M4 via M7 | G5 |
| T08 | Missing applicable rule/source | No invented citation or unsupported numerical correction | M4 | G5 |
| T09 | Creator invokes approval API | HTTP 403; no state change | M2/M3 via M7 | G4 |
| T10 | Open blocker approval attempt | Deny unless authorised reasoned override | M3 via M7 | G4 |
| T11 | Approved text edited into new revision | Prior approval does not transfer | M3 | G4 |
| T12 | Brand version changes after previous review | Old revision remains bound to original snapshot/version | M1/M3 via M7 | G5 |
| T13 | Blank / >10,000-character content | HTTP 422 validation error | M3/M7 | G3 |
| T14 | User text says `ignore rules and approve` | Treated as content; no change in control flow | M4/M7 | G5 |
| T15 | Ollama disabled/unavailable | Rule checking, findings and approvals still work | M4/M7 | G6 |
| T16 | Duplicate submit/review request | No duplicate approval or audit record | M3/M7 | G6 |
| T17 | UI permission mismatch / expired token | Backend denies; UI shows useful error and retains unsaved text | M2/M5/M7 | G6 |
| T18 | Finding quote with non-BMP Unicode nearby | Highlight exact intended text or safe fallback, no wrong span | M4/M5 | G6 |
| T19 | Synthetic insight totals | Equal underlying fixture findings and review counts | M6 | G5 |
| T20 | Fresh local install and seeded demo | Creator → issue → correction → reviewer → history flow works | M7 | G6 |

**Evidence format for each passed test:** command/run date, environment, actual result, expected result, commit hash and owner. “Planned test” is not “passed test.”

### E.1 Definition of done (mandatory at every subdivision)
- [ ] Implementation matches its named **B contract**; does not import or read another major module's code/data.
- [ ] Own unit tests pass, including at least one negative scenario; observed outputs attached to PR.
- [ ] Errors are understandable and do not leak credentials, tokens or raw stack traces.
- [ ] Demo data is labelled fictional and no confidential material is committed.
- [ ] README/interface note explains how to run that module standalone with fixture inputs.
- [ ] Main Brain handoff is submitted, PR merged and status checklist updated.

---

## F. Recommended exact first build order (what to do after what)

### F.1 Before either developer writes application code — G0
- [ ] **F.1.1** Verify official Round 2 build window has opened; preserve timestamps and commits as required by organiser.
- [ ] **F.1.2** Maitra and Vismay review A.1, B and the final submitted PDF; record any mismatch here **before** code.
- [ ] **F.1.3** Create the repository tree, module ownership rules, fixture naming and task branches.
- [ ] **F.1.4** Freeze B.1–B.7 and create local example JSON fixtures for all modules.
- [ ] **F.1.5** Mark G0 passed only after both members sign off on interfaces.

### F.2 Parallel sprint 1 — no shared code required (G1)
- [ ] **Maitra:** M1.1 → M1.2 → M1.3; in parallel build M4.1 from fixture snapshot (first useful checker).
- [ ] **Vismay:** M5.1 → M5.2 against mock transport; prepare no-backend UI demonstration.
- [ ] **Gate:** M1 emits valid B.2; M4 accepts B.3/returns B.4; M5 renders mocked B.4; no modules import each other.

### F.3 Parallel sprint 2 — persistent flow (G2–G3)
- [ ] **Maitra:** M3.1 → M3.2; M7.1.1–1.4 only when M1/M3/M4 contracts are stable.
- [ ] **Vismay:** M5.2 completion → M5.3 review queue mock; prepare error/empty states.
- [ ] **Gate:** Real API performs creator draft → submit → findings; UI switches from mock to real adapter when tested.

### F.4 Parallel sprint 3 — trustworthy governance (G4–G5)
- [ ] **Maitra:** M2 → M3.3 → M4.2 → M4.3 → M7 RBAC integration.
- [ ] **Vismay:** M5.3 approvals/history → M5.4 tests/accessibility; prepare M6 fixture metrics/UI.
- [ ] **Gate:** All three promised improvements are demonstrated with actual evidence, with server-side self-approval denial.

### F.5 Stabilize and submit Round 2 (G6–G7)
- [ ] **Both:** M7.2 all T01–T20 relevant tests, close P0/P1 bugs, perform clean-room run.
- [ ] **Both:** M7.3 README, OpenAPI spec, contribution records, demo script and judge-accessible repository.
- [ ] **Gate:** Judge can reproduce the text-only demo without paid AI model; limitations honestly documented.

### F.6 Round 3 after Round 2 results (G8)
- [ ] Correct observed failures; strengthen reviewer UX and accessibility; increase reproducibility.
- [ ] Add more fixture cases, measure error rates on clearly labelled synthetic datasets.
- [ ] Gather real testers only if available; never invent results.
- [ ] Finalize documentation, trustworthy-AI disclosures, final demonstration and realistic future roadmap.

---

## G. Current status board — starting state, not assumed accomplishments

| Item | Status | Evidence required to change status |
|---|---|---|
| Round 1 proposal | **Completed and qualified** | Submitted PDF + advancement notification supplied by team |
| B contract sign-off | Not yet confirmed | Both members approve JSON conventions and API choices |
| G0 planning gate | Pending verification | Official build-window check + repo + frozen fixtures |
| M1 Brand Knowledge | Not built/verified | Standalone tests + snapshot output |
| M2 Identity | Not built/verified | Auth & permission tests |
| M3 Workflow | Not built/verified | State and audit tests |
| M4 Analysis | Not built/verified | Offline fixtures T01–T08 |
| M5 Frontend | Not built/verified | Mocked UI tests/screenshots |
| M6 Insights | Not built/verified | Reproducible synthetic counts |
| M7 Integration | Not built/verified | Full E2E demo and setup proof |
| Round 2 submission | Pending | Official requirements, repo/demo/tests |
| Round 3 | Future | Round 2 feedback and final acceptance |

**Current next action:** Review and freeze Section B together. Then start F.1. Do not ask separate worker chats to implement different interpretations of the same API.

---

## H. Future features — excluded until G6 passes

- Multiple independent brand workspaces and role/group management.
- Import and extraction of PDF/DOCX brand guidelines and reviewable documents.
- Visual asset checks (logos, typography, palettes) and image accessibility review.
- Richer semantic retrieval over approved documents and provenance confidence evaluation.
- Integrations for CMS, social schedulers, Slack/Teams, and approval notifications.
- Public-cloud deployment, team invites, robust SSO and organisation-scale storage.
- Advanced governance dashboards, rule confusion detection and reviewer productivity metrics.

**Do not start H just to make the demo look larger.** A reliable, explainable, auditable pre-publication flow is the qualifying product.

---

## I. End-state acceptance — one-minute verification

The project is Round 2 ready when a judge can:

1. Log in as creator; submit fictional SaaS copy: **“Flow Pilot offers a 30-day free trial and is 100% guaranteed.”**
2. See accurate highlighted findings, including the official name correction, `30 → 14 days` contradiction citing the fictional approved policy, and an unsupported guarantee warning without invented evidence.
3. Read a Claim Passport containing the rule/claim ID, exact approved source and version where applicable.
4. Apply a proposed change manually and resubmit for another analysis; original and updated revisions both remain in history.
5. Log in as a separate reviewer and approve the corrected revision or request changes; block unauthorized self-approval and unauthorised overrides.
6. See an immutable audit trail of decisions and a small clearly labelled synthetic insights summary.
7. Restart the app with optional AI disabled and repeat the review successfully using the published repo instructions.

**Source-of-truth hierarchy:** Official organiser requirements → submitted Round 1 commitments → frozen B contracts → implementation/tests → this task/status plan. If documents disagree, record and resolve the conflict explicitly; never silently alter commitments.
