# Moderator shared contracts — v1.0

**Team:** PINEAPPLE. **Scope:** Round 2 text-only MVP, fictional FlowPilot Demo.

## Usage
1. Copy `schemas/` and `examples/` into `moderator/docs/contracts/`.
2. Run `pip install jsonschema` and `python validate.py` to check every example.
3. Frontend (Vismay) uses `examples/` as mock fixtures. Backend (Maitra) uses `schemas/` to validate output and generate matching Pydantic models.
4. Freeze a Git commit before building modules; breaking schema changes require agreement from both members.

## Boundary conventions
- All public APIs use `/api/v1`, `application/json` and UTF-8.
- IDs are opaque strings; timestamps are ISO 8601 UTC.
- Backend span offsets are Python Unicode code-point positions with exclusive `end`, not JavaScript UTF-16 indices. Verify `text[start:end] == quote`; the UI must convert offsets when necessary.
- `knowledge` in analysis-request is a complete immutable snapshot, never a database handle.
- `null` source IDs are permitted on policy rules, but never invent evidence. Unsupported claims are `needs_verification`, not automatically `contradicted`.
- Activated knowledge versions are immutable; each review applies to a single revision.
- `override_approve` requires reviewer/admin permissions, justification, and audit logging.
- JSON Schema ensures shape, NOT business rules: add checks for matching spans, referenced IDs, author/reviewer separation, version immutability, and permission enforcement.
- Analysis engine must work with `ai_enabled=false`; optional Ollama is not authoritative.

## API ownership
- M1 knowledge: `/brands/{id}/knowledge`
- M2 identity: `/auth/login`, `/auth/me`
- M3 workflow: `/submissions`, `/submissions/{id}/submit`, `/submissions/{id}/revisions`, `/submissions/{id}/reviews`, findings/history
- M4 analysis: internal JSON `analysis-request` → `analysis-response`
- M6 analytics: `/analytics/summary`
- M7 integration: all public `/api/v1` routes and wiring; only M7 imports module entrypoints.

**Note:** Request/response examples are contract fixtures, not evidence of working implementations.

## Improved validation (v1.1)

Run `python validate.py --verbose --self-test` for schema field summaries and automatic negative tests. It reports all errors across files with JSON paths and helpful explanations. Exit codes: 0 = all pass, 1 = validation failures, 2 = setup/dependency failures. Schema validation checks payload structure, not cross-file foreign keys, business truth, user permissions or running services.
