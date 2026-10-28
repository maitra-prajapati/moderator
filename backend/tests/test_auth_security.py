
"""Unit and database integration checks for M2.2 password security."""

import pytest
from sqlalchemy import select

from backend.modules.auth.models import User
from backend.modules.auth.security import (
    hash_password,
    password_needs_rehash,
    validate_new_password,
    verify_password,
)
from backend.modules.knowledge.database import make_session_factory


def test_hash_is_argon2id_not_plaintext():
    raw = "CorrectHorseBattery!7"
    encoded = hash_password(raw)

    assert encoded.startswith("$argon2id$")
    assert encoded != raw
    assert raw not in encoded


def test_correct_password_is_accepted():
    raw = "CorrectHorseBattery!7"

    assert verify_password(raw, hash_password(raw)) is True


def test_wrong_password_is_rejected():
    encoded = hash_password("CorrectHorseBattery!7")

    assert verify_password(
        "IncorrectHorseBattery!7",
        encoded,
    ) is False


def test_random_salt_creates_distinct_hashes():
    raw = "CorrectHorseBattery!7"

    first = hash_password(raw)
    second = hash_password(raw)

    assert first != second
    assert verify_password(raw, first) is True
    assert verify_password(raw, second) is True


def test_too_short_password_is_rejected():
    with pytest.raises(ValueError):
        hash_password("short")


def test_long_utf8_password_is_rejected():
    with pytest.raises(ValueError):
        hash_password("🙂" * 257)


def test_non_string_password_is_rejected():
    with pytest.raises(TypeError):
        hash_password(123456)


def test_invalid_inputs_to_verification_return_false():
    good_hash = hash_password("CorrectHorseBattery!7")

    assert verify_password(None, good_hash) is False
    assert verify_password("CorrectHorseBattery!7", None) is False
    assert verify_password("CorrectHorseBattery!7", "garbage") is False
    assert verify_password("CorrectHorseBattery!7", "$argon2id$malformed") is False
    assert verify_password("a" * 1025, good_hash) is False


def test_current_hash_does_not_need_rehash():
    encoded = hash_password("CorrectHorseBattery!7")

    assert password_needs_rehash(encoded) is False


def test_invalid_hash_needs_rehash():
    assert password_needs_rehash("garbage") is True
    assert password_needs_rehash(None) is True


def test_password_whitespace_is_not_trimmed():
    raw = "  CorrectHorseBattery!7  "
    encoded = hash_password(raw)

    assert verify_password(raw, encoded) is True
    assert verify_password(raw.strip(), encoded) is False


def test_new_password_validation_does_not_apply_to_old_hashes():
    # Older accounts may have passwords below the current minimum.
    from argon2 import PasswordHasher

    legacy_hash = PasswordHasher().hash("old-pass")

    assert verify_password("old-pass", legacy_hash) is True

    with pytest.raises(ValueError):
        validate_new_password("old-pass")


def test_database_saves_hash_not_password(tmp_path):
    factory = make_session_factory(
        f"sqlite+pysqlite:///{tmp_path / 'auth.sqlite'}"
    )

    raw = "CorrectHorseBattery!7"

    with factory() as session:
        user = User(
            email="creator@example.com",
            password_hash=hash_password(raw),
        )

        session.add(user)
        session.commit()

        user_id = user.id

    with factory() as session:
        saved = session.scalar(
            select(User).where(User.id == user_id)
        )

        assert saved is not None
        assert saved.password_hash.startswith("$argon2id$")
        assert saved.password_hash != raw
        assert verify_password(raw, saved.password_hash) is True
