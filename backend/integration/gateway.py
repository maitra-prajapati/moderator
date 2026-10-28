
"""M7 public API. Only M7 knows about more than one feature module."""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from fastapi import (
    Depends, FastAPI, Header, HTTPException, Query, Request
)
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from jsonschema import Draft202012Validator
from pydantic import BaseModel, ConfigDict, Field, StrictBool, ValidationError

from .ports import Ports
from backend.modules.auth.router import LoginRateLimiter


class Body(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Login(Body):
    email: str
    password: str


class UserCreate(Body):
    email: str
    password: str = Field(min_length=12)
    role: Literal["creator", "reviewer", "admin"]


class BrandAssignments(Body):
    brand_ids: list[str] = Field(max_length=100)


class Create(Body):
    brand_id: str = Field(min_length=1)
    title: str = Field(min_length=1, max_length=200)
    channel: Literal["linkedin", "website", "email"]
    text: str = Field(min_length=1, max_length=10000)


class Revise(Body):
    text: str = Field(min_length=1, max_length=10000)


class Review(Body):
    decision: Literal[
        "approve", "reject",
        "request_changes", "override_approve"
    ]
    comment: str = ""


class Action(Body):
    action: Literal[
        "acknowledge", "accept_suggestion", "dismiss"
    ]
    reason: str | None = None


class ApiFault(Exception):
    def __init__(self, status: int, code: str, message: str):
        self.status_code = status
        self.code = code
        self.message = message
        super().__init__(message)


def fail(status: int, code: str, message: str) -> None:
    raise ApiFault(status, code, message)


def make_app(
    ports: Ports,
    allowed_origins: list[str] | None = None,
) -> FastAPI:
    app = FastAPI(title="MODERATOR", version="1.0.0")
    login_limiter = LoginRateLimiter()

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins or [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ],
        allow_methods=["GET", "POST", "PATCH", "PUT"],
        allow_headers=["Authorization", "Content-Type"],
    )

    @app.exception_handler(RequestValidationError)
    async def validation_error(
        _request: Request,
        exc: RequestValidationError,
    ):
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "INVALID_REQUEST",
                    "message": "Invalid request fields",
                    "details": [
                        {
                            "path": ".".join(
                                map(str, e["loc"])
                            ),
                            "message": e["msg"],
                        }
                        for e in exc.errors()
                    ],
                }
            },
        )

    @app.exception_handler(HTTPException)
    async def http_error(
        _request: Request,
        exc: HTTPException,
    ):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": f"HTTP_{exc.status_code}",
                    "message": str(exc.detail),
                    "details": None,
                }
            },
        )

    @app.exception_handler(ApiFault)
    async def api_fault(
        _request: Request,
        exc: ApiFault,
    ):
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

    @app.exception_handler(Exception)
    async def domain_error(
        _request: Request,
        exc: Exception,
    ):
        status = 422 if isinstance(exc, ValidationError) else getattr(exc, "status_code", 500)

        if type(status) is not int or not (
            400 <= status <= 599
        ):
            status = 500

        code = (
            getattr(exc, "code", None)
            if status < 500
            else None
        )
        message = (
            getattr(exc, "message", None)
            if status < 500
            else None
        )

        return JSONResponse(
            status_code=status,
            content={
                "error": {
                    "code": (
                        code
                        if isinstance(code, str)
                        else "INTERNAL_ERROR"
                    ),
                    "message": (
                        message
                        if isinstance(message, str)
                        else "Internal server error"
                    ),
                    "details": None,
                }
            },
        )

    def actor(
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        if (
            not authorization
            or not authorization.startswith("Bearer ")
        ):
            fail(
                401,
                "UNAUTHENTICATED",
                "Bearer token required",
            )

        token = authorization[len("Bearer "):].strip()

        if not token:
            fail(
                401,
                "UNAUTHENTICATED",
                "Bearer token required",
            )

        try:
            user = ports.auth.me(token)
        except ApiFault:
            raise
        except Exception:
            fail(
                401,
                "UNAUTHENTICATED",
                "Invalid or expired token",
            )

        if (
            not isinstance(user, dict)
            or user.get("is_active") is not True
        ):
            fail(
                401,
                "UNAUTHENTICATED",
                "Inactive or invalid account",
            )

        if (
            not user.get("user_id")
            or not isinstance(
                user.get("permissions"), dict
            )
        ):
            fail(
                401,
                "UNAUTHENTICATED",
                "Invalid identity response",
            )

        return user

    def require(user: dict, permission: str) -> None:
        if (
            user["permissions"].get(permission)
            is not True
        ):
            fail(
                403,
                "FORBIDDEN",
                f"Permission required: {permission}",
            )

    def brand(user: dict, brand_id: str) -> None:
        # Deny access unless M2 explicitly assigns the brand.
        brand_ids = user.get("brand_ids")

        if (
            not isinstance(brand_ids, list)
            or brand_id not in brand_ids
        ):
            fail(
                403,
                "BRAND_FORBIDDEN",
                "Brand access denied",
            )

    def visible(
        user: dict,
        submission: dict,
    ) -> None:
        brand(
            user,
            str(submission.get("brand_id", "")),
        )

        if (
            submission.get("author_id") != user["user_id"]
            and user["permissions"].get("can_review")
            is not True
            and user["permissions"].get("can_approve")
            is not True
        ):
            fail(
                403,
                "SUBMISSION_FORBIDDEN",
                "Submission access denied",
            )

    def get_visible(
        submission_id: str,
        user: dict,
    ) -> dict:
        item = ports.workflow.get(
            submission_id, user
        )

        visible(user, item)

        return item

    def can_see(user: dict, submission: dict) -> bool:
        return (
            isinstance(user.get("brand_ids"), list)
            and submission.get("brand_id")
            in user["brand_ids"]
            and (
                submission.get("author_id")
                == user["user_id"]
                or user["permissions"].get("can_review")
                is True
                or user["permissions"].get("can_approve")
                is True
            )
        )

    @app.get("/api/v1/health")
    def health():
        return {
            "status": "ok",
            "service": "moderator-m7",
        }

    @app.post("/api/v1/auth/login")
    def login(body: Login, request: Request):
        ip = request.client.host if request.client else "unknown"
        if not login_limiter.allowed(ip):
            fail(429, "TOO_MANY_ATTEMPTS", "Too many login attempts; try again later")
        try:
            return ports.auth.login(body.email, body.password)
        except ApiFault as exc:
            if exc.status_code == 401:
                login_limiter.failure(ip)
            raise
        except Exception:
            # Don't convert unavailable infrastructure into bad credentials.
            fail(503, "AUTH_UNAVAILABLE", "Authentication service unavailable")

    @app.get("/api/v1/auth/me")
    def me(user: dict = Depends(actor)):
        return {
            key: value
            for key, value in user.items()
            if key != "brand_ids"
        }

    @app.get("/api/v1/admin/users")
    def users(user: dict = Depends(actor)):
        require(user, "can_manage_users")

        return ports.auth.users(user)

    @app.post(
        "/api/v1/admin/users",
        status_code=201,
    )
    def create_user(
        body: UserCreate,
        user: dict = Depends(actor),
    ):
        require(user, "can_manage_users")

        return ports.auth.create_user(
            user, body.model_dump()
        )

    @app.patch(
        "/api/v1/admin/users/{user_id}/permissions"
    )
    def permissions(
        user_id: str,
        changes: dict[str, StrictBool],
        user: dict = Depends(actor),
    ):
        require(user, "can_manage_users")

        allowed = {
            "can_create",
            "can_review",
            "can_approve",
            "can_manage_knowledge",
            "can_manage_users",
        }

        if (
            not changes
            or any(
                k not in allowed or type(v) is not bool
                for k, v in changes.items()
            )
        ):
            fail(
                422,
                "INVALID_PERMISSIONS",
                "Invalid permissions payload",
            )

        return ports.auth.permissions(
            user,
            user_id,
            changes,
        )

    @app.put("/api/v1/admin/users/{user_id}/brands")
    def update_brands(
        user_id: str,
        body: BrandAssignments,
        user: dict = Depends(actor),
    ):
        require(user, "can_manage_users")
        if user.get("role") != "admin":
            fail(403, "FORBIDDEN", "Admin role required")
        return ports.auth.brands(user, user_id, body.brand_ids)

    @app.get(
        "/api/v1/brands/{brand_id}/knowledge"
    )
    def knowledge(
        brand_id: str,
        user: dict = Depends(actor),
    ):
        brand(user, brand_id)

        return ports.knowledge.active(brand_id)

    @app.post(
        "/api/v1/brands/{brand_id}/knowledge",
        status_code=201,
    )
    def knowledge_draft(
        brand_id: str,
        data: dict,
        user: dict = Depends(actor),
    ):
        require(user, "can_manage_knowledge")
        brand(user, brand_id)

        return ports.knowledge.draft(
            brand_id, data
        )

    @app.post(
        "/api/v1/brands/{brand_id}/knowledge/"
        "{version_no}/activate"
    )
    def activate_knowledge(
        brand_id: str,
        version_no: int,
        user: dict = Depends(actor),
    ):
        require(user, "can_manage_knowledge")
        brand(user, brand_id)

        return ports.knowledge.activate(
            brand_id,
            version_no,
        )

    @app.get("/api/v1/submissions")
    def list_submissions(
        user: dict = Depends(actor),
    ):
        return [
            item
            for item in ports.workflow.list_for(user)
            if can_see(user, item)
        ]

    @app.post(
        "/api/v1/submissions",
        status_code=201,
    )
    def create_submission(
        body: Create,
        user: dict = Depends(actor),
    ):
        require(user, "can_create")
        brand(user, body.brand_id)

        return ports.workflow.create(
            body.model_dump(), user
        )

    @app.get(
        "/api/v1/submissions/{submission_id}"
    )
    def submission(
        submission_id: str,
        user: dict = Depends(actor),
    ):
        return get_visible(submission_id, user)

    @app.post(
        "/api/v1/submissions/{submission_id}/revisions"
    )
    def revision(
        submission_id: str,
        body: Revise,
        user: dict = Depends(actor),
    ):
        require(user, "can_create")

        item = get_visible(
            submission_id, user
        )

        if item.get("author_id") != user["user_id"]:
            fail(
                403,
                "AUTHOR_REQUIRED",
                "Only the author can revise",
            )

        if item.get("state") == "ANALYZING":
            fail(
                409,
                "INVALID_STATE",
                "This submission cannot be revised",
            )

        return ports.workflow.revise(
            submission_id,
            body.text,
            user,
        )

    @app.post(
        "/api/v1/submissions/{submission_id}/submit"
    )
    def submit(
        submission_id: str,
        user: dict = Depends(actor),
    ):
        require(user, "can_create")

        item = get_visible(
            submission_id, user
        )

        if item.get("author_id") != user["user_id"]:
            fail(
                403,
                "AUTHOR_REQUIRED",
                "Only the author can submit",
            )

        if item.get("state") == "REVIEW_REQUIRED":
            return {
                **item,
                "request_id": item.get("request_id"),
            }

        if item.get("state") not in {
            "DRAFT",
            "CHANGES_REQUESTED",
            "ANALYSIS_FAILED",
        }:
            fail(
                409,
                "INVALID_STATE",
                "Submission cannot be analyzed "
                "in its current state",
            )

        # A failed revision must retry under its original M1 version.
        if item.get("state") == "ANALYSIS_FAILED" and item.get("knowledge_version_id"):
            snapshot = ports.knowledge.by_version(
                str(item["brand_id"]), str(item["knowledge_version_id"])
            )
        else:
            snapshot = ports.knowledge.active(str(item["brand_id"]))

        if snapshot.get("brand_id") != item["brand_id"]:
            fail(
                500,
                "BAD_KNOWLEDGE",
                "Knowledge snapshot does not match brand",
            )

        # A source can expire after M1 activation.
        active_sources = {
            x.get("id"): x
            for x in snapshot.get("sources", [])
        }

        for row in [
            *snapshot.get("claims", []),
            *snapshot.get("rules", []),
        ]:
            source = active_sources.get(
                row.get("source_id")
            )

            if not source:
                continue

            until = source.get("valid_until")

            if (
                until
                and date.fromisoformat(until)
                < datetime.now(timezone.utc).date()
            ):
                fail(
                    409,
                    "EXPIRED_SOURCE",
                    "Knowledge evidence expired; "
                    "update the active version",
                )

        version_id = snapshot[
            "knowledge_version_id"
        ]

        frozen = ports.workflow.begin_analysis(
            submission_id, user, version_id
        )

        revision_id = str(
            frozen["current_revision_id"]
        )
        request_id = str(frozen["request_id"])

        try:
            if (
                frozen.get("state") != "ANALYZING"
                or frozen.get("knowledge_version_id")
                != version_id
                or not isinstance(
                    frozen.get("text"), str
                )
            ):
                raise ValueError(
                    "Frozen revision violates "
                    "the analysis contract"
                )

            request = {
                "request_id": request_id,
                "submission_id": submission_id,
                "revision_id": revision_id,
                "channel": frozen["channel"],
                "text": frozen["text"],
                "knowledge": snapshot,
                "ai_enabled": False,
            }

            result = ports.analyse(request)

            if (
                not isinstance(result, dict)
                or not isinstance(
                    result.get("findings"), list
                )
                or result.get("status")
                in {"FAILED", "ANALYSIS_FAILED"}
                or result.get("analysis_status")
                in {"FAILED", "ANALYSIS_FAILED"}
            ):
                raise ValueError(
                    "M4 did not return "
                    "completed findings"
                )

            if (
                result.get("request_id") != request_id
                or result.get("submission_id") != submission_id
                or result.get("revision_id") != revision_id
            ):
                raise ValueError("M4 response IDs do not match frozen request")

            findings = result["findings"]

            _validate_findings(
                findings,
                frozen["text"],
                snapshot,
            )

            saved = ports.workflow.save_analysis(
                submission_id,
                revision_id,
                request_id,
                findings,
                user,
            )

            if (
                saved.get("state") != "REVIEW_REQUIRED"
                or saved.get("current_revision_id")
                != revision_id
            ):
                raise ValueError(
                    "M3 did not confirm persisted "
                    "review-required state"
                )

            return {
                **saved,
                "request_id": request_id,
            }

        except Exception:
            # Check for an already-committed result
            # before recording a failure.
            current = ports.workflow.get(
                submission_id, user
            )

            if (
                current.get("state")
                == "REVIEW_REQUIRED"
                and current.get(
                    "current_revision_id"
                ) == revision_id
                and current.get(
                    "knowledge_version_id"
                ) == version_id
            ):
                return {
                    **current,
                    "request_id": request_id,
                }

            if (
                current.get("state") == "ANALYZING"
                and current.get(
                    "current_revision_id"
                ) == revision_id
            ):
                ports.workflow.fail_analysis(
                    submission_id,
                    revision_id,
                    request_id,
                    "Analysis or persistence failed",
                    user,
                )

            fail(
                500,
                "ANALYSIS_FAILED",
                "Analysis failed; "
                "revision kept for retry",
            )

    @app.get(
        "/api/v1/submissions/{submission_id}/findings"
    )
    def findings(
        submission_id: str,
        revision_id: str | None = None,
        user: dict = Depends(actor),
    ):
        get_visible(submission_id, user)

        return ports.workflow.findings(
            submission_id,
            revision_id,
            user,
        )

    @app.post(
        "/api/v1/submissions/{submission_id}/"
        "findings/{finding_id}/actions"
    )
    def finding_action(
        submission_id: str,
        finding_id: str,
        body: Action,
        user: dict = Depends(actor),
    ):
        require(user, "can_create")

        item = get_visible(
            submission_id, user
        )

        if item.get("author_id") != user["user_id"]:
            fail(
                403,
                "AUTHOR_REQUIRED",
                "Only the author can act on a finding",
            )

        return ports.workflow.finding_action(
            submission_id,
            finding_id,
            body.action,
            body.reason,
            user,
        )

    @app.post(
        "/api/v1/submissions/{submission_id}/reviews"
    )
    def review(
        submission_id: str,
        body: Review,
        user: dict = Depends(actor),
    ):
        require(user, "can_review")

        item = get_visible(
            submission_id, user
        )

        if item.get("state") != "REVIEW_REQUIRED":
            fail(
                409,
                "NOT_REVIEWABLE",
                "Only analyzed submissions "
                "can be reviewed",
            )

        if item.get("author_id") == user["user_id"]:
            fail(
                403,
                "SELF_REVIEW",
                "Author cannot review own submission",
            )

        if body.decision in {
            "approve", "override_approve"
        }:
            require(user, "can_approve")

        if body.decision == "override_approve":
            if (
                user.get("role") != "admin"
                or not body.comment.strip()
            ):
                fail(
                    403,
                    "OVERRIDE_FORBIDDEN",
                    "Admin override requires a reason",
                )

        if (
            body.decision == "approve"
            and item.get(
                "finding_counts", {}
            ).get("blocker", 0) > 0
        ):
            fail(
                409,
                "BLOCKERS_PRESENT",
                "Blocker findings require "
                "an admin override",
            )

        check = ports.workflow.findings(
            submission_id,
            item.get("current_revision_id"),
            user,
        )

        if check.get(
            "analysis_status"
        ) != "COMPLETED":
            fail(
                409,
                "UNANALYZED",
                "The current revision "
                "has not been analyzed",
            )

        return ports.workflow.review(
            submission_id,
            body.decision,
            body.comment,
            user,
        )

    @app.get(
        "/api/v1/submissions/{submission_id}/history"
    )
    def history(
        submission_id: str,
        user: dict = Depends(actor),
    ):
        get_visible(submission_id, user)

        return ports.workflow.history(
            submission_id, user
        )

    @app.get("/api/v1/analytics/summary")
    def analytics(
        start: str | None = Query(None),
        end: str | None = Query(None),
        user: dict = Depends(actor),
    ):
        models = ports.workflow.analytics_models(
            user
        )

        if (
            not isinstance(models, dict)
            or not isinstance(
                models.get("submissions"), list
            )
        ):
            fail(
                500,
                "BAD_READ_MODEL",
                "Analytics read models unavailable",
            )

        eligible = [
            s
            for s in models["submissions"]
            if can_see(user, s)
        ]

        ids = {
            s["submission_id"]
            for s in eligible
        }

        safe = {
            "submissions": eligible,
            "data_label": (
                "authorized application data"
            ),
            "period": {
                "start": start,
                "end": end,
            },
        }

        for key in (
            "findings",
            "reviews",
            "events",
        ):
            rows = models.get(key, [])

            if not isinstance(rows, list):
                fail(
                    500,
                    "BAD_READ_MODEL",
                    "Analytics read models invalid",
                )

            safe[key] = [
                r
                for r in rows
                if isinstance(r, dict)
                and r.get("submission_id") in ids
            ]

        try:
            return ports.summarise(safe)
        except ValueError as exc:
            fail(
                422,
                "INVALID_PERIOD",
                str(exc),
            )

    return app


@lru_cache(maxsize=1)
def _finding_schema_validator() -> Draft202012Validator:
    schema_file = (
        Path(__file__).resolve().parents[1]
        / "contracts"
        / "schemas"
        / "analysis-finding.schema.json"
    )

    schema = json.loads(
        schema_file.read_text(
            encoding="utf-8"
        )
    )

    return Draft202012Validator(schema)


def _validate_findings(
    findings: list,
    text: str,
    snapshot: dict,
) -> None:
    sources = {
        s["id"]
        for s in snapshot.get("sources", [])
    }
    claims = {
        c["id"]
        for c in snapshot.get("claims", [])
    }
    rules = {
        r["id"]
        for r in snapshot.get("rules", [])
    }

    seen_ids: set[str] = set()

    for finding in findings:
        if not isinstance(finding, dict):
            raise ValueError(
                "Finding must be a JSON object"
            )

        _finding_schema_validator().validate(
            finding
        )

        if finding["finding_id"] in seen_ids:
            raise ValueError(
                "Duplicate finding identifier"
            )

        seen_ids.add(finding["finding_id"])

        span = finding.get("span")

        if not isinstance(span, dict):
            raise ValueError(
                "Finding span is missing"
            )

        a = span.get("start")
        b = span.get("end")
        quote = span.get("quote")

        if (
            type(a) is not int
            or type(b) is not int
            or not 0 <= a < b <= len(text)
            or not isinstance(quote, str)
            or text[a:b] != quote
        ):
            raise ValueError(
                "Finding span disagrees "
                "with frozen text"
            )

        if (
            finding.get("knowledge_version_id")
            != snapshot["knowledge_version_id"]
        ):
            raise ValueError(
                "Finding references the wrong "
                "knowledge version"
            )

        for field, valid in (
            ("source_id", sources),
            ("claim_id", claims),
            ("rule_id", rules),
        ):
            reference = finding.get(field)

            if (
                reference is not None
                and reference not in valid
            ):
                raise ValueError(
                    f"Unknown finding {field}"
                )
