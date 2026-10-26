"""M2.1 user model and database integration tests."""

import pytest

from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError

from backend.modules.auth.models import User
from backend.modules.knowledge.database import make_session_factory


def test_auth_table_created_in_existing_database(tmp_path):
    url = f"sqlite+pysqlite:///{tmp_path / 'moderator-test.sqlite'}"

    factory = make_session_factory(url)

    tables = inspect(factory.kw["bind"]).get_table_names()

    assert "auth_users" in tables
    assert "knowledge_brands" in tables
    assert "knowledge_versions" in tables


def test_account_persisted_with_creator_defaults(tmp_path):
    factory = make_session_factory(
        f"sqlite+pysqlite:///{tmp_path / 'test.sqlite'}"
    )

    with factory() as session:
        user = User(
            email="  Creator@Example.COM  ",
            password_hash="fake-test-hash",
        )

        session.add(user)
        session.commit()
        user_id = user.id

    with factory() as session:
        result = session.get(User, user_id)

        assert result is not None
        assert result.email == "creator@example.com"
        assert result.role == "creator"
        assert result.is_active is True
        assert result.can_create is True
        assert result.can_review is False
        assert result.can_approve is False
        assert result.can_manage_knowledge is False
        assert result.can_manage_users is False
        assert result.created_at is not None
        assert result.updated_at is not None


def test_role_presets_and_independent_override(tmp_path):
    factory = make_session_factory(
        f"sqlite+pysqlite:///{tmp_path / 'test.sqlite'}"
    )

    with factory() as session:
        reviewer = User(
            email="reviewer@example.com",
            password_hash="fake-test-hash",
            role="reviewer",
        )

        admin = User(
            email="admin@example.com",
            password_hash="fake-test-hash",
            role="admin",
        )

        custom = User(
            email="custom@example.com",
            password_hash="fake-test-hash",
            role="reviewer",
            can_approve=False,
        )

        session.add_all([reviewer, admin, custom])
        session.commit()

        assert reviewer.can_review is True
        assert reviewer.can_approve is True
        assert reviewer.can_manage_knowledge is False

        assert admin.can_manage_knowledge is True
        assert admin.can_manage_users is True

        assert custom.can_review is True
        assert custom.can_approve is False

        # Changing the role label must not silently grant
        # or revoke permissions.
        admin.role = "creator"

        assert admin.can_manage_users is True


def test_duplicate_case_insensitive_email_rejected(tmp_path):
    factory = make_session_factory(
        f"sqlite+pysqlite:///{tmp_path / 'test.sqlite'}"
    )

    with factory() as session:
        session.add(
            User(
                email="alice@example.com",
                password_hash="fake-test-hash",
            )
        )
        session.commit()

        session.add(
            User(
                email=" ALICE@EXAMPLE.COM ",
                password_hash="fake-test-hash",
            )
        )

        with pytest.raises(IntegrityError):
            session.commit()

        session.rollback()


def test_account_activation_can_be_changed(tmp_path):
    factory = make_session_factory(
        f"sqlite+pysqlite:///{tmp_path / 'test.sqlite'}"
    )

    with factory() as session:
        user = User(
            email="blocked@example.com",
            password_hash="fake-test-hash",
        )

        session.add(user)
        session.commit()

        user.is_active = False
        session.commit()

        user_id = user.id

    with factory() as session:
        assert session.get(User, user_id).is_active is False


def test_unsupported_role_rejected():
    with pytest.raises(ValueError):
        User(
            email="alice@example.com",
            password_hash="fake-test-hash",
            role="owner",
        )