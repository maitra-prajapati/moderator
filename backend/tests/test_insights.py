import copy
import json
from pathlib import Path

import pytest

from modules.insights import summarise


FIXTURE = (
    Path(__file__).resolve().parents[2]
    / "demo"
    / "fixtures"
    / "m6-synthetic.json"
)


def load():
    return json.loads(
        FIXTURE.read_text(encoding="utf-8")
    )


def test_reproducible_fixture_totals():
    result = summarise(load())

    assert (
        result["total"],
        result["approved"],
        result["reviewing"],
        result["blockers"],
    ) == (8, 3, 2, 5)

    assert result["findings"]["total"] == 11

    assert result["findings"]["by_category"] == {
        "terminology": 2,
        "restricted_phrase": 3,
        "claim_mismatch": 3,
        "unsupported_claim": 1,
        "tone": 2,
    }

    assert result["findings"]["by_severity"] == {
        "info": 2,
        "warning": 3,
        "blocker": 6,
    }

    assert result["reviews"]["total"] == 5

    assert result["reviews"]["by_decision"] == {
        "approve": 2,
        "request_changes": 1,
        "reject": 1,
        "override_approve": 1,
    }

    assert result["reviews"]["blocker_overrides"] == 1

    assert (
        result["data_label"]
        == "synthetic demonstration data"
    )


def test_empty_input_and_explicit_empty_authorized_scope():
    empty = summarise({})

    assert empty["total"] == 0
    assert empty["findings"]["total"] == 0
    assert empty["reviews"]["total"] == 0
    assert empty["blockers"] == 0

    restricted = summarise({
        "submissions": [],
        "findings": load()["findings"],
    })

    assert restricted["findings"]["total"] == 0


def test_duplicate_rows_and_per_revision_distinction():
    fixture = load()

    baseline = summarise(fixture)

    fixture["submissions"] += copy.deepcopy(
        fixture["submissions"]
    )
    fixture["findings"] += copy.deepcopy(
        fixture["findings"]
    )
    fixture["reviews"] += copy.deepcopy(
        fixture["reviews"]
    )
    fixture["events"] += copy.deepcopy(
        fixture["events"]
    )

    assert summarise(fixture) == baseline

    assert (
        baseline["findings"]["by_category"][
            "restricted_phrase"
        ] == 3
    )


def test_reordered_input_is_identical():
    fixture = load()
    expected = summarise(fixture)

    for key in (
        "submissions",
        "findings",
        "reviews",
        "events",
    ):
        fixture[key].reverse()

    assert summarise(fixture) == expected


def test_period_is_start_inclusive_end_exclusive():
    fixture = load()

    fixture["period"] = {
        "start": "2026-10-23T00:00:00Z",
        "end": "2026-10-25T00:00:00Z",
    }

    metrics = summarise(fixture)

    assert metrics["total"] == 2
    assert metrics["approved"] == 1
    assert metrics["blockers"] == 1
    assert metrics["findings"]["total"] == 1
    assert metrics["reviews"]["total"] == 1
    assert (
        metrics["reviews"]["blocker_overrides"]
        == 1
    )


def test_dated_period_does_not_guess_undated_rows():
    fixture = load()

    fixture["findings"].append({
        "finding_id": "undated",
        "submission_id": "sub_001",
        "revision_id": "rev_001",
        "severity": "blocker",
        "category": "tone",
    })

    assert summarise(fixture)["findings"]["total"] == 11

    fixture.pop("period")

    assert summarise(fixture)["findings"]["total"] == 12


def test_scope_restricts_linked_records_to_authorized_submissions():
    fixture = load()

    fixture["submissions"] = [
        fixture["submissions"][0]
    ]

    summary = summarise(fixture)

    assert summary["total"] == 1
    assert summary["findings"]["total"] == 2
    assert summary["reviews"]["total"] == 1

    assert (
        summary["reviews"]["blocker_overrides"]
        == 0
    )


def test_audit_event_fallback_without_review_rows():
    fixture = load()
    fixture["reviews"] = []

    metrics = summarise(fixture)

    assert metrics["reviews"]["total"] == 5
    assert (
        metrics["reviews"]["blocker_overrides"]
        == 1
    )


def test_event_only_input_with_missing_optional_fields():
    metrics = summarise({
        "events": [
            {
                "event_id": "a",
                "event_type": "finding.detected",
                "submission_id": "s",
                "revision_id": "r",
                "metadata": {
                    "finding_id": "f",
                    "category": "terminology",
                    "severity": "warning",
                },
            },
            {
                "event_id": "b",
                "event_type": "review.override_approve",
                "submission_id": "s",
                "revision_id": "r",
            },
        ]
    })

    # Events alone cannot establish current state.
    assert metrics["total"] == 0

    assert metrics["findings"]["total"] == 1
    assert (
        metrics["reviews"]["blocker_overrides"]
        == 1
    )


def test_does_not_mutate_input():
    source = load()
    before = copy.deepcopy(source)

    summarise(source)

    assert source == before


@pytest.mark.parametrize("payload", [
    {
        "period": {
            "start": "2026-10-31T00:00:00Z",
            "end": "2026-10-01T00:00:00Z",
        }
    },
    {"period": {"start": "2026-10-01"}},
    {"submissions": {}},
    {"period": []},
    {"findings": ["not an object"]},
    {"events": [1]},
    [],
])
def test_invalid_input_fails_explicitly(payload):
    with pytest.raises(ValueError):
        summarise(payload)