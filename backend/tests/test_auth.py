"""M2 authentication, permission and integration tests."""

from copy import deepcopy

import jwt
import pytest

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from backend.main.main import create_app

from backend.modules.auth.models import User

from backend.modules.auth.permissions import AuthDependencies

from backend.modules.auth.security import (
    create_access_token,
    get_jwt_secret,
    hash_password,
    read_access_token,
)

from backend.modules.knowledge.database import (
    make_session_factory,
)

from backend.modules.knowledge.seed import (
    FLOWPILOT,
    seed,
)

from backend.contracts.validate_v_1 import validate_json


@pytest.fixture
def env(tmp_path):

    url = (
        f"sqlite+pysqlite:///"
        f"{tmp_path / 'm2.sqlite'}"
    )

    app = create_app(url)
    factory = make_session_factory(url)

    seed(factory)

    with factory() as session:
        accounts = {
            "admin": User(
                email="admin@example.com",
                role="admin",
                password_hash=hash_password(
                    "AdminPassword#123"
                ),
            ),
            "creator": User(
                email="creator@example.com",
                role="creator",
                password_hash=hash_password(
                    "CreatorPassword#123"
                ),
            ),
            "reviewer": User(
                email="reviewer@example.com",
                role="reviewer",
                password_hash=hash_password(
                    "ReviewerPassword#123"
                ),
            ),
            "admin2": User(
                email="admin2@example.com",
                role="admin",
                password_hash=hash_password(
                    "Admin2Password#123"
                ),
            ),
        }

        session.add_all(accounts.values())
        session.commit()

        ids = {
            key: account.id
            for key, account in accounts.items()
        }

    return TestClient(app), factory, ids


def header(ids, role):
    token = create_access_token(
        ids[role],
        get_jwt_secret(),
    )

    return {
        "Authorization": f"Bearer {token}"
    }


def test_login_and_me_show_effective_permissions(env):
    client, _, _ = env

    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "CREATOR@example.com",
            "password": "CreatorPassword#123",
        },
    )

    assert response.status_code == 200, response.text

    body = response.json()

    assert body["token_type"] == "bearer"
    assert body["expires_in"] == 1800

    me = client.get(
        "/api/v1/auth/me",
        headers={
            "Authorization": (
                f"Bearer {body['access_token']}"
            )
        },
    )

    assert me.status_code == 200

    assert me.json()["permissions"]["can_create"] is True
    assert me.json()["permissions"]["can_review"] is False

    assert "password_hash" not in str(me.json())

    assert validate_json(
        me.json(),
        "auth-me-response",
    )["valid"] is True


@pytest.mark.parametrize(
    "payload",
    [
        {
            "email": "creator@example.com",
            "password": "wrong",
        },
        {
            "email": "unknown@example.com",
            "password": "wrong",
        },
    ],
)
def test_invalid_credentials_are_indistinguishable(
    env,
    payload,
):
    client, _, _ = env

    response = client.post(
        "/api/v1/auth/login",
        json=payload,
    )

    assert response.status_code == 401

    assert (
        response.json()["error"]["code"]
        == "INVALID_CREDENTIALS"
    )


def test_login_rejects_role_or_permissions_in_payload(env):
    client, _, _ = env

    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "creator@example.com",
            "password": "CreatorPassword#123",
            "role": "admin",
        },
    )

    assert response.status_code == 422


def test_missing_bad_and_wrongly_signed_tokens(env):
    client, _, ids = env

    assert client.get(
        "/api/v1/auth/me"
    ).status_code == 401

    assert client.get(
        "/api/v1/auth/me",
        headers={
            "Authorization": "Bearer nonsense"
        },
    ).status_code == 401

    forged = create_access_token(
        ids["admin"],
        "different-test-secret-with-more-than-32-bytes",
    )

    assert client.get(
        "/api/v1/auth/me",
        headers={
            "Authorization": f"Bearer {forged}"
        },
    ).status_code == 401


def test_jwt_missing_required_claim_and_expiry(env):
    client, _, ids = env

    secret = get_jwt_secret()

    bad = jwt.encode(
        {"sub": ids["admin"]},
        secret,
        algorithm="HS256",
    )

    assert read_access_token(bad, secret) is None

    assert client.get(
        "/api/v1/auth/me",
        headers={
            "Authorization": f"Bearer {bad}"
        },
    ).status_code == 401


def test_disabled_user_login_and_preexisting_token(env):
    client, factory, ids = env

    old_token_header = header(ids, "creator")

    with factory() as session:
        user = session.get(User, ids["creator"])
        user.is_active = False
        session.commit()

    assert client.get(
        "/api/v1/auth/me",
        headers=old_token_header,
    ).status_code == 401

    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "creator@example.com",
            "password": "CreatorPassword#123",
        },
    )

    assert response.status_code == 401


def test_reviewer_cannot_manage_knowledge_and_creator_cannot_approve(env):
    client, _, ids = env

    draft = deepcopy(FLOWPILOT)

    assert client.post(
        "/api/v1/brands/brand_flowpilot/knowledge",
        json=draft,
        headers=header(ids, "reviewer"),
    ).status_code == 403

    assert client.post(
        "/api/v1/brands/brand_flowpilot/knowledge/1/activate",
        headers=header(ids, "reviewer"),
    ).status_code == 403

    response = client.get(
        "/api/v1/auth/me",
        headers=header(ids, "creator"),
    )

    assert (
        response.json()["permissions"]["can_approve"]
        is False
    )


def test_knowledge_requires_auth_and_admin_can_manage(env):
    client, _, ids = env

    assert client.get(
        "/api/v1/brands/brand_flowpilot/knowledge"
    ).status_code == 401

    assert client.post(
        "/api/v1/brands/brand_flowpilot/knowledge",
        json=FLOWPILOT,
    ).status_code == 401

    assert client.post(
        "/api/v1/brands/brand_flowpilot/knowledge/1/activate"
    ).status_code == 401

    assert client.post(
        "/api/v1/brands/brand_flowpilot/knowledge",
        json=FLOWPILOT,
        headers=header(ids, "admin"),
    ).status_code == 201


def test_admin_can_create_list_and_change_permissions(env):
    client, _, ids = env

    admin = header(ids, "admin")

    created = client.post(
        "/api/v1/admin/users",
        headers=admin,
        json={
            "email": "new@example.com",
            "password": "NewAccountPassword#1",
            "role": "reviewer",
        },
    )

    assert created.status_code == 201, created.text

    new_id = created.json()["user_id"]

    assert (
        created.json()["permissions"]["can_approve"]
        is True
    )

    assert client.get(
        "/api/v1/admin/users",
        headers=admin,
    ).status_code == 200

    changed = client.patch(
        f"/api/v1/admin/users/{new_id}/permissions",
        headers=admin,
        json={
            "can_approve": False,
        },
    )

    assert changed.status_code == 200, changed.text

    assert (
        changed.json()["permissions"]["can_review"]
        is True
    )

    assert (
        changed.json()["permissions"]["can_approve"]
        is False
    )


def test_permission_change_applies_to_existing_token(env):
    client, _, ids = env

    old_token_header = header(ids, "creator")

    response = client.patch(
        f"/api/v1/admin/users/{ids['creator']}/permissions",
        json={
            "can_manage_knowledge": True,
        },
        headers=header(ids, "admin"),
    )

    assert response.status_code == 200, response.text

    assert client.post(
        "/api/v1/brands/brand_flowpilot/knowledge",
        json=FLOWPILOT,
        headers=old_token_header,
    ).status_code == 201


def test_nonadmin_cannot_access_user_management(env):
    client, _, ids = env

    assert client.get(
        "/api/v1/admin/users",
        headers=header(ids, "creator"),
    ).status_code == 403

    assert client.patch(
        f"/api/v1/admin/users/{ids['creator']}/permissions",
        json={
            "can_manage_users": True,
        },
        headers=header(ids, "reviewer"),
    ).status_code == 403


def test_admin_cannot_modify_self(env):
    client, _, ids = env

    admin = header(ids, "admin")

    assert client.patch(
        f"/api/v1/admin/users/{ids['admin']}/permissions",
        headers=admin,
        json={
            "can_manage_users": False,
        },
    ).status_code == 403

    assert client.patch(
        f"/api/v1/admin/users/{ids['admin']}/status",
        headers=admin,
        json={
            "is_active": False,
        },
    ).status_code == 403


def test_last_active_admin_cannot_be_disabled_or_deprivileged(env):
    client, _, ids = env

    admin = header(ids, "admin")

    assert client.patch(
        f"/api/v1/admin/users/{ids['admin2']}/status",
        headers=admin,
        json={
            "is_active": False,
        },
    ).status_code == 200

    # The remaining administrator cannot disable themselves.
    assert client.patch(
        f"/api/v1/admin/users/{ids['admin']}/status",
        headers=admin,
        json={
            "is_active": False,
        },
    ).status_code == 403

    # Removing user-management rights from the inactive
    # administrator does not remove the last active manager.
    assert client.patch(
        f"/api/v1/admin/users/{ids['admin2']}/permissions",
        headers=admin,
        json={
            "can_manage_users": False,
        },
    ).status_code == 200


def test_status_change_rejects_existing_token(env):
    client, _, ids = env

    old_token_header = header(ids, "reviewer")

    response = client.patch(
        f"/api/v1/admin/users/{ids['reviewer']}/status",
        json={
            "is_active": False,
        },
        headers=header(ids, "admin"),
    )

    assert response.status_code == 200

    assert client.get(
        "/api/v1/auth/me",
        headers=old_token_header,
    ).status_code == 401


def test_unsupported_fields_cannot_be_edited(env):
    client, _, ids = env

    response = client.patch(
        f"/api/v1/admin/users/{ids['creator']}/permissions",
        json={
            "role": "admin",
        },
        headers=header(ids, "admin"),
    )

    assert response.status_code == 422


def test_login_rate_limit(env):
    client, _, _ = env

    payload = {
        "email": "unknown@example.com",
        "password": "incorrect",
    }

    for _ in range(5):
        assert client.post(
            "/api/v1/auth/login",
            json=payload,
        ).status_code == 401

    blocked = client.post(
        "/api/v1/auth/login",
        json=payload,
    )

    assert blocked.status_code == 429
    assert blocked.headers["retry-after"] == "60"


def test_reusable_approve_dependency(env):
    _, factory, ids = env

    app = FastAPI()

    deps = AuthDependencies(
        factory,
        get_jwt_secret(),
    )

    @app.post("/test/approve")
    def approve(
        _user: User = Depends(
            deps.require("can_approve")
        ),
    ):
        return {
            "approved": True
        }

    client = TestClient(app)

    assert client.post(
        "/test/approve",
        headers=header(ids, "creator"),
    ).status_code == 403

    assert client.post(
        "/test/approve",
        headers=header(ids, "reviewer"),
    ).status_code == 200