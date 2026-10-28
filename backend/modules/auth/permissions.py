"""Reusable FastAPI authentication and authorization dependencies."""

from collections.abc import Callable

from fastapi import Depends, HTTPException

from fastapi.security import (
    HTTPAuthorizationCredentials,
    HTTPBearer,
)

from sqlalchemy.orm import Session

from .models import User
from .security import read_access_token


bearer = HTTPBearer(auto_error=False)

PERMISSION_NAMES = frozenset({
    "can_create",
    "can_review",
    "can_approve",
    "can_manage_knowledge",
    "can_manage_users",
})


def api_error(
    status: int,
    code: str,
    message: str,
    headers: dict | None = None,
):
    raise HTTPException(
        status_code=status,
        detail={
            "code": code,
            "message": message,
        },
        headers=headers,
    )


class AuthDependencies:

    def __init__(
        self,
        session_factory: Callable[[], Session],
        jwt_secret: str,
    ):
        self.session_factory = session_factory
        self.jwt_secret = jwt_secret

    def current_user(
        self,
        credentials: HTTPAuthorizationCredentials | None = Depends(
            bearer
        ),
    ) -> User:

        if (
            credentials is None
            or credentials.scheme.lower() != "bearer"
        ):
            api_error(
                401,
                "UNAUTHENTICATED",
                "Authentication required",
                {"WWW-Authenticate": "Bearer"},
            )

        user_id = read_access_token(
            credentials.credentials,
            self.jwt_secret,
        )

        if user_id is None:
            api_error(
                401,
                "UNAUTHENTICATED",
                "Invalid or expired access token",
                {"WWW-Authenticate": "Bearer"},
            )

        with self.session_factory() as session:
            user = session.get(User, user_id)

            if user is None or not user.is_active:
                api_error(
                    401,
                    "UNAUTHENTICATED",
                    "Invalid or inactive account",
                    {"WWW-Authenticate": "Bearer"},
                )

            return user

    def require(self, permission: str):
        if permission not in PERMISSION_NAMES:
            raise ValueError(
                f"Unknown permission: {permission}"
            )

        def dependency(
            user: User = Depends(self.current_user),
        ) -> User:

            if not getattr(user, permission):
                api_error(
                    403,
                    "FORBIDDEN",
                    "Insufficient permissions",
                )

            if (
                permission == "can_manage_users"
                and user.role != "admin"
            ):
                api_error(
                    403,
                    "FORBIDDEN",
                    "Administrator access required",
                )

            return user

        return dependency