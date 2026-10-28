"""Strict request and response schemas for M2."""

from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    model_validator,
)


Role = Literal["creator", "reviewer", "admin"]


class StrictModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        strict=True,
    )


class Permissions(StrictModel):
    can_create: bool
    can_review: bool
    can_approve: bool
    can_manage_knowledge: bool
    can_manage_users: bool


class LoginRequest(StrictModel):
    email: EmailStr
    password: str = Field(
        min_length=1,
        max_length=1024,
    )


class TokenResponse(StrictModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int


class UserResponse(StrictModel):
    user_id: str
    email: str
    role: Role
    is_active: bool
    permissions: Permissions

    @classmethod
    def from_user(cls, user):
        return cls(
            user_id=user.id,
            email=user.email,
            role=user.role,
            is_active=user.is_active,
            permissions=Permissions(
                can_create=user.can_create,
                can_review=user.can_review,
                can_approve=user.can_approve,
                can_manage_knowledge=(
                    user.can_manage_knowledge
                ),
                can_manage_users=user.can_manage_users,
            ),
        )


class CreateUserRequest(StrictModel):
    email: EmailStr
    password: str = Field(
        min_length=12,
        max_length=1024,
    )
    role: Role = "creator"


class PermissionPatch(StrictModel):
    can_create: bool | None = None
    can_review: bool | None = None
    can_approve: bool | None = None
    can_manage_knowledge: bool | None = None
    can_manage_users: bool | None = None

    @model_validator(mode="after")
    def check_nonempty(self):
        values = self.model_dump(exclude_unset=True)

        if not values or any(
            value is None for value in values.values()
        ):
            raise ValueError(
                "Provide at least one Boolean permission"
            )

        return self


class StatusPatch(StrictModel):
    is_active: bool