"""M7 adapter: M2 actor + M1 active version -> independent M3 router."""
from fastapi import Depends, HTTPException
from backend.modules.auth.models import User
from backend.modules.auth.permissions import AuthDependencies
from backend.modules.knowledge.service import get_active_snapshot, knowledge_error
from backend.modules.workflow.database import make_session_factory as make_workflow_factory
from backend.modules.workflow.router import create_router
from backend.modules.workflow.schemas import Actor


def build_workflow_router(auth: AuthDependencies, knowledge_factory, workflow_url=None):
    workflow_factory = make_workflow_factory(workflow_url)

    def current_actor(user: User = Depends(auth.current_user)) -> Actor:
        return Actor(
            id=user.id, role=user.role, can_create=user.can_create,
            can_review=user.can_review, can_approve=user.can_approve,
            can_manage_knowledge=user.can_manage_knowledge,
            can_manage_users=user.can_manage_users,
        )

    def active_version(brand_id: str) -> str:
        try:
            with knowledge_factory() as session:
                return get_active_snapshot(session, brand_id)['knowledge_version_id']
        except knowledge_error as exc:
            raise HTTPException(status_code=exc.status_code, detail={
                'code': exc.code, 'message': exc.message,
            }) from None

    return create_router(workflow_factory, current_actor, active_version)