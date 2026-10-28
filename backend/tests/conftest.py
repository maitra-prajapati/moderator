"""Isolated signing key for automated tests."""

import pytest


@pytest.fixture(autouse=True)
def auth_secret_for_tests(monkeypatch):
    monkeypatch.setenv(
        "MODERATOR_JWT_SECRET",
        "test-only-secret-is-not-for-production-" * 2,
    )