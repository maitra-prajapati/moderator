"""Independent M3 state machine, persistence and immutable audit ledger."""
from sqlalchemy import func, select
from datetime import timezone
from sqlalchemy.orm import Session
from .models import (
    Submission, Revision, AnalysisRun, Finding, FindingAction, Review, AuditEvent,
    new_id, utcnow,
)
from .schemas import Actor, SubmissionCreate, RevisionCreate, AnalysisResponse, ReviewRequest, FindingActionRequest

TRANSITIONS = {
    'DRAFT': {'ANALYZING'},
    'ANALYZING': {'REVIEW_REQUIRED', 'ANALYSIS_FAILED'},
    'ANALYSIS_FAILED': {'ANALYZING', 'DRAFT'},
    'REVIEW_REQUIRED': {'APPROVED', 'REJECTED', 'CHANGES_REQUESTED', 'DRAFT'},
    'CHANGES_REQUESTED': {'DRAFT'},
    'APPROVED': {'DRAFT'},
    'REJECTED': {'DRAFT'},
}


class WorkflowError(Exception):
    def __init__(self, status: int, code: str, message: str):
        self.status = status
        self.code = code
        self.message = message
        super().__init__(message)


def fail(status, code, message):
    raise WorkflowError(status, code, message)


def _write(session: Session):
    if session.get_bind().dialect.name == 'sqlite' and not session.in_transaction():
        session.connection().exec_driver_sql('BEGIN IMMEDIATE')


def _state(sub: Submission, next_state: str):
    if next_state not in TRANSITIONS[sub.state]:
        fail(409, 'INVALID_TRANSITION', f'{sub.state} cannot transition to {next_state}')
    sub.state = next_state
    sub.updated_at = utcnow()


def _iso(value):
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat().replace('+00:00', 'Z')


def _audit(session, sub, revision_id, actor_id, event_type, version=None, **metadata):
    session.add(AuditEvent(
        id=new_id('evt'), event_type=event_type, actor_id=actor_id,
        submission_id=sub.id, revision_id=revision_id,
        knowledge_version_id=version, details=metadata,
    ))


def _sub(session: Session, submission_id: str):
    sub = session.get(Submission, submission_id)
    if sub is None:
        fail(404, 'SUBMISSION_NOT_FOUND', 'Submission not found')
    return sub


def _readable(sub: Submission, actor: Actor):
    if actor.id == sub.author_id or actor.can_review or (
        actor.role == 'admin' and actor.can_manage_users
    ):
        return
    fail(403, 'FORBIDDEN', 'You cannot access this submission')


def _writable(sub: Submission, actor: Actor):
    if actor.id != sub.author_id or not actor.can_create:
        fail(403, 'FORBIDDEN', 'Only the authorized author may edit or submit this content')


def _reviewer(sub: Submission, actor: Actor, decision: str):
    if actor.id == sub.author_id:
        fail(403, 'SELF_REVIEW', 'You cannot review your own submission')
    if not actor.can_review:
        fail(403, 'FORBIDDEN', 'Review permission is required')
    if decision in ('approve', 'override_approve') and not actor.can_approve:
        fail(403, 'FORBIDDEN', 'Approval permission is required')
    if decision == 'override_approve' and not (
        actor.role == 'admin' and actor.can_manage_knowledge and actor.can_approve
    ):
        fail(403, 'OVERRIDE_FORBIDDEN', 'Override requires an authorized administrator')


def _last_run(session, revision_id):
    return session.scalar(select(AnalysisRun).where(
        AnalysisRun.revision_id == revision_id
    ).order_by(AnalysisRun.attempt_no.desc()).limit(1))


def _counts(session, run_id):
    counts = {'info': 0, 'warning': 0, 'blocker': 0}
    if run_id:
        for severity, count in session.execute(
            select(Finding.severity, func.count(Finding.id)).where(
                Finding.analysis_run_id == run_id
            ).group_by(Finding.severity)
        ):
            counts[severity] = count
    return counts


def summary(session: Session, sub: Submission):
    revision = session.get(Revision, sub.current_revision_id)
    run = _last_run(session, revision.id)
    if sub.state in ('DRAFT', 'ANALYZING', 'ANALYSIS_FAILED'):
        run_for_counts = None
    else:
        run_for_counts = run if run and run.status == 'COMPLETED' else None
    return {
        'submission_id': sub.id,
        'brand_id': sub.brand_id,
        'author_id': sub.author_id,
        'title': sub.title,
        'channel': sub.channel,
        'state': sub.state,
        'current_revision_id': revision.id,
        'revision_no': revision.revision_no,
        'knowledge_version_id': run.knowledge_version_id if run else '',
        'finding_counts': _counts(session, run_for_counts.id if run_for_counts else None),
        'updated_at': _iso(sub.updated_at),
    }


def create_submission(session, actor: Actor, data: SubmissionCreate):
    if not actor.can_create:
        fail(403, 'FORBIDDEN', 'Create permission is required')
    _write(session)
    sub_id, rev_id = new_id('sub'), new_id('rev')
    sub = Submission(id=sub_id, brand_id=data.brand_id, author_id=actor.id,
                     title=data.title, channel=data.channel, state='DRAFT',
                     current_revision_id=rev_id)
    rev = Revision(id=rev_id, submission_id=sub_id, revision_no=1,
                   text=data.text, created_by=actor.id)
    session.add(sub)
    session.flush()
    session.add(rev)
    session.flush()  # persist parent rows before inserting FK-linked audit event
    _audit(session, sub, rev_id, actor.id, 'content.created')
    session.commit()
    return summary(session, sub)


def list_submissions(session, actor: Actor, limit: int = 50, offset: int = 0):
    stmt = select(Submission).order_by(Submission.created_at.desc(), Submission.id.desc())
    if not (actor.can_review or (actor.role == 'admin' and actor.can_manage_users)):
        stmt = stmt.where(Submission.author_id == actor.id)
    return [summary(session, sub) for sub in session.scalars(stmt.limit(limit).offset(offset))]


def get_submission(session, actor: Actor, submission_id: str):
    sub = _sub(session, submission_id)
    _readable(sub, actor)
    data = summary(session, sub)
    data['text'] = session.get(Revision, sub.current_revision_id).text
    return data


def create_revision(session, actor: Actor, submission_id: str, data: RevisionCreate):
    _write(session)
    sub = _sub(session, submission_id)
    _writable(sub, actor)
    if sub.state == 'ANALYZING':
        fail(409, 'ANALYSIS_RUNNING', 'Wait for analysis to finish before revising')
    old = session.get(Revision, sub.current_revision_id)
    if old.text == data.text:
        fail(409, 'UNCHANGED_TEXT', 'Revision text must differ from current text')
    rev = Revision(id=new_id('rev'), submission_id=sub.id, revision_no=old.revision_no + 1,
                   text=data.text, created_by=actor.id)
    session.add(rev)
    session.flush()
    sub.current_revision_id = rev.id
    if sub.state != 'DRAFT':
        _state(sub, 'DRAFT')
    else:
        sub.updated_at = utcnow()
    _audit(session, sub, rev.id, actor.id, 'content.revised', prior_revision_id=old.id)
    session.commit()
    return summary(session, sub)


def begin_analysis(session, actor: Actor, submission_id: str, knowledge_version_id: str):
    if not knowledge_version_id:
        fail(422, 'KNOWLEDGE_VERSION_REQUIRED', 'An activated knowledge version is required')
    _write(session)
    sub = _sub(session, submission_id)
    _writable(sub, actor)
    rev_id = sub.current_revision_id
    prior = _last_run(session, rev_id)
    if prior and sub.state in ('ANALYZING', 'REVIEW_REQUIRED', 'APPROVED', 'REJECTED', 'CHANGES_REQUESTED'):
        if prior.knowledge_version_id != knowledge_version_id:
            fail(409, 'VERSION_LOCKED', 'This revision is bound to its first knowledge version')
        return summary(session, sub), prior.id  # idempotent repeated submit
    if sub.state not in ('DRAFT', 'ANALYSIS_FAILED'):
        fail(409, 'INVALID_TRANSITION', f'Cannot submit from {sub.state}')
    if prior and prior.knowledge_version_id != knowledge_version_id:
        fail(409, 'VERSION_LOCKED', 'Retry must use the original knowledge version')
    attempt = (prior.attempt_no + 1) if prior else 1
    run = AnalysisRun(id=new_id('req'), submission_id=sub.id, revision_id=rev_id,
                      attempt_no=attempt, knowledge_version_id=knowledge_version_id,
                      status='ANALYZING')
    session.add(run)
    _state(sub, 'ANALYZING')
    _audit(session, sub, rev_id, actor.id,
           'content.submitted' if attempt == 1 else 'content.analysis_retried',
           knowledge_version_id, request_id=run.id, attempt=attempt)
    session.commit()
    return summary(session, sub), run.id


def complete_analysis(session, response: AnalysisResponse, actor_id: str = 'system:m7'):
    """Called by trusted M7 code, never by a public user-supplied findings endpoint."""
    _write(session)
    run = session.get(AnalysisRun, response.request_id)
    if not run or run.submission_id != response.submission_id or run.revision_id != response.revision_id:
        fail(404, 'ANALYSIS_NOT_FOUND', 'Unknown analysis request/revision')
    sub = _sub(session, response.submission_id)
    if run.status == 'COMPLETED':
        previous = list(session.scalars(select(Finding).where(
            Finding.analysis_run_id == run.id
        )))
        stored = sorted([{
            'finding_id': f.external_finding_id,
            'category': f.category, 'severity': f.severity,
            'evidence_status': f.evidence_status,
            'span': {'start': f.start, 'end': f.end, 'quote': f.quote},
            'rule_id': f.rule_id, 'claim_id': f.claim_id, 'source_id': f.source_id,
            'knowledge_version_id': f.knowledge_version_id,
            'explanation': f.explanation,
            'suggested_replacement': f.suggested_replacement,
            'confidence_kind': f.confidence_kind,
        } for f in previous], key=lambda x: x['finding_id'])
        incoming = sorted([f.model_dump() for f in response.findings],
                          key=lambda x: x['finding_id'])
        if stored != incoming:
            fail(409, 'ANALYSIS_ALREADY_COMPLETED', 'Completed analysis cannot be replaced')
        return summary(session, sub)  # same payload is safely idempotent
    if run.status != 'ANALYZING' or sub.state != 'ANALYZING' or sub.current_revision_id != run.revision_id:
        fail(409, 'ANALYSIS_NOT_CURRENT', 'Analysis request is no longer active')
    revision = session.get(Revision, run.revision_id)
    seen = set()
    for finding in response.findings:
        if finding.finding_id in seen:
            fail(422, 'DUPLICATE_FINDING', 'Duplicate finding ID in analysis response')
        seen.add(finding.finding_id)
        if finding.knowledge_version_id != run.knowledge_version_id:
            fail(422, 'VERSION_MISMATCH', 'Finding knowledge version does not match frozen analysis')
        span = finding.span
        if span.end <= span.start or span.end > len(revision.text) or revision.text[span.start:span.end] != span.quote:
            fail(422, 'INVALID_SPAN', 'Finding offset and quote do not match saved text')
    for finding in response.findings:
        session.add(Finding(
            id=new_id('fnd'), external_finding_id=finding.finding_id,
            analysis_run_id=run.id, submission_id=sub.id, revision_id=revision.id,
            knowledge_version_id=run.knowledge_version_id,
            category=finding.category, severity=finding.severity,
            evidence_status=finding.evidence_status, start=finding.span.start,
            end=finding.span.end, quote=finding.span.quote,
            rule_id=finding.rule_id, claim_id=finding.claim_id, source_id=finding.source_id,
            explanation=finding.explanation, suggested_replacement=finding.suggested_replacement,
            confidence_kind=finding.confidence_kind,
        ))
    run.status = 'COMPLETED'
    run.completed_at = utcnow()
    _state(sub, 'REVIEW_REQUIRED')
    _audit(session, sub, run.revision_id, actor_id, 'content.analysis_completed',
           run.knowledge_version_id, request_id=run.id, finding_count=len(response.findings))
    session.commit()
    return summary(session, sub)


def fail_analysis(session, request_id: str, message: str, actor_id='system:m7'):
    _write(session)
    run = session.get(AnalysisRun, request_id)
    if run is None:
        fail(404, 'ANALYSIS_NOT_FOUND', 'Analysis request not found')
    sub = _sub(session, run.submission_id)
    if run.status == 'FAILED':
        return summary(session, sub)
    if run.status != 'ANALYZING' or sub.current_revision_id != run.revision_id or sub.state != 'ANALYZING':
        fail(409, 'ANALYSIS_NOT_CURRENT', 'Cannot mark this analysis as failed')
    run.status = 'FAILED'
    run.error_message = message[:1000]
    run.completed_at = utcnow()
    _state(sub, 'ANALYSIS_FAILED')
    _audit(session, sub, run.revision_id, actor_id, 'content.analysis_failed',
           run.knowledge_version_id, request_id=run.id)
    session.commit()
    return summary(session, sub)


def findings_for(session, actor: Actor, submission_id: str, revision_id: str | None = None):
    sub = _sub(session, submission_id)
    _readable(sub, actor)
    revision_id = revision_id or sub.current_revision_id
    rev = session.get(Revision, revision_id)
    if not rev or rev.submission_id != sub.id:
        fail(404, 'REVISION_NOT_FOUND', 'Revision not found')
    run = _last_run(session, rev.id)
    if not run:
        return {'revision_id': rev.id, 'knowledge_version_id': None,
                'analysis_status': 'NOT_STARTED', 'findings': []}
    rows = list(session.scalars(select(Finding).where(Finding.analysis_run_id == run.id).order_by(Finding.start, Finding.id)))
    result = []
    for f in rows:
        action = session.scalar(select(FindingAction).where(FindingAction.finding_id == f.id)
                                .order_by(FindingAction.created_at.desc(), FindingAction.id.desc()).limit(1))
        result.append({
            'finding_id': f.external_finding_id, 'category': f.category,
            'severity': f.severity, 'evidence_status': f.evidence_status,
            'span': {'start': f.start, 'end': f.end, 'quote': f.quote},
            'rule_id': f.rule_id, 'claim_id': f.claim_id, 'source_id': f.source_id,
            'knowledge_version_id': f.knowledge_version_id,
            'explanation': f.explanation, 'suggested_replacement': f.suggested_replacement,
            'confidence_kind': f.confidence_kind, 'user_action': action.action if action else None,
            'action_reason': action.reason if action else None,
        })
    return {'revision_id': rev.id, 'knowledge_version_id': run.knowledge_version_id,
            'analysis_status': run.status, 'findings': result}


def finding_action(session, actor: Actor, submission_id: str, finding_id: str, data: FindingActionRequest):
    _write(session)
    sub = _sub(session, submission_id)
    _readable(sub, actor)
    if sub.state != 'REVIEW_REQUIRED':
        fail(409, 'INVALID_TRANSITION', 'Finding actions require REVIEW_REQUIRED')
    if not ((actor.id == sub.author_id and actor.can_create) or actor.can_review):
        fail(403, 'FORBIDDEN', 'Finding action requires creator or reviewer permission')
    run = _last_run(session, sub.current_revision_id)
    f = session.scalar(select(Finding).where(Finding.analysis_run_id == run.id,
                                             Finding.external_finding_id == finding_id))
    if f is None:
        fail(404, 'FINDING_NOT_FOUND', 'Finding not found in current revision')
    if data.action == 'accept_suggestion' and f.suggested_replacement is None:
        fail(409, 'NO_SUGGESTION', 'This finding has no suggested wording')
    # Dismissing a blocker does NOT waive it. Only authorized override can approve it.
    last = session.scalar(select(FindingAction).where(FindingAction.finding_id == f.id)
                          .order_by(FindingAction.created_at.desc(), FindingAction.id.desc()).limit(1))
    if last and last.actor_id == actor.id and last.action == data.action and last.reason == data.reason:
        return {'finding_id': finding_id, 'action': last.action, 'reason': last.reason}
    session.add(FindingAction(id=new_id('fact'), finding_id=f.id, actor_id=actor.id,
                              action=data.action, reason=data.reason))
    _audit(session, sub, f.revision_id, actor.id, 'finding.' + data.action,
           f.knowledge_version_id, finding_id=finding_id, reason=data.reason)
    session.commit()
    return {'finding_id': finding_id, 'action': data.action, 'reason': data.reason}


def review(session, actor: Actor, submission_id: str, data: ReviewRequest):
    _write(session)
    sub = _sub(session, submission_id)
    _reviewer(sub, actor, data.decision)
    rev_id = sub.current_revision_id
    prior = session.scalar(select(Review).where(Review.revision_id == rev_id))
    if prior:
        if prior.reviewer_id == actor.id and prior.decision == data.decision and prior.comment == data.comment:
            return {'review_id': prior.id, 'revision_id': rev_id, 'decision': prior.decision,
                    'state': sub.state, 'comment': prior.comment}  # idempotent replay
        fail(409, 'ALREADY_REVIEWED', 'This revision already has a final reviewer decision')
    if sub.state != 'REVIEW_REQUIRED':
        fail(409, 'INVALID_TRANSITION', 'Review requires completed analysis')
    run = _last_run(session, rev_id)
    if not run or run.status != 'COMPLETED':
        fail(409, 'NOT_ANALYZED', 'Cannot review a revision without completed analysis')
    blocked = bool(session.scalar(select(Finding.id).where(
        Finding.analysis_run_id == run.id, Finding.severity == 'blocker'
    ).limit(1)))
    if data.decision == 'approve' and blocked:
        fail(409, 'OPEN_BLOCKERS', 'Blocker findings require a new revision or authorized override')
    if data.decision == 'override_approve' and not blocked:
        fail(409, 'NO_BLOCKERS', 'Use normal approval when there are no blocker findings')
    state = {
        'approve': 'APPROVED',
        'override_approve': 'APPROVED',
        'request_changes': 'CHANGES_REQUESTED',
        'reject': 'REJECTED',
    }[data.decision]
    row = Review(id=new_id('review'), submission_id=sub.id, revision_id=rev_id,
                 analysis_run_id=run.id, reviewer_id=actor.id,
                 decision=data.decision, comment=data.comment)
    session.add(row)
    _state(sub, state)
    events = {'approve': 'review.approved', 'override_approve': 'review.override_approved',
              'request_changes': 'review.changes_requested', 'reject': 'review.rejected'}
    _audit(session, sub, rev_id, actor.id, events[data.decision], run.knowledge_version_id,
           review_id=row.id, reason=data.comment, override=(data.decision == 'override_approve'))
    session.commit()
    return {'review_id': row.id, 'revision_id': rev_id,
            'decision': data.decision, 'state': state, 'comment': data.comment}


def history(session, actor: Actor, submission_id: str):
    sub = _sub(session, submission_id)
    _readable(sub, actor)
    events = list(session.scalars(select(AuditEvent).where(
        AuditEvent.submission_id == sub.id
    ).order_by(AuditEvent.occurred_at, AuditEvent.id)))
    return [{
        'event_id': e.id, 'event_type': e.event_type,
        'occurred_at': _iso(e.occurred_at),
        'actor_id': e.actor_id, 'submission_id': e.submission_id,
        'revision_id': e.revision_id, 'knowledge_version_id': e.knowledge_version_id,
        'metadata': e.details,
    } for e in events]