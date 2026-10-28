"""M3 HTTP entrypoint; the M7 caller injects identity and M1 version callbacks."""
from collections.abc import Callable
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from .schemas import Actor, SubmissionCreate, RevisionCreate, ReviewRequest, FindingActionRequest
from . import service


def create_router(
    session_factory: Callable[[], Session],
    get_actor: Callable,
    get_knowledge_version: Callable[[str], str],
) -> APIRouter:
    router = APIRouter(prefix='/api/v1/submissions', tags=['Workflow (M3)'])

    def run(callback):
        try:
            with session_factory() as session:
                return callback(session)
        except service.WorkflowError as exc:
            raise HTTPException(status_code=exc.status, detail={
                'code': exc.code, 'message': exc.message,
            }) from None

    @router.post('', status_code=201)
    def create(data: SubmissionCreate, actor: Actor = Depends(get_actor)):
        return run(lambda s: service.create_submission(s, actor, data))

    @router.get('')
    def listed(limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0),
               actor: Actor = Depends(get_actor)):
        return run(lambda s: service.list_submissions(s, actor, limit, offset))

    @router.get('/{submission_id}')
    def detail(submission_id: str, actor: Actor = Depends(get_actor)):
        return run(lambda s: service.get_submission(s, actor, submission_id))

    @router.post('/{submission_id}/revisions', status_code=201)
    def revise(submission_id: str, data: RevisionCreate, actor: Actor = Depends(get_actor)):
        return run(lambda s: service.create_revision(s, actor, submission_id, data))

    @router.post('/{submission_id}/submit')
    def submit(submission_id: str, actor: Actor = Depends(get_actor)):
        # Need to authorize ownership before retrieving brand knowledge.
        detail = run(lambda s: service.get_submission(s, actor, submission_id))
        if detail['author_id'] != actor.id or not actor.can_create:
            raise HTTPException(status_code=403, detail={
                'code': 'FORBIDDEN', 'message': 'Only the author may submit this content',
            })
        version = detail['knowledge_version_id'] or get_knowledge_version(detail['brand_id'])
        record, request_id = run(lambda s: service.begin_analysis(s, actor, submission_id, version))
        return {**record, 'request_id': request_id}

    @router.get('/{submission_id}/findings')
    def findings(submission_id: str, revision_id: str | None = None,
                 actor: Actor = Depends(get_actor)):
        return run(lambda s: service.findings_for(s, actor, submission_id, revision_id))

    @router.post('/{submission_id}/findings/{finding_id}/actions')
    def action(submission_id: str, finding_id: str, data: FindingActionRequest,
               actor: Actor = Depends(get_actor)):
        return run(lambda s: service.finding_action(s, actor, submission_id, finding_id, data))

    @router.post('/{submission_id}/reviews')
    def review(submission_id: str, data: ReviewRequest, actor: Actor = Depends(get_actor)):
        return run(lambda s: service.review(s, actor, submission_id, data))

    @router.get('/{submission_id}/history')
    def history(submission_id: str, actor: Actor = Depends(get_actor)):
        return run(lambda s: service.history(s, actor, submission_id))

    return router