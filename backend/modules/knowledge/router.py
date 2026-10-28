"""M1 knowledge routes protected by M2 permissions."""

from collections.abc import Callable

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from sqlalchemy.orm import Session

from backend.modules.auth.models import User
from backend.modules.auth.permissions import (
    AuthDependencies,
)

from .schemas import knowledgedraft

from .service import (
    knowledge_error,
    activate,
    create_draft,
    get_active_snapshot,
)


def create_router(
    session_factory: Callable[[], Session],
    auth: AuthDependencies,
) -> APIRouter:

    router = APIRouter(
        prefix="/api/v1/brands",
        tags=["Brand Knowledge (M1)"],
    )

    def handle_error(
        exc: knowledge_error,
    ) -> JSONResponse:

        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "details": None,
                }
            },
        )

    @router.get("/{brand_id}/knowledge")
    def read_knowledge(
        brand_id: str,
        _user: User = Depends(auth.current_user),
    ):

        try:
            with session_factory() as session:
                return get_active_snapshot(
                    session,
                    brand_id,
                )

        except knowledge_error as exc:
            return handle_error(exc)

    @router.post(
        "/{brand_id}/knowledge",
        status_code=201,
    )
    def new_knowledge_draft(
        brand_id: str,
        draft: knowledgedraft,
        _user: User = Depends(
            auth.require("can_manage_knowledge")
        ),
    ):

        try:
            with session_factory() as session:
                return create_draft(
                    session,
                    brand_id,
                    draft,
                )

        except knowledge_error as exc:
            return handle_error(exc)

    @router.post(
        "/{brand_id}/knowledge/{version_no}/activate"
    )
    def activate_knowledge(
        brand_id: str,
        version_no: int,
        _user: User = Depends(
            auth.require("can_manage_knowledge")
        ),
    ):

        try:
            with session_factory() as session:
                return activate(
                    session,
                    brand_id,
                    version_no,
                )

        except knowledge_error as exc:
            return handle_error(exc)

    return router