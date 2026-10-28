"""M6: deterministic analytics over JSON, with no database or M1–M5 imports.

M7 must authenticate, authorize, brand-scope and user-scope EVERY supplied row
before calling summarise(). This module is intentionally not an API router.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import json
from typing import Any, Mapping

STATES = (
    "DRAFT", "ANALYZING", "ANALYSIS_FAILED", "REVIEW_REQUIRED",
    "CHANGES_REQUESTED", "APPROVED", "REJECTED",
)

SEVERITIES = ("info", "warning", "blocker")

CATEGORIES = (
    "terminology", "restricted_phrase", "claim_mismatch",
    "unsupported_claim", "tone",
)

DECISIONS = (
    "approve", "request_changes", "reject", "override_approve"
)


def _object(value: Any, name: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be a JSON object")
    return value


def _records(
    data: Mapping[str, Any],
    key: str
) -> list[Mapping[str, Any]]:
    value = data.get(key, [])
    if not isinstance(value, list) or any(
        not isinstance(x, dict) for x in value
    ):
        raise ValueError(f"{key} must be a list of JSON objects")
    return value


def _time(value: Any, label: str) -> datetime | None:
    if value is None or value == "":
        return None

    if not isinstance(value, str):
        raise ValueError(
            f"{label} must be an ISO-8601 timestamp"
        )

    try:
        dt = datetime.fromisoformat(
            value.replace("Z", "+00:00")
        )
    except ValueError as exc:
        raise ValueError(
            f"{label} must be an ISO-8601 timestamp"
        ) from exc

    if dt.tzinfo is None:
        raise ValueError(
            f"{label} must include a UTC offset or Z"
        )

    return dt.astimezone(timezone.utc)


def _key(
    row: Mapping[str, Any],
    id_field: str,
    *parts: str
) -> str:
    identifier = row.get(id_field)

    if isinstance(identifier, str) and identifier.strip():
        return identifier

    # Identical rows without IDs count once.
    # Producers should provide stable identifiers.
    return json.dumps(
        [row.get(p) for p in parts],
        sort_keys=True,
        default=str,
    )


def _unique(
    rows: list[Mapping[str, Any]],
    id_field: str,
    timestamp: str,
    *fallback: str
) -> list[Mapping[str, Any]]:
    """Deduplicate by ID; newest timestamp wins."""

    picked: dict[str, Mapping[str, Any]] = {}

    for row in rows:
        key = _key(row, id_field, *fallback)
        old = picked.get(key)

        if old is None:
            picked[key] = row
        else:
            old_dt = _time(old.get(timestamp), timestamp)
            new_dt = _time(row.get(timestamp), timestamp)

            minimum = datetime.min.replace(
                tzinfo=timezone.utc
            )

            old_order = (
                old_dt or minimum,
                json.dumps(old, sort_keys=True, default=str),
            )
            new_order = (
                new_dt or minimum,
                json.dumps(row, sort_keys=True, default=str),
            )

            if new_order > old_order:
                picked[key] = row

    return list(picked.values())


def _inside(
    row: Mapping[str, Any],
    field: str,
    start: datetime | None,
    end: datetime | None
) -> bool:
    if start is None and end is None:
        return True

    dt = _time(row.get(field), field)

    # Undated records cannot be placed into dated periods.
    return (
        dt is not None
        and (start is None or dt >= start)
        and (end is None or dt < end)
    )


def _positive_int(value: Any) -> int | None:
    if type(value) is int and value >= 0:
        return value
    return None


def summarise(
    events_or_read_models_json: Mapping[str, Any]
) -> dict[str, Any]:
    """Aggregate pre-authorized JSON read models and audit events."""

    data = _object(
        events_or_read_models_json,
        "input"
    )

    period = _object(
        data.get("period", {}),
        "period"
    )

    start = _time(
        period.get("start"),
        "period.start"
    )
    end = _time(
        period.get("end"),
        "period.end"
    )

    if (
        start is not None
        and end is not None
        and start >= end
    ):
        raise ValueError(
            "period.start must be before period.end"
        )

    submissions = _unique(
        _records(data, "submissions"),
        "submission_id",
        "updated_at",
        "submission_id",
    )

    findings = _records(data, "findings")
    reviews = _records(data, "reviews")

    events = _unique(
        _records(data, "events"),
        "event_id",
        "occurred_at",
        "event_type",
        "submission_id",
        "revision_id",
        "occurred_at",
    )

    # Explicit submission scope prevents linked records
    # from contributing counts for unauthorized submissions.
    allowed = {
        x.get("submission_id")
        for x in submissions
        if x.get("submission_id")
    }

    restricted = "submissions" in data

    def authorized(row: Mapping[str, Any]) -> bool:
        return (
            not restricted
            or row.get("submission_id") in allowed
        )

    visible_submissions = [
        s for s in submissions
        if _inside(s, "updated_at", start, end)
    ]

    state_counts = Counter(
        s.get("state", "UNKNOWN")
        for s in visible_submissions
    )

    state_summary = {
        state: state_counts.pop(state, 0)
        for state in STATES
    }

    if state_counts:
        state_summary["UNKNOWN"] = sum(
            state_counts.values()
        )

    # Current-revision blocker counts are from
    # the submission's supplied finding_counts.
    current_blockers = 0

    for s in visible_submissions:
        counts = s.get("finding_counts")

        count = (
            counts.get("blocker")
            if isinstance(counts, dict)
            else None
        )

        if _positive_int(count) is not None:
            current_blockers += count

    # Count each finding once per revision.
    finding_rows: dict[str, Mapping[str, Any]] = {}

    for row in findings:
        if not authorized(row):
            continue

        key = (
            str(row.get("submission_id")),
            str(row.get("revision_id")),
            _key(
                row,
                "finding_id",
                "category",
                "severity",
                "span",
                "rule_id",
                "claim_id",
            ),
        )

        stable_key = json.dumps(key)
        old = finding_rows.get(stable_key)

        if old is None:
            finding_rows[stable_key] = row
        else:
            replacement = _unique(
                [old, row],
                "finding_id",
                "recorded_at",
                "revision_id",
                "category",
                "severity",
            )
            finding_rows[stable_key] = replacement[0]

    # Audit events can supply findings missing
    # from the read-model records.
    for event in events:
        if (
            event.get("event_type") != "finding.detected"
            or not authorized(event)
        ):
            continue

        meta = (
            event.get("metadata")
            if isinstance(event.get("metadata"), dict)
            else {}
        )

        finding_id = meta.get(
            "finding_id",
            event.get("event_id")
        )

        key = json.dumps((
            str(event.get("submission_id")),
            str(event.get("revision_id")),
            str(finding_id),
        ))

        finding_rows.setdefault(
            key,
            {
                "submission_id": event.get(
                    "submission_id"
                ),
                "revision_id": event.get(
                    "revision_id"
                ),
                "finding_id": finding_id,
                "category": meta.get("category"),
                "severity": meta.get("severity"),
                "recorded_at": event.get(
                    "occurred_at"
                ),
            },
        )

    dated_findings = [
        f for f in finding_rows.values()
        if _inside(f, "recorded_at", start, end)
    ]

    category_counts = Counter(
        str(f.get("category") or "unspecified")
        for f in dated_findings
    )

    severity_counts = Counter(
        str(f.get("severity") or "unspecified")
        for f in dated_findings
    )

    by_category = {
        cat: category_counts.pop(cat, 0)
        for cat in CATEGORIES
    }
    by_category.update(
        sorted(category_counts.items())
    )

    by_severity = {
        sev: severity_counts.pop(sev, 0)
        for sev in SEVERITIES
    }
    by_severity.update(
        sorted(severity_counts.items())
    )

    # Count unique reviewer decisions.
    review_rows: dict[str, Mapping[str, Any]] = {}

    explicit_review_triplets: set[
        tuple[Any, Any, str]
    ] = set()

    for row in reviews:
        if not authorized(row):
            continue

        key = _key(
            row,
            "review_id",
            "submission_id",
            "revision_id",
            "decision",
            "occurred_at",
        )

        old = review_rows.get(key)

        if old is None:
            review_rows[key] = row
        else:
            review_rows[key] = _unique(
                [old, row],
                "review_id",
                "occurred_at",
                "submission_id",
                "revision_id",
                "decision",
            )[0]

        explicit_review_triplets.add((
            row.get("submission_id"),
            row.get("revision_id"),
            str(row.get("decision")),
        ))

    # Use audit events as fallback when a matching
    # review read-model record is unavailable.
    for event in events:
        if not authorized(event):
            continue

        event_type = event.get("event_type")

        if (
            not isinstance(event_type, str)
            or not event_type.startswith("review.")
        ):
            continue

        metadata = (
            event.get("metadata")
            if isinstance(event.get("metadata"), dict)
            else {}
        )

        raw_decision = event_type[len("review."):]

        if raw_decision == "approved":
            raw_decision = (
                "override_approve"
                if metadata.get("override") is True
                else "approve"
            )
        elif raw_decision == "rejected":
            raw_decision = "reject"
        elif raw_decision == "changes_requested":
            raw_decision = "request_changes"

        if raw_decision not in DECISIONS:
            continue

        triplet = (
            event.get("submission_id"),
            event.get("revision_id"),
            raw_decision,
        )

        if triplet in explicit_review_triplets:
            continue

        linked_id = metadata.get("review_id")

        key = (
            str(linked_id)
            if linked_id
            else f"event:{event.get('event_id')}"
        )

        review_rows.setdefault(
            key,
            {
                "review_id": key,
                "submission_id": event.get(
                    "submission_id"
                ),
                "revision_id": event.get(
                    "revision_id"
                ),
                "decision": raw_decision,
                "occurred_at": event.get(
                    "occurred_at"
                ),
            },
        )

    dated_reviews = [
        r for r in review_rows.values()
        if _inside(r, "occurred_at", start, end)
    ]

    decision_counts = Counter(
        str(r.get("decision") or "unspecified")
        for r in dated_reviews
    )

    by_decision = {
        decision: decision_counts.pop(decision, 0)
        for decision in DECISIONS
    }

    by_decision.update(
        sorted(decision_counts.items())
    )

    overrides = by_decision["override_approve"]

    return {
        "schema_version": "1.0",

        "data_label": str(
            data.get("data_label")
            or "authorized application data"
        ),

        "period": {
            "start": period.get("start"),
            "end": period.get("end"),
            "end_exclusive": True,
        },

        # Backward-compatible fields for M5 frontend.
        "total": len(visible_submissions),
        "approved": state_summary["APPROVED"],
        "reviewing": state_summary["REVIEW_REQUIRED"],
        "blockers": current_blockers,

        "submissions": {
            "total": len(visible_submissions),
            "by_state": state_summary,
            "unit": (
                "distinct current submission snapshots "
                "updated within period"
            ),
        },

        "findings": {
            "total": len(dated_findings),
            "by_category": by_category,
            "by_severity": by_severity,
            "unit": (
                "distinct finding instances across "
                "revisions, detected within period"
            ),
        },

        "reviews": {
            "total": len(dated_reviews),
            "by_decision": by_decision,
            "blocker_overrides": overrides,
            "unit": (
                "distinct recorded review decisions "
                "within period"
            ),
        },

        "definitions": {
            "blockers": (
                "Sum of current-revision "
                "finding_counts.blocker for selected "
                "submission snapshots; not "
                "necessarily unresolved"
            ),
            "period": (
                "Inclusive start, exclusive end; "
                "timestamps required when period "
                "is filtered"
            ),
            "deduplication": (
                "submission_id; "
                "(submission_id,revision_id,finding_id); "
                "review_id; event_id"
            ),
            "scope": (
                "M7 must pass only authorized, "
                "brand-scoped read models"
            ),
        },
    }