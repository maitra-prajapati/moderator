# user model hsaring the existing M1 

from datetime import datetime , timezone
from uuid import uuid4
from sqlalchemy import Boolean, CheckConstraint, DateTime, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, validates
from backend.modules.knowledge.models import Base


# role presets apply when account is created
# individual permission remain independent afterwards


ROLE_PERMISSION_DEFAULTS: dict[str, dict[str, bool]] = {
    "creator": {
        "can_create": True,
        "can_review": False,
        "can_approve": False,
        "can_manage_knowledge": False,
        "can_manage_users": False,
    },
    "reviewer": {
        "can_create": False,
        "can_review": True,
        "can_approve": True,
        "can_manage_knowledge": False,
        "can_manage_users": False,
    },
    "admin": {
        "can_create": True,
        "can_review": True,
        "can_approve": True,
        "can_manage_knowledge": True,
        "can_manage_users": True,
    },
}



class User(Base):
    __tablename__ = "auth_users"

    __table_args__ = (
        UniqueConstraint(
            "email",
            name = "uq_auth_users_email",
        ),

        CheckConstraint(
            "role IN ('creator', 'reviewer', 'admin')",
            name = "ck_auth_users_role",
        ),

    )


    # Unique account identifier
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )



    # Case-insensitive email uniqueness in SQLite
    email: Mapped[str] = mapped_column(
        String(320, collation="NOCASE"),
        nullable=False,
        index=True,
    )



    # Store a password hash, never a plaintext password
    password_hash: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
    )


    # Role is a preset label, not the authorization source
    role: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="creator",
    )



    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )


    # Independent account permissions
    can_create: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    can_review: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    can_approve: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    can_manage_knowledge: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    can_manage_users: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    


    def __init__(self, **kwargs):
        role = kwargs.get("role", "creator")

        if role not in ROLE_PERMISSION_DEFAULTS:
            raise ValueError("Unsupported account role")

        # Apply role defaults only for unspecified permissions
        for name, allowed in ROLE_PERMISSION_DEFAULTS[role].items():
            kwargs.setdefault(name, allowed)

        super().__init__(**kwargs)



    @validates("email")
    def _normalize_email(self, _key: str, value: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("Email must be a non-empty string")

        return value.strip().casefold()


