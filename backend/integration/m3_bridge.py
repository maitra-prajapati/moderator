"""M3 adapter: only workflow service writes workflow tables; analytics is read-only."""
from __future__ import annotations

import os
from datetime import timezone

from sqlalchemy import select

from backend.modules.workflow import service
from backend.modules.workflow.database import make_session_factory
from backend.modules.workflow.models import (
    Submission, AnalysisRun, Finding, Review, AuditEvent,
)
from backend.modules.workflow.schemas import (
    Actor, SubmissionCreate, RevisionCreate, AnalysisResponse,
    ReviewRequest, FindingActionRequest,
)
from .gateway import ApiFault


def _actor(identity: dict) -> Actor:
    p = identity["permissions"]
    return Actor(
        id=identity["user_id"], role=identity["role"],
        **{k: bool(p.get(k)) for k in (
            "can_create", "can_review", "can_approve",
            "can_manage_knowledge", "can_manage_users",
        )},
    )


def _iso(dt):
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat().replace("+00:00", "Z")


def _reject(exc: service.WorkflowError):
    raise ApiFault(exc.status, exc.code, exc.message) from exc


class WorkflowAdapter:
    def __init__(self, database_url: str | None = None):
        self.sessions = make_session_factory(database_url)

    def _call(self, fn):
        try:
            with self.sessions() as session:
                return fn(session)
        except service.WorkflowError as exc:
            _reject(exc)

    def create(self, data: dict, actor: dict) -> dict:
        payload = SubmissionCreate.model_validate(data)
        return self._call(lambda s: service.create_submission(s, _actor(actor), payload))

    def list_for(self, actor: dict) -> list[dict]:
        # M7 rechecks brand/user visibility independently; no page truncation.
        return self._call(lambda s: service.list_submissions(s, _actor(actor), 1_000_000, 0))

    def get(self, submission_id: str, actor: dict) -> dict:
        def run(s):
            record = service.get_submission(s, _actor(actor), submission_id)
            last = service._last_run(s, record["current_revision_id"])
            if last is not None:
                record["request_id"] = last.id
            return record
        return self._call(run)

    def revise(self, submission_id: str, text: str, actor: dict) -> dict:
        payload = RevisionCreate(text=text)
        return self._call(lambda s: service.create_revision(s, _actor(actor), submission_id, payload))

    def begin_analysis(self, submission_id: str, actor: dict, version_id: str) -> dict:
        def run(s):
            record, request_id = service.begin_analysis(s, _actor(actor), submission_id, version_id)
            # The actual persisted M3 AnalysisRun ID, not a synthetic string.
            frozen = service.get_submission(s, _actor(actor), submission_id)
            if (frozen["current_revision_id"] != record["current_revision_id"]
                    or frozen["state"] != "ANALYZING"):
                raise ApiFault(409, "ANALYSIS_NOT_CURRENT", "Revision changed before analysis")
            return {**frozen, "request_id": request_id}
        return self._call(run)

    def save_analysis(self, submission_id: str, revision_id: str, request_id: str,
                      findings: list[dict], actor: dict) -> dict:
        response = AnalysisResponse.model_validate({
            "request_id": request_id, "submission_id": submission_id,
            "revision_id": revision_id, "findings": findings,
        })
        return self._call(lambda s: service.complete_analysis(s, response))

    def fail_analysis(self, submission_id: str, revision_id: str, request_id: str,
                      reason: str, actor: dict) -> None:
        def run(s):
            analysis = s.get(AnalysisRun, request_id)
            if (analysis is None or analysis.submission_id != submission_id
                    or analysis.revision_id != revision_id):
                raise ApiFault(409, "ANALYSIS_NOT_CURRENT", "Analysis request mismatch")
            return service.fail_analysis(s, request_id, reason)
        self._call(run)

    def findings(self, submission_id: str, revision_id: str | None, actor: dict) -> dict:
        return self._call(lambda s: service.findings_for(s, _actor(actor), submission_id, revision_id))

    def finding_action(self, submission_id: str, finding_id: str, action: str,
                       reason: str | None, actor: dict) -> dict:
        payload = FindingActionRequest(action=action, reason=reason)
        return self._call(lambda s: service.finding_action(s, _actor(actor), submission_id, finding_id, payload))

    def review(self, submission_id: str, decision: str, comment: str, actor: dict) -> dict:
        payload = ReviewRequest(decision=decision, comment=comment)
        return self._call(lambda s: service.review(s, _actor(actor), submission_id, payload))

    def history(self, submission_id: str, actor: dict) -> list[dict]:
        return self._call(lambda s: service.history(s, _actor(actor), submission_id))

    def analytics_models(self, actor: dict) -> dict:
        # Scope at query level, before reading findings/reviews/events.
        p = actor["permissions"]
        reviewer = bool(p.get("can_review") or p.get("can_approve"))
        brands = actor.get("brand_ids", [])
        with self.sessions() as session:
            stmt = select(Submission).where(Submission.brand_id.in_(brands))
            if not reviewer:
                stmt = stmt.where(Submission.author_id == actor["user_id"])
            subs = list(session.scalars(stmt))
            ids = [s.id for s in subs]
            if not ids:
                return {"submissions": [], "findings": [], "reviews": [], "events": []}
            findings = []
            for f, run in session.execute(
                select(Finding, AnalysisRun)
                .join(AnalysisRun, Finding.analysis_run_id == AnalysisRun.id)
                .where(Finding.submission_id.in_(ids), AnalysisRun.status == "COMPLETED")
            ):
                findings.append({
                    "finding_id": f.external_finding_id,
                    "submission_id": f.submission_id,
                    "revision_id": f.revision_id,
                    "category": f.category, "severity": f.severity,
                    "recorded_at": _iso(run.completed_at),
                })
            reviews = [{
                "review_id": r.id, "submission_id": r.submission_id,
                "revision_id": r.revision_id, "decision": r.decision,
                "occurred_at": _iso(r.created_at),
            } for r in session.scalars(select(Review).where(Review.submission_id.in_(ids)))]
            events = [{
                "event_id": e.id, "event_type": e.event_type,
                "submission_id": e.submission_id,
                "revision_id": e.revision_id,
                "occurred_at": _iso(e.occurred_at),
                "metadata": e.details,
            } for e in session.scalars(select(AuditEvent).where(AuditEvent.submission_id.in_(ids)))]
            return {
                "submissions": [service.summary(session, s) for s in subs],
                "findings": findings,
                "reviews": reviews,
                "events": events,
            }


def make_workflow_port() -> WorkflowAdapter:
    return WorkflowAdapter(os.getenv("MODERATOR_WORKFLOW_DB_URL"))
