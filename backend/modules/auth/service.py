"""Database-backed authentication and user management."""

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .models import User
from .permissions import api_error
from .schemas import (
    CreateUserRequest,
    PermissionPatch,
    StatusPatch,
)
from .security import hash_password, verify_password


def lookup_user(
    session: Session,
    email: str,
) -> User | None:

    normalized = email.strip().casefold()

    return session.scalar(
        select(User).where(
            User.email == normalized
        )
    )


def authenticate(
    session: Session,
    email: str,
    password: str,
    dummy_hash: str,
) -> User | None:

    user = lookup_user(session, email)

    # Perform Argon2 verification even for unknown accounts.
    # This reduces differences in response timing.
    stored_hash = (
        user.password_hash
        if user is not None
        else dummy_hash
    )

    valid_password = verify_password(
        password,
        stored_hash,
    )

    if (
        user is None
        or not valid_password
        or not user.is_active
    ):
        return None

    return user


def _begin_sqlite_write(session: Session) -> None:
    # Serialize administrator mutations in SQLite.
    if session.get_bind().dialect.name == "sqlite":
        session.connection().exec_driver_sql(
            "BEGIN IMMEDIATE"
        )


def _assert_admin(
    session: Session,
    actor_id: str,
) -> None:

    actor = session.get(User, actor_id)

    if (
        not actor
        or not actor.is_active
        or actor.role != "admin"
        or not actor.can_manage_users
    ):
        api_error(
            403,
            "FORBIDDEN",
            "Administrator access required",
        )


def _active_admin_count(session: Session) -> int:

    count = session.scalar(
        select(func.count())
        .select_from(User)
        .where(
            User.is_active.is_(True),
            User.role == "admin",
            User.can_manage_users.is_(True),
        )
    )

    return count or 0


def create_user(
    session: Session,
    actor_id: str,
    data: CreateUserRequest,
) -> User:

    hashed = hash_password(data.password)

    _begin_sqlite_write(session)
    _assert_admin(session, actor_id)

    user = User(
        email=str(data.email),
        password_hash=hashed,
        role=data.role,
    )

    session.add(user)

    try:
        session.commit()

    except IntegrityError:
        session.rollback()

        api_error(
            409,
            "EMAIL_IN_USE",
            "Email address already exists",
        )

    session.refresh(user)

    return user


def list_users(
    session: Session,
    limit: int,
    offset: int,
) -> list[User]:

    query = (
        select(User)
        .order_by(User.email)
        .limit(limit)
        .offset(offset)
    )

    return list(session.scalars(query))


def patch_permissions(
    session: Session,
    actor_id: str,
    target_id: str,
    data: PermissionPatch,
) -> User:

    _begin_sqlite_write(session)
    _assert_admin(session, actor_id)

    if target_id == actor_id:
        api_error(
            403,
            "SELF_MODIFICATION_FORBIDDEN",
            "Cannot modify your own permissions",
        )

    target = session.get(User, target_id)

    if target is None:
        api_error(
            404,
            "USER_NOT_FOUND",
            "User not found",
        )

    updated = data.model_dump(
        exclude_unset=True
    )

    # Never remove the last active administrator.
    if (
        target.is_active
        and target.role == "admin"
        and target.can_manage_users
        and updated.get("can_manage_users") is False
        and _active_admin_count(session) <= 1
    ):
        api_error(
            409,
            "LAST_ADMIN",
            "Cannot remove the last active administrator",
        )

    for key, value in updated.items():
        setattr(target, key, value)

    session.commit()
    session.refresh(target)

    return target


def patch_status(
    session: Session,
    actor_id: str,
    target_id: str,
    data: StatusPatch,
) -> User:

    _begin_sqlite_write(session)
    _assert_admin(session, actor_id)

    if target_id == actor_id:
        api_error(
            403,
            "SELF_MODIFICATION_FORBIDDEN",
            "Cannot change your own status",
        )

    target = session.get(User, target_id)

    if target is None:
        api_error(
            404,
            "USER_NOT_FOUND",
            "User not found",
        )

    if (
        target.is_active
        and target.role == "admin"
        and target.can_manage_users
        and not data.is_active
        and _active_admin_count(session) <= 1
    ):
        api_error(
            409,
            "LAST_ADMIN",
            "Cannot disable the last active administrator",
        )

    target.is_active = data.is_active

    session.commit()
    session.refresh(target)

    return target