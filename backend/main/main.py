"""FastAPI application factory for M1 and M2."""

import os

from fastapi import FastAPI, HTTPException, Request
from backend.integration.workflow_adapter import build_workflow_router
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.modules.auth.permissions import (
    AuthDependencies,
)

from backend.modules.auth.router import (
    create_router as create_auth_router,
)

from backend.modules.auth.security import (
    get_jwt_secret,
)

from backend.modules.knowledge.database import (
    make_session_factory,
)

from backend.modules.knowledge.router import (
    create_router as create_knowledge_router,
)

def create_app(
    database_url: str | None = None,
    workflow_database_url: str | None = None,
) -> FastAPI:

    # Fail startup if the JWT signing secret is missing.
    secret = get_jwt_secret()

    # Reuse the existing M1 database.
    session_factory = make_session_factory(
        database_url
    )

    auth = AuthDependencies(
        session_factory,
        secret,
    )

    app = FastAPI(
        title="Moderator MVP",
        version="0.2.0",
    )

    # Local frontend development origins.
    origins = [
        origin.strip()
        for origin in os.getenv(
            "MODERATOR_FRONTEND_ORIGINS",
            "http://localhost:5173,http://127.0.0.1:5173",
        ).split(",")
        if origin.strip()
    ]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=False,
        allow_methods=[
            "GET",
            "POST",
            "PATCH",
            "OPTIONS",
        ],
        allow_headers=[
            "Authorization",
            "Content-Type",
        ],
    )

    @app.exception_handler(RequestValidationError)
    async def invalid_request(
        _request: Request,
        exc: RequestValidationError,
    ):

        issues = [
            {
                "path": ".".join(
                    map(str, err["loc"])
                ),
                "message": err["msg"],
            }
            for err in exc.errors()
        ]

        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "INVALID_REQUEST",
                    "message": (
                        "Request does not match "
                        "the expected JSON fields"
                    ),
                    "details": {
                        "issues": issues
                    },
                }
            },
        )

    @app.exception_handler(HTTPException)
    async def http_error(
        _request: Request,
        exc: HTTPException,
    ):

        detail = exc.detail

        if isinstance(detail, dict):
            code = detail.get(
                "code",
                "HTTP_ERROR",
            )
            message = detail.get(
                "message",
                "Request failed",
            )
        else:
            code = "HTTP_ERROR"
            message = str(detail)

        return JSONResponse(
            status_code=exc.status_code,
            headers=exc.headers,
            content={
                "error": {
                    "code": code,
                    "message": message,
                    "details": None,
                }
            },
        )

    # Register M2 authentication endpoints.

    app.include_router(create_auth_router(session_factory, auth))
    app.include_router(create_knowledge_router(session_factory, auth))
    app.include_router(
        build_workflow_router(
            auth,
            session_factory,
            workflow_database_url,
        )
    )
    return app