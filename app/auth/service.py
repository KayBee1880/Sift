"""Authentication: password hashing and JWT issuance/verification.

Real, working auth, not a placeholder: bcrypt password hashing and signed
JWTs. Deliberately minimal dependencies — `bcrypt` and `PyJWT` directly,
rather than a heavier auth framework — since this project's scope needs
hashing and sign/verify, nothing else. Same reasoning already applied to
`app/generation/service.py`'s use of raw `httpx` over the `groq` SDK for a
single endpoint: a focused library over a does-everything one when the
project's actual surface area doesn't need the extra abstraction.
"""

from datetime import UTC, datetime, timedelta

import bcrypt
import jwt

from app.config import get_settings

JWT_ALGORITHM = "HS256"

# Short enough that a leaked/stale token doesn't stay valid indefinitely, long
# enough that a demo session doesn't need to re-authenticate mid-use. Not
# empirically tuned against real usage patterns, same honesty standard already
# applied to other unverified placeholder constants in this project (e.g.
# MIN_RETRIEVAL_SIMILARITY).
JWT_EXPIRY_MINUTES = 60


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), hashed_password.encode("utf-8"))


def create_access_token(username: str) -> str:
    settings = get_settings()
    expire = datetime.now(UTC) + timedelta(minutes=JWT_EXPIRY_MINUTES)
    payload = {"sub": username, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> str:
    """Returns the username encoded in a valid, unexpired token.

    Raises jwt.PyJWTError (or a subclass, e.g. ExpiredSignatureError,
    InvalidSignatureError) for anything invalid, expired, or malformed. This
    function stays a pure decode/verify operation; turning a decode failure
    into an HTTP 401 is the caller's job (app.auth.dependencies.get_current_user),
    not this module's — keeps this module usable outside an HTTP context too
    (e.g. directly in tests or scripts) without dragging in FastAPI concerns.
    """
    settings = get_settings()
    payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[JWT_ALGORITHM])
    return payload["sub"]
