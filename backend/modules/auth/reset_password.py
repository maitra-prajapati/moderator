import getpass

from sqlalchemy import select

from backend.modules.auth.models import User
from backend.modules.auth.security import hash_password
from backend.modules.knowledge.database import make_session_factory


def main():
    print("=== MODERATOR PASSWORD RESET ===")

    email = input("Enter account email: ").strip().casefold()

    session_factory = make_session_factory()

    with session_factory() as session:
        user = session.scalar(
            select(User).where(User.email == email)
        )

        if user is None:
            print("Account not found.")
            return

        print(f"Account found: {user.email}")

        new_password = getpass.getpass("New password: ")
        confirm_password = getpass.getpass("Confirm password: ")

        if new_password != confirm_password:
            print("Passwords do not match.")
            return

        try:
            new_hash = hash_password(new_password)
        except (ValueError, TypeError) as exc:
            print(f"Invalid password: {exc}")
            return

        user.password_hash = new_hash

        session.commit()

        print("Password reset successfully!")


if __name__ == "__main__":
    main()