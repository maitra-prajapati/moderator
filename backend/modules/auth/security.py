"""Argon2id password utilities and signed JWT access tokens."""

import os
import secrets

from datetime import datetime, timedelta, timezone

import jwt

from argon2 import PasswordHasher, Type
from argon2.exceptions import (
    InvalidHashError,
    VerificationError,
)


HASHER = PasswordHasher(
    time_cost=3,
    memory_cost=65536,
    parallelism=4,
    hash_len=32,
    salt_len=16,
    type=Type.ID,
)

JWT_ALGORITHM = "HS256"
JWT_ISSUER = "moderator-api"
JWT_AUDIENCE = "moderator-frontend"

TOKEN_MINUTES = 30
MIN_PASSWORD_LENGTH = 12
MAX_PASSWORD_BYTES = 1024


def validate_new_password(password: str) -> None:
    if not isinstance(password, str):
        raise TypeError("Password must be a string")

    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(
            "Password must be at least 12 characters"
        )

    if len(password.encode("utf-8")) > MAX_PASSWORD_BYTES:
        raise ValueError("Password is too long")


# Compatibility with the earlier M2.2 naming.
validate_password = validate_new_password


def hash_password(password: str) -> str:
    validate_new_password(password)

    return HASHER.hash(password)


def verify_password(
    password: str,
    encoded_hash: str,
) -> bool:
    if not isinstance(password, str):
        return False

    if not isinstance(encoded_hash, str):
        return False

    if len(password.encode("utf-8")) > MAX_PASSWORD_BYTES:
        return False

    if not encoded_hash.startswith("$argon2id$"):
        return False

    try:
        return bool(
            HASHER.verify(encoded_hash, password)
        )
    except (VerificationError, InvalidHashError):
        return False


def password_needs_rehash(encoded_hash: str) -> bool:
    if not isinstance(encoded_hash, str):
        return True

    if not encoded_hash.startswith("$argon2id$"):
        return True

    try:
        return HASHER.check_needs_rehash(encoded_hash)
    except (VerificationError, InvalidHashError):
        return True


def get_jwt_secret() -> str:
    secret = os.getenv("MODERATOR_JWT_SECRET", "")

    if len(secret.encode("utf-8")) < 32:
        raise RuntimeError(
            "Set MODERATOR_JWT_SECRET "
            "to at least 32 random bytes"
        )

    return secret


def create_access_token(
    user_id: str,
    secret: str,
) -> str:
    now = datetime.now(timezone.utc)

    payload = {
        "sub": user_id,
        "iat": now,
        "exp": now + timedelta(minutes=TOKEN_MINUTES),
        "iss": JWT_ISSUER,
        "aud": JWT_AUDIENCE,
        "jti": secrets.token_hex(16),
    }

    return jwt.encode(
        payload,
        secret,
        algorithm=JWT_ALGORITHM,
    )


def read_access_token(
    token: str,
    secret: str,
) -> str | None:
    try:
        claims = jwt.decode(
            token,
            secret,
            algorithms=[JWT_ALGORITHM],
            issuer=JWT_ISSUER,
            audience=JWT_AUDIENCE,
            options={
                "require": [
                    "sub",
                    "iat",
                    "exp",
                    "iss",
                    "aud",
                    "jti",
                ]
            },
        )

    except jwt.PyJWTError:
        return None

    subject = claims.get("sub")

    if isinstance(subject, str) and subject:
        return subject

    return None