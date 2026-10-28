"""M2 authentication and administrator API routes."""

from collections import defaultdict, deque
from collections.abc import Callable

from threading import Lock
from time import monotonic

import secrets

from fastapi import (
    APIRouter,
    Depends,
    Query,
    Request,
)

from sqlalchemy.orm import Session

from .models import User
from .permissions import (
    AuthDependencies,
    api_error,
)

from .schemas import (
    CreateUserRequest,
    LoginRequest,
    PermissionPatch,
    StatusPatch,
    TokenResponse,
    UserResponse,
)

from .security import (
    TOKEN_MINUTES,
    create_access_token,
    hash_password,
)

from .service import (
    authenticate,
    create_user,
    list_users,
    patch_permissions,
    patch_status,
)


class LoginRateLimiter:
    """Simple per-process, per-client-IP failure throttle."""

    def __init__(
        self,
        max_failures: int = 5,
        window_seconds: int = 60,
    ):
        self.max_failures = max_failures
        self.window_seconds = window_seconds
        self.entries = defaultdict(deque)
        self.lock = Lock()

    def _prune(self, queue, now):
        while (
            queue
            and now - queue[0] >= self.window_seconds
        ):
            queue.popleft()

    def allowed(self, client_ip: str) -> bool:

        with self.lock:
            queue = self.entries[client_ip]

            self._prune(
                queue,
                monotonic(),
            )

            return len(queue) < self.max_failures

    def failure(self, client_ip: str) -> None:

        with self.lock:
            queue = self.entries[client_ip]

            self._prune(
                queue,
                monotonic(),
            )

            queue.append(monotonic())


def create_router(
    session_factory: Callable[[], Session],
    auth: AuthDependencies,
) -> APIRouter:

    router = APIRouter()

    limiter = LoginRateLimiter()

    # Dummy hash for unknown email verification.
    dummy_hash = hash_password(
        secrets.token_urlsafe(24)
    )

    @router.post(
        "/api/v1/auth/login",
        tags=["Authentication (M2)"],
        response_model=TokenResponse,
    )
    def login(
        data: LoginRequest,
        request: Request,
    ):
        ip = (
            request.client.host
            if request.client
            else "unknown"
        )

        if not limiter.allowed(ip):
            api_error(
                429,
                "TOO_MANY_ATTEMPTS",
                "Too many login attempts. Try again later.",
                {"Retry-After": "60"},
            )

        with session_factory() as session:
            user = authenticate(
                session,
                str(data.email),
                data.password,
                dummy_hash,
            )

        if user is None:
            limiter.failure(ip)

            api_error(
                401,
                "INVALID_CREDENTIALS",
                "Invalid email or password",
                {"WWW-Authenticate": "Bearer"},
            )

        return TokenResponse(
            access_token=create_access_token(
                user.id,
                auth.jwt_secret,
            ),
            expires_in=TOKEN_MINUTES * 60,
        )

    @router.get(
        "/api/v1/auth/me",
        tags=["Authentication (M2)"],
        response_model=UserResponse,
    )
    def me(
        user: User = Depends(auth.current_user),
    ):
        return UserResponse.from_user(user)

    admin = APIRouter(
        prefix="/api/v1/admin",
        tags=["User Administration (M2)"],
        dependencies=[
            Depends(auth.require("can_manage_users"))
        ],
    )

    @admin.get(
        "/users",
        response_model=list[UserResponse],
    )
    def users(
        limit: int = Query(100, ge=1, le=100),
        offset: int = Query(0, ge=0),
    ):
        with session_factory() as session:
            accounts = list_users(
                session,
                limit,
                offset,
            )

            return [
                UserResponse.from_user(user)
                for user in accounts
            ]

    @admin.post(
        "/users",
        response_model=UserResponse,
        status_code=201,
    )
    def new_user(
        data: CreateUserRequest,
        actor: User = Depends(auth.current_user),
    ):
        with session_factory() as session:
            account = create_user(
                session,
                actor.id,
                data,
            )

            return UserResponse.from_user(account)

    @admin.patch(
        "/users/{user_id}/permissions",
        response_model=UserResponse,
    )
    def update_permissions(
        user_id: str,
        data: PermissionPatch,
        actor: User = Depends(auth.current_user),
    ):
        with session_factory() as session:
            account = patch_permissions(
                session,
                actor.id,
                user_id,
                data,
            )

            return UserResponse.from_user(account)

    @admin.patch(
        "/users/{user_id}/status",
        response_model=UserResponse,
    )
    def update_status(
        user_id: str,
        data: StatusPatch,
        actor: User = Depends(auth.current_user),
    ):
        with session_factory() as session:
            account = patch_status(
                session,
                actor.id,
                user_id,
                data,
            )

            return UserResponse.from_user(account)

    router.include_router(admin)

    return router