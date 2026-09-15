"""Creates a small set of demo users for local development and for
demonstrating per-service access control end to end.

Not run automatically by ingest_corpus.py or CI — seeding is a demo/dev
convenience, a deliberate, explicit step, not something a real deployment
would want auto-run against its actual user table.

The passwords below are dev-only placeholders, committed in the open on
purpose, the same convention already used for Settings.postgres_password:
a non-secret, clearly-local default, never meant for a real deployment.

Usage: PYTHONPATH=. uv run python -m app.auth.seed_users
"""

from sqlalchemy import select

from app.auth.service import hash_password
from app.db.models import User
from app.db.session import SessionLocal

DEMO_USERS = [
    {
        "username": "payments-engineer",
        "password": "demo-payments-pw",
        "allowed_services": ["payments"],
    },
    {
        "username": "checkout-engineer",
        "password": "demo-checkout-pw",
        "allowed_services": ["checkout"],
    },
    {
        # None (SQL NULL) means unrestricted, mirroring Document.service's own
        # NULL-means-universal convention — see app/db/models.py's User.allowed_services.
        "username": "admin",
        "password": "demo-admin-pw",
        "allowed_services": None,
    },
]


def seed_users() -> None:
    session = SessionLocal()
    try:
        for spec in DEMO_USERS:
            existing = session.execute(
                select(User).where(User.username == spec["username"])
            ).scalar_one_or_none()
            if existing is not None:
                print(f"skipped (already exists): {spec['username']}")
                continue

            user = User(
                username=spec["username"],
                hashed_password=hash_password(spec["password"]),
                allowed_services=spec["allowed_services"],
            )
            session.add(user)
            session.commit()
            print(f"created: {spec['username']} (allowed_services={spec['allowed_services']})")
    finally:
        session.close()


if __name__ == "__main__":
    seed_users()
