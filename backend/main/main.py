# example of submission-create schema check while setting up fastapi server

from backend.contracts.validate_v_1 import validate_json, print_validation_result
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
import httpx
from backend.modules.knowledge.database import make_session_factory
from backend.modules.knowledge.router import create_router

def create_app(database_url:str | None = None) -> FastAPI:

    app = FastAPI(title="Moderator MVP", version="0.1.0")
    session_factory = make_session_factory(database_url)
    @app.exception_handler(RequestValidationError)
    async def invalid_request(_request: Request, exc: RequestValidationError):
        issues = [
            {"path": ".".join(map(str, err["loc"])), "message": err["msg"]}
            for err in exc.errors()
        ]

        return JSONResponse(status_code=422, content={
            "error": {
                "code": "INVALID_REQUEST",
                "message": "Request does not match the expected JSON fields",
                "details": {"issues": issues},
            }
        })

    app.include_router(create_router(session_factory))
    return app


app = create_app()
