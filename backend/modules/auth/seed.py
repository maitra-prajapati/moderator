"""Manual first-administrator bootstrap for a fresh database."""

import getpass
import os

from sqlalchemy import select

from backend.modules.knowledge.database import (
    make_session_factory,
)

from .models import User
from .security import hash_password


def main():

    email = os.getenv(
        "MODERATOR_ADMIN_EMAIL",
        "",
    ).strip().casefold()

    if not email or "@" not in email:
        raise SystemExit(
            "Set MODERATOR_ADMIN_EMAIL "
            "to the intended admin email"
        )

    password = getpass.getpass(
        "New administrator password: "
    )

    hashed = hash_password(password)

    factory = make_session_factory()

    with factory() as session:

        # Only bootstrap a completely fresh user database.
        if session.scalar(
            select(User.id).limit(1)
        ) is not None:
            raise SystemExit(
                "Bootstrap refused: user records already exist"
            )

        account = User(
            email=email,
            password_hash=hashed,
            role="admin",
        )

        session.add(account)
        session.commit()

        print(
            f"Administrator created: {account.email}"
        )


if __name__ == "__main__":
    main()