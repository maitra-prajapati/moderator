from collections.abc import Callable

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from .schemas import knowledgedraft
from .service import knowledge_error, activate, create_draft, get_active_snapshot




def create_router(session_factory: Callable[[], Session]) -> APIRouter:
    router = APIRouter(prefix="/api/v1/brands", tags=["Brand Knowledge (M1)"])

    def handle_error(exc: knowledge_error) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={
            "error": {"code": exc.code, "message": exc.message, "details": None}
        })


    @router.get("/{brand_id}/knowledge")
    def read_knowledge(brand_id: str):
        try:
            with session_factory() as session:
                return get_active_snapshot(session, brand_id)
        except knowledge_error as exc:
            return handle_error(exc)




    @router.post("/{brand_id}/knowledge", status_code=201)
    def new_knowledge_draft(brand_id: str, draft: knowledgedraft):
        try:
            with session_factory() as session:
                return create_draft(session, brand_id, draft)
        except knowledge_error as exc:
            return handle_error(exc)



    @router.post("/{brand_id}/knowledge/{version_no}/activate")
    def activate_knowledge(brand_id: str, version_no: int):
        try:
            with session_factory() as session:
                return activate(session, brand_id, version_no)
        except knowledge_error as exc:
            return handle_error(exc)

    return router


