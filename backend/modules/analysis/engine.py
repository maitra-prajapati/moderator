"""Deterministic M4 analyser. No IO, databases, or other module imports."""

from datetime import date, datetime, timezone
from hashlib import sha256

import json
import os
import re

from .schemas import (
    AnalysisRequest,
    AnalysisResponse,
    Finding,
    Span,
)

from .tone import suggest_tone


# Python str positions are Unicode code-point offsets, as required by B.1.6.
_TRIAL = re.compile(
    r'(?<!\w)(?P<days>\d{1,3})\s*[-\u2010-\u2015]?\s*days?\s+free\s+trial\b',
    re.IGNORECASE,
)

_UPTIME = re.compile(
    r'(?<!\w)\d+(?:\.\d+)?%\s+uptime\b',
    re.IGNORECASE,
)

_ABSOLUTE = re.compile(
    r'(?<!\w)(?:100%\s+(?:guaranteed|secure|safe)|guaranteed\s+results)\b',
    re.IGNORECASE,
)


def _source_is_usable(source, today: date) -> bool:
    if source is None:
        return False

    if source.valid_until is None:
        return True

    try:
        return date.fromisoformat(source.valid_until) >= today
    except ValueError:
        return False


def _claim_has_evidence(claim, sources, today: date) -> bool:
    """
    Require the source itself to assert the approved trial duration.

    A snapshot reference and expiry check alone cannot establish
    an arbitrary factual claim. This check is deliberately narrow.
    """
    source = sources.get(claim.source_id)

    if (
        not _source_is_usable(source, today)
        or claim.fact_key != "free_trial_days"
    ):
        return False

    if claim.unit.casefold() not in ("day", "days"):
        return False

    return any(
        int(match.group("days")) == claim.value
        for match in _TRIAL.finditer(source.excerpt)
    )


def _stable_id(*parts) -> str:
    raw = json.dumps(
        parts,
        ensure_ascii=False,
        separators=(",", ":"),
    )

    return (
        "find_"
        + sha256(raw.encode("utf-8")).hexdigest()[:24]
    )


def _add(
    rows,
    seen,
    text,
    version,
    category,
    severity,
    evidence,
    start,
    end,
    explanation,
    suggestion=None,
    rule_id=None,
    claim_id=None,
    source_id=None,
    confidence="deterministic",
    scope="",
):
    if end <= start or text[start:end] == "":
        return

    # Deduplicate identical findings, preserving unrelated categories.
    key = (
        category,
        start,
        end,
        rule_id,
        claim_id,
    )

    if key in seen:
        return

    seen.add(key)

    rows.append(
        Finding(
            finding_id=_stable_id(
                scope,
                version,
                text[start:end],
                *key,
            ),
            category=category,
            severity=severity,
            evidence_status=evidence,
            span=Span(
                start=start,
                end=end,
                quote=text[start:end],
            ),
            rule_id=rule_id,
            claim_id=claim_id,
            source_id=source_id,
            knowledge_version_id=version,
            explanation=explanation,
            suggested_replacement=suggestion,
            confidence_kind=confidence,
        )
    )


def _overlaps(start, end, rows) -> bool:
    return any(
        start < row.span.end and row.span.start < end
        for row in rows
    )


def analyse_with_status(
    request_json: dict,
    *,
    as_of: date | None = None,
):
    """
    Return (B.4 analysis response, separate optional AI status).

    Never edits user text or writes to a database.
    """
    req = AnalysisRequest.model_validate(request_json)

    text = req.text
    knowledge = req.knowledge
    version = knowledge.knowledge_version_id

    today = as_of or datetime.now(timezone.utc).date()

    sources = {
        src.id: src
        for src in knowledge.sources
    }

    claims = {
        claim.fact_key: claim
        for claim in knowledge.claims
    }

    rows = []
    seen = set()

    # --------------------------------------------------
    # 1. Terminology and restricted-phrase rules
    # --------------------------------------------------

    for rule in knowledge.rules:
        # Escaping prevents snapshot content from executing regex syntax.
        pattern = re.compile(
            r"(?<!\w)"
            + re.escape(rule.pattern)
            + r"(?!\w)",
            re.IGNORECASE,
        )

        for match in pattern.finditer(text):
            valid_rule_source = (
                rule.source_id
                and _source_is_usable(
                    sources.get(rule.source_id),
                    today,
                )
            )

            explanation = (
                f"Brand policy {rule.id}: "
                + (
                    f"use {rule.replacement!r} instead."
                    if rule.replacement is not None
                    else "this wording is restricted."
                )
            )

            _add(
                rows,
                seen,
                text,
                version,
                rule.type,
                rule.severity,
                "not_applicable",
                match.start(),
                match.end(),
                explanation,
                suggestion=(
                    rule.replacement
                    if rule.type == "terminology"
                    else None
                ),
                rule_id=rule.id,
                source_id=(
                    rule.source_id
                    if valid_rule_source
                    else None
                ),
                scope=req.request_id,
            )

    # --------------------------------------------------
    # 2. Structured free-trial duration checking
    # --------------------------------------------------

    trial_claim = claims.get("free_trial_days")

    evidence_valid = (
        trial_claim is not None
        and _claim_has_evidence(
            trial_claim,
            sources,
            today,
        )
    )

    for match in _TRIAL.finditer(text):
        if _overlaps(
            match.start(),
            match.end(),
            [
                finding
                for finding in rows
                if finding.category == "restricted_phrase"
            ],
        ):
            continue

        observed = int(match.group("days"))

        if not evidence_valid:
            _add(
                rows,
                seen,
                text,
                version,
                "unsupported_claim",
                "warning",
                "needs_verification",
                match.start(),
                match.end(),
                (
                    "Trial duration cannot be verified "
                    "against an approved, current source."
                ),
                claim_id=(
                    trial_claim.id
                    if trial_claim
                    else None
                ),
                scope=req.request_id,
            )

        elif observed != trial_claim.value:
            _add(
                rows,
                seen,
                text,
                version,
                "claim_mismatch",
                "blocker",
                "contradicted",
                match.start(),
                match.end(),
                (
                    f"The approved free trial is "
                    f"{trial_claim.value} days, "
                    f"not {observed} days."
                ),
                suggestion=trial_claim.approved_text,
                claim_id=trial_claim.id,
                source_id=trial_claim.source_id,
                scope=req.request_id,
            )

        else:
            _add(
                rows,
                seen,
                text,
                version,
                "claim_mismatch",
                "info",
                "supported",
                match.start(),
                match.end(),
                (
                    f"Trial duration matches approved "
                    f"{trial_claim.value}-day policy."
                ),
                claim_id=trial_claim.id,
                source_id=trial_claim.source_id,
                scope=req.request_id,
            )

    # --------------------------------------------------
    # 3. Unsupported quantitative / absolute claims
    # --------------------------------------------------

    for regex in (_UPTIME, _ABSOLUTE):
        for match in regex.finditer(text):
            if _overlaps(
                match.start(),
                match.end(),
                rows,
            ):
                continue

            _add(
                rows,
                seen,
                text,
                version,
                "unsupported_claim",
                "warning",
                "needs_verification",
                match.start(),
                match.end(),
                (
                    "Absolute or quantitative claim "
                    "needs approved, current evidence."
                ),
                scope=req.request_id,
            )

    # --------------------------------------------------
    # 4. Optional AI tone suggestions
    # --------------------------------------------------

    status = "disabled"

    if (
        req.ai_enabled
        and os.getenv("MODERATOR_OLLAMA_ENABLED", "0") == "1"
    ):
        ai = suggest_tone(
            text,
            knowledge.voice_traits,
            rows,
            enabled=True,
        )

        status = ai["status"]

        for proposal in ai["proposals"]:
            # An AI suggestion never replaces deterministic findings.
            if _overlaps(
                proposal.start,
                proposal.end,
                rows,
            ):
                continue

            _add(
                rows,
                seen,
                text,
                version,
                "tone",
                "info",
                "not_applicable",
                proposal.start,
                proposal.end,
                proposal.reason,
                suggestion=proposal.replacement,
                confidence="ai_assisted",
                scope=req.request_id,
            )

    # --------------------------------------------------
    # 5. Final ordering and output contract
    # --------------------------------------------------

    priority = {
        "blocker": 0,
        "warning": 1,
        "info": 2,
    }

    rows.sort(
        key=lambda f: (
            f.span.start,
            f.span.end,
            priority[f.severity],
            f.category,
            f.finding_id,
        )
    )

    if len(rows) > 500:
        raise ValueError(
            "Analysis produced over 500 findings; "
            "shorten or split the input"
        )

    output = AnalysisResponse(
        request_id=req.request_id,
        submission_id=req.submission_id,
        revision_id=req.revision_id,
        findings=rows,
    ).model_dump(mode="json")

    return output, status


def analyse(request_json: dict) -> dict:
    """
    Frozen B.3 -> B.4 interface.

    M7 can pass this result to M3 after analysis.
    """
    return analyse_with_status(request_json)[0]