"""M2 adapter. Keeps JWT, password and permission logic inside M2."""
from __future__ import annotations

import os

from fastapi import HTTPException
from sqlalchemy import Column, ForeignKey, String, Table, select, delete, insert
from sqlalchemy.exc import IntegrityError

from backend.modules.auth.models import User
from backend.modules.auth.schemas import CreateUserRequest, PermissionPatch, UserResponse
from backend.modules.auth.security import (
    create_access_token, get_jwt_secret, hash_password, read_access_token,
    TOKEN_MINUTES,
)
from backend.modules.auth.service import (
    authenticate, create_user, list_users, patch_permissions,
)
from backend.modules.knowledge.database import make_session_factory
from backend.modules.knowledge.models import Base, Brand
from .gateway import ApiFault

# M2 did not previously model brand membership. This additive association
# table supplies explicit, persistent per-email grants. No default access.
USER_BRANDS = Table(
    "auth_user_brands", Base.metadata,
    Column("user_id", String(36), ForeignKey("auth_users.id"), primary_key=True),
    Column("brand_id", String(100), ForeignKey("knowledge_brands.id"), primary_key=True),
)


def _raise_http(exc: HTTPException):
    detail = exc.detail
    if isinstance(detail, dict):
        raise ApiFault(exc.status_code, str(detail.get("code", "ERROR")), str(detail.get("message", "Request rejected"))) from exc
    raise ApiFault(exc.status_code, "HTTP_ERROR", str(detail)) from exc


class AuthAdapter:
    def __init__(self, database_url: str | None = None):
        self.sessions = make_session_factory(database_url)
        Base.metadata.create_all(bind=self.sessions.kw["bind"], tables=[USER_BRANDS])
        # Resolve the JWT secret per request; import/test discovery does not need it.
        # Expensive dummy hash prevents distinguishable unknown email timing.
        self.dummy_hash = hash_password("M7UnusedDummyPassword#123")

    @property
    def jwt_secret(self) -> str:
        return get_jwt_secret()

    @staticmethod
    def _permissions(user: User) -> dict:
        return UserResponse.from_user(user).model_dump(mode="json")

    def _brands(self, session, user_id: str) -> list[str]:
        return list(session.scalars(
            select(USER_BRANDS.c.brand_id)
            .where(USER_BRANDS.c.user_id == user_id)
            .order_by(USER_BRANDS.c.brand_id)
        ))

    def _identity(self, session, user: User) -> dict:
        return {**self._permissions(user), "brand_ids": self._brands(session, user.id)}

    def login(self, email: str, password: str) -> dict:
        with self.sessions() as session:
            user = authenticate(session, email, password, self.dummy_hash)
            if user is None:
                raise ApiFault(401, "INVALID_CREDENTIALS", "Invalid email or password")
            return {
                "access_token": create_access_token(user.id, self.jwt_secret),
                "token_type": "bearer",
                "expires_in": TOKEN_MINUTES * 60,
            }

    def me(self, token: str) -> dict:
        user_id = read_access_token(token, self.jwt_secret)
        if user_id is None:
            raise ApiFault(401, "UNAUTHENTICATED", "Invalid or expired token")
        with self.sessions() as session:
            user = session.get(User, user_id)
            if user is None or not user.is_active:
                raise ApiFault(401, "UNAUTHENTICATED", "Inactive or invalid account")
            return self._identity(session, user)

    def users(self, actor: dict) -> list[dict]:
        with self.sessions() as session:
            return [self._identity(session, user) for user in list_users(session, 10000, 0)]

    def create_user(self, actor: dict, data: dict) -> dict:
        try:
            validated = CreateUserRequest.model_validate(data)
            with self.sessions() as session:
                user = create_user(session, actor["user_id"], validated)
                # Newly created users inherit the administrator's existing
                # grants; an administrator may restrict them using /brands.
                for brand_id in self._brands(session, actor["user_id"]):
                    session.execute(insert(USER_BRANDS).values(user_id=user.id, brand_id=brand_id))
                session.commit()
                return self._identity(session, user)
        except HTTPException as exc:
            _raise_http(exc)

    def permissions(self, actor: dict, user_id: str, changes: dict) -> dict:
        try:
            validated = PermissionPatch.model_validate(changes)
            with self.sessions() as session:
                user = patch_permissions(session, actor["user_id"], user_id, validated)
                return self._identity(session, user)
        except HTTPException as exc:
            _raise_http(exc)

    def brands(self, actor: dict, user_id: str, brand_ids: list[str]) -> dict:
        if actor.get("role") != "admin" or not actor["permissions"].get("can_manage_users"):
            raise ApiFault(403, "FORBIDDEN", "Admin user-management permission required")
        if len(brand_ids) != len(set(brand_ids)) or len(brand_ids) > 100:
            raise ApiFault(422, "INVALID_BRANDS", "Provide distinct brand identifiers")
        with self.sessions() as session:
            target = session.get(User, user_id)
            if not target:
                raise ApiFault(404, "USER_NOT_FOUND", "User not found")
            for brand_id in brand_ids:
                if not isinstance(brand_id, str) or session.get(Brand, brand_id) is None:
                    raise ApiFault(422, "INVALID_BRAND", "Unknown brand identifier")
            session.execute(delete(USER_BRANDS).where(USER_BRANDS.c.user_id == user_id))
            for brand_id in brand_ids:
                session.execute(insert(USER_BRANDS).values(user_id=user_id, brand_id=brand_id))
            session.commit()
            return self._identity(session, target)


def make_auth_port() -> AuthAdapter:
    return AuthAdapter(os.getenv("MODERATOR_KNOWLEDGE_DB_URL"))
