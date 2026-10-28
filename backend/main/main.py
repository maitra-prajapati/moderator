"""Single server entry point. No-argument app uses M7; URLs preserve M1–M3 test API."""
import os

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from backend.integration.bindings import build_ports
from backend.integration.gateway import make_app


def create_app(knowledge_database_url=None, workflow_database_url=None):
    if knowledge_database_url is not None or workflow_database_url is not None:
        # Legacy module-level route composition for M1/M2/M3 regression tests.
        from backend.modules.auth.permissions import AuthDependencies
        from backend.modules.auth.router import create_router as auth_router
        from backend.modules.auth.security import get_jwt_secret
        from backend.modules.knowledge.database import make_session_factory as knowledge_db
        from backend.modules.knowledge.router import create_router as knowledge_router
        from backend.modules.knowledge.service import get_active_snapshot, knowledge_error
        from backend.modules.workflow.database import make_session_factory as workflow_db
        from backend.modules.workflow.router import create_router as workflow_router
        from backend.modules.workflow.schemas import Actor

        k_factory = knowledge_db(knowledge_database_url)
        auth = AuthDependencies(k_factory, get_jwt_secret())
        legacy = FastAPI(title="MODERATOR Module Contract Tests")

        @legacy.exception_handler(knowledge_error)
        async def _legacy_knowledge_error(_request: Request, exc: knowledge_error):
            return JSONResponse(status_code=exc.status_code, content={"error": {
                "code": exc.code, "message": exc.message, "details": None,
            }})

        @legacy.exception_handler(RequestValidationError)
        async def _legacy_validation(_request: Request, exc: RequestValidationError):
            return JSONResponse(status_code=422, content={"error": {
                "code": "INVALID_REQUEST", "message": "Invalid request fields", "details": None,
            }})

        @legacy.exception_handler(HTTPException)
        async def _legacy_http_error(_request: Request, exc: HTTPException):
            detail = exc.detail
            if not isinstance(detail, dict):
                detail = {"code": f"HTTP_{exc.status_code}", "message": str(detail)}
            return JSONResponse(status_code=exc.status_code, content={
                "error": {
                    "code": detail.get("code", "ERROR"),
                    "message": detail.get("message", "Request failed"),
                    "details": None,
                }
            }, headers=exc.headers)

        legacy.include_router(auth_router(k_factory, auth))
        legacy.include_router(knowledge_router(k_factory, auth))
        if workflow_database_url:
            w_factory = workflow_db(workflow_database_url)

            def workflow_actor(user=Depends(auth.current_user)):
                return Actor(
                    id=user.id, role=user.role,
                    **{k: getattr(user, k) for k in (
                        "can_create", "can_review", "can_approve",
                        "can_manage_knowledge", "can_manage_users",
                    )},
                )

            def active_version(brand_id: str):
                with k_factory() as session:
                    return get_active_snapshot(session, brand_id)["knowledge_version_id"]

            legacy.include_router(workflow_router(w_factory, workflow_actor, active_version))
        return legacy

    raw = os.getenv(
        "MODERATOR_CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173",
    )
    allowed = [x.strip() for x in raw.split(",") if x.strip()]
    return make_app(build_ports(), allowed_origins=allowed)


app = create_app()
