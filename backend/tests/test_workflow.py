"""M3 isolated service tests (no M1/M2/M4 imports) and M7 HTTP integration tests."""
import pytest
from fastapi.testclient import TestClient

from backend.modules.workflow.database import make_session_factory
from backend.modules.workflow.schemas import (
    Actor, SubmissionCreate, RevisionCreate, ReviewRequest,
    FindingIn, AnalysisResponse, FindingActionRequest,
)
from backend.modules.workflow.models import Submission, Revision, Review, AnalysisRun
from backend.modules.workflow import service as m3

CREATOR = Actor('alice', 'creator', can_create=True)
REVIEWER = Actor('bob', 'reviewer', can_review=True, can_approve=True)
ADMIN = Actor('carol', 'admin', can_create=True, can_review=True, can_approve=True,
              can_manage_knowledge=True, can_manage_users=True)
OTHER = Actor('mallory', 'creator', can_create=True)
TEXT = 'Flow Pilot offers a 30-day free trial.'

@pytest.fixture
def db(tmp_path):
    return make_session_factory(f'sqlite+pysqlite:///{tmp_path / "workflow.sqlite"}')


def create(db, author=CREATOR):
    with db() as s:
        return m3.create_submission(s, author, SubmissionCreate(
            brand_id='brand_flowpilot', title='Launch copy', channel='linkedin', text=TEXT))


def start(db, submission_id, actor=CREATOR, version='kv_001'):
    with db() as s:
        return m3.begin_analysis(s, actor, submission_id, version)


def response(row, request_id, blocker=True, bad_span=False, wrong_version=False):
    finding = {
        'finding_id': 'find_1', 'category': 'claim_mismatch',
        'severity': 'blocker' if blocker else 'warning',
        'evidence_status': 'contradicted',
        'span': {'start': 20, 'end': 37, 'quote': '30-day free trial' if not bad_span else '14-day free trial'},
        'rule_id': None, 'claim_id': 'claim_trial', 'source_id': 'src_trial',
        'knowledge_version_id': 'kv_other' if wrong_version else 'kv_001',
        'explanation': 'Trial is 14 days', 'suggested_replacement': '14-day free trial',
        'confidence_kind': 'deterministic',
    }
    return AnalysisResponse(request_id=request_id, submission_id=row['submission_id'],
                            revision_id=row['current_revision_id'], findings=[FindingIn.model_validate(finding)])


def finish(db, row, req, blocker=True):
    with db() as s:
        return m3.complete_analysis(s, response(row, req, blocker))


def raises(code, fn):
    with pytest.raises(m3.WorkflowError) as error:
        fn()
    assert error.value.code == code


def test_create_draft_and_contract(db):
    row = create(db)
    assert row['state'] == 'DRAFT' and row['revision_no'] == 1
    assert row['knowledge_version_id'] == ''
    with db() as s:
        assert m3.get_submission(s, CREATOR, row['submission_id'])['text'] == TEXT
        assert len(m3.history(s, CREATOR, row['submission_id'])) == 1


def test_unauthorized_creation(db):
    with db() as s:
        raises('FORBIDDEN', lambda: m3.create_submission(s, REVIEWER, SubmissionCreate(
            brand_id='brand_flowpilot', title='x', channel='email', text='text')))


def test_visibility_and_ownership(db):
    row = create(db)
    with db() as s:
        assert len(m3.list_submissions(s, CREATOR)) == 1
        assert len(m3.list_submissions(s, OTHER)) == 0
        assert len(m3.list_submissions(s, REVIEWER)) == 1
        raises('FORBIDDEN', lambda: m3.get_submission(s, OTHER, row['submission_id']))
        raises('FORBIDDEN', lambda: m3.create_revision(s, OTHER, row['submission_id'], RevisionCreate(text='other')))


def test_submit_idempotent_and_lock_version(db):
    row = create(db)
    a, req1 = start(db, row['submission_id'])
    b, req2 = start(db, row['submission_id'])
    assert a['state'] == b['state'] == 'ANALYZING'
    assert req1 == req2
    raises('VERSION_LOCKED', lambda: start(db, row['submission_id'], version='kv_002'))


def test_cannot_edit_while_analysing(db):
    row = create(db)
    start(db, row['submission_id'])
    with db() as s:
        raises('ANALYSIS_RUNNING', lambda: m3.create_revision(s, CREATOR,
            row['submission_id'], RevisionCreate(text='changed')))


def test_complete_findings_and_frozen_version(db):
    row = create(db)
    _, req = start(db, row['submission_id'])
    done = finish(db, row, req)
    assert done['state'] == 'REVIEW_REQUIRED'
    assert done['finding_counts']['blocker'] == 1
    with db() as s:
        f = m3.findings_for(s, CREATOR, row['submission_id'])
        assert f['analysis_status'] == 'COMPLETED'
        assert f['knowledge_version_id'] == 'kv_001'
        assert f['findings'][0]['span']['quote'] == '30-day free trial'


def test_empty_findings_still_marks_analysis_complete(db):
    row = create(db)
    _, req = start(db, row['submission_id'])
    with db() as s:
        done = m3.complete_analysis(s, AnalysisResponse(request_id=req,
            submission_id=row['submission_id'], revision_id=row['current_revision_id'], findings=[]))
        assert done['state'] == 'REVIEW_REQUIRED'
        assert done['finding_counts']['blocker'] == 0


def test_bad_span_and_mismatched_version_rejected_atomically(db):
    row = create(db)
    _, req = start(db, row['submission_id'])
    for options, expected in [({'bad_span': True}, 'INVALID_SPAN'),
                              ({'wrong_version': True}, 'VERSION_MISMATCH')]:
        with db() as s:
            raises(expected, lambda: m3.complete_analysis(s, response(row, req, **options)))
            s.rollback()
    with db() as s:
        assert m3.get_submission(s, CREATOR, row['submission_id'])['state'] == 'ANALYZING'
        assert m3.findings_for(s, CREATOR, row['submission_id'])['findings'] == []


def test_analysis_failure_and_retry_audit(db):
    row = create(db)
    _, req1 = start(db, row['submission_id'])
    with db() as s:
        failed = m3.fail_analysis(s, req1, 'offline')
        assert failed['state'] == 'ANALYSIS_FAILED'
    _, req2 = start(db, row['submission_id'])
    assert req1 != req2
    done = finish(db, row, req2)
    assert done['state'] == 'REVIEW_REQUIRED'
    with db() as s:
        assert len(list(s.query(AnalysisRun).filter_by(revision_id=row['current_revision_id']))) == 2
        names = [e['event_type'] for e in m3.history(s, CREATOR, row['submission_id'])]
        assert 'content.analysis_failed' in names and 'content.analysis_retried' in names


def test_self_review_and_creator_denied(db):
    row = create(db)
    _, req = start(db, row['submission_id'])
    finish(db, row, req)
    with db() as s:
        raises('SELF_REVIEW', lambda: m3.review(s, CREATOR, row['submission_id'], ReviewRequest(
            decision='approve', comment='ok')))
        raises('FORBIDDEN', lambda: m3.review(s, OTHER, row['submission_id'], ReviewRequest(
            decision='approve', comment='ok')))


def test_blockers_require_authorized_override(db):
    row = create(db)
    _, req = start(db, row['submission_id'])
    finish(db, row, req)
    with db() as s:
        raises('OPEN_BLOCKERS', lambda: m3.review(s, REVIEWER, row['submission_id'], ReviewRequest(
            decision='approve', comment='looks good')))
        raises('OVERRIDE_FORBIDDEN', lambda: m3.review(s, REVIEWER, row['submission_id'], ReviewRequest(
            decision='override_approve', comment='Approved despite findings')))
        done = m3.review(s, ADMIN, row['submission_id'], ReviewRequest(
            decision='override_approve', comment='Reviewed evidence; approved for demo'))
    assert done['state'] == 'APPROVED'


def test_override_requires_reason(db):
    with pytest.raises(ValueError):
        ReviewRequest(decision='override_approve', comment='')


def test_review_replay_is_idempotent(db):
    row = create(db)
    _, req = start(db, row['submission_id'])
    finish(db, row, req, blocker=False)
    data = ReviewRequest(decision='approve', comment='ok')
    with db() as s:
        first = m3.review(s, REVIEWER, row['submission_id'], data)
        second = m3.review(s, REVIEWER, row['submission_id'], data)
        assert first == second
        assert s.query(Review).count() == 1


def test_review_requires_completed_analysis(db):
    row = create(db)
    with db() as s:
        raises('INVALID_TRANSITION', lambda: m3.review(s, REVIEWER, row['submission_id'], ReviewRequest(
            decision='approve', comment='ok')))


def test_request_changes_and_new_revision_invalidate_approval(db):
    row = create(db)
    _, req = start(db, row['submission_id'])
    finish(db, row, req, blocker=False)
    with db() as s:
        decided = m3.review(s, REVIEWER, row['submission_id'], ReviewRequest(
            decision='approve', comment='ok'))
        edited = m3.create_revision(s, CREATOR, row['submission_id'], RevisionCreate(text='FlowPilot offers 14 days.'))
        assert edited['state'] == 'DRAFT' and edited['revision_no'] == 2
        assert edited['finding_counts']['warning'] == 0
        assert s.get(Revision, row['current_revision_id']).text == TEXT
        assert s.query(Review).filter_by(revision_id=row['current_revision_id']).one().id == decided['review_id']
        assert m3.findings_for(s, CREATOR, row['submission_id'])['analysis_status'] == 'NOT_STARTED'


def test_request_changes_then_edit(db):
    row = create(db)
    _, req = start(db, row['submission_id'])
    finish(db, row, req)
    with db() as s:
        decision = m3.review(s, REVIEWER, row['submission_id'], ReviewRequest(
            decision='request_changes', comment='Fix the 30-day statement'))
        assert decision['state'] == 'CHANGES_REQUESTED'
        assert m3.create_revision(s, CREATOR, row['submission_id'], RevisionCreate(text='Revised.'))['state'] == 'DRAFT'


def test_dismiss_blocker_not_silent_approval(db):
    row = create(db)
    _, req = start(db, row['submission_id'])
    finish(db, row, req)
    with db() as s:
        f = m3.finding_action(s, CREATOR, row['submission_id'], 'find_1',
                              FindingActionRequest(action='dismiss', reason='I disagree'))
        assert f['action'] == 'dismiss'
        raises('OPEN_BLOCKERS', lambda: m3.review(s, REVIEWER, row['submission_id'], ReviewRequest(
            decision='approve', comment='OK')))


def test_accept_suggestion_does_not_change_text(db):
    row = create(db)
    _, req = start(db, row['submission_id'])
    finish(db, row, req)
    with db() as s:
        m3.finding_action(s, CREATOR, row['submission_id'], 'find_1',
                          FindingActionRequest(action='accept_suggestion'))
        assert m3.get_submission(s, CREATOR, row['submission_id'])['text'] == TEXT


def test_revision_validation():
    with pytest.raises(ValueError):
        SubmissionCreate(brand_id='brand_flowpilot', title='t', channel='unknown', text='ok')
    with pytest.raises(ValueError):
        RevisionCreate(text=' ')


def test_saved_audit_is_revision_specific(db):
    row = create(db)
    _, req = start(db, row['submission_id'])
    finish(db, row, req, blocker=False)
    with db() as s:
        m3.review(s, REVIEWER, row['submission_id'], ReviewRequest(decision='approve', comment='ok'))
        new = m3.create_revision(s, CREATOR, row['submission_id'], RevisionCreate(text='new'))
        events = m3.history(s, REVIEWER, row['submission_id'])
        assert any(e['event_type'] == 'review.approved' and e['revision_id'] == row['current_revision_id'] for e in events)
        assert events[-1]['revision_id'] == new['current_revision_id']


def test_duplicate_analysis_completion(db):
    row = create(db)
    _, req = start(db, row['submission_id'])
    with db() as s:
        payload = response(row, req)
        a = m3.complete_analysis(s, payload)
        b = m3.complete_analysis(s, payload)
        assert a == b
        assert m3.findings_for(s, CREATOR, row['submission_id'])['findings'][0]['finding_id'] == 'find_1'


def test_reject_flow(db):
    row = create(db)
    _, req = start(db, row['submission_id'])
    finish(db, row, req)
    with db() as s:
        assert m3.review(s, REVIEWER, row['submission_id'], ReviewRequest(
            decision='reject', comment='Cannot publish'))['state'] == 'REJECTED'


def test_revision_can_use_new_policy_version(db):
    row = create(db)
    _, req = start(db, row['submission_id'])
    finish(db, row, req)
    with db() as s:
        edited = m3.create_revision(s, CREATOR, row['submission_id'], RevisionCreate(text='new'))
    _, newreq = start(db, row['submission_id'], version='kv_002')
    with db() as s:
        assert s.get(AnalysisRun, newreq).knowledge_version_id == 'kv_002'
        assert s.get(AnalysisRun, req).knowledge_version_id == 'kv_001'


def test_duplicate_analysis_with_different_payload_is_denied(db):
    row = create(db)
    _, req = start(db, row['submission_id'])
    with db() as s:
        m3.complete_analysis(s, response(row, req, blocker=True))
    with db() as s:
        raises('ANALYSIS_ALREADY_COMPLETED', lambda: m3.complete_analysis(
            s, response(row, req, blocker=False)))


def test_audit_event_contract(db):
    from backend.contracts.validate_v_1 import validate_json
    row = create(db)
    _, req = start(db, row['submission_id'])
    finish(db, row, req)
    with db() as s:
        for e in m3.history(s, CREATOR, row['submission_id']):
            assert validate_json(e, 'audit-event')['valid']