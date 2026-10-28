"""Local-only CLI: grant a known user a known brand (no HTTP bypass)."""
import argparse
from sqlalchemy import select, insert

from backend.modules.auth.models import User
from backend.modules.auth.service import lookup_user
from backend.modules.knowledge.models import Brand
from .m2_bridge import make_auth_port, USER_BRANDS


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("email", help="Existing M2 account email")
    parser.add_argument("brand_id", help="Existing M1 brand ID")
    args = parser.parse_args()
    adapter = make_auth_port()
    with adapter.sessions() as session:
        user = lookup_user(session, args.email)
        if user is None:
            parser.error("Account not found; create it first")
        if session.get(Brand, args.brand_id) is None:
            parser.error("Brand not found; seed M1 first")
        exists = session.execute(
            select(USER_BRANDS).where(
                USER_BRANDS.c.user_id == user.id,
                USER_BRANDS.c.brand_id == args.brand_id,
            )
        ).first()
        if not exists:
            session.execute(insert(USER_BRANDS).values(
                user_id=user.id, brand_id=args.brand_id,
            ))
            session.commit()
        print(f"Granted {args.brand_id} to {user.email}")


if __name__ == "__main__":
    main()
