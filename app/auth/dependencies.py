from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jwt import PyJWTError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.service import decode_access_token
from app.db.models import User
from app.db.session import get_db

# tokenUrl only tells FastAPI's auto-generated docs where to send the login
# request (Swagger UI's "Authorize" button), it doesn't affect runtime token
# validation, which happens entirely below via decode_access_token.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def get_current_user(
    token: str = Depends(oauth2_scheme), session: Session = Depends(get_db)
) -> User:
    # Identical error for "malformed/expired token" and "token valid but the
    # user no longer exists" — distinguishing them would leak whether a given
    # username currently exists to a caller holding a stale or forged token.
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        username = decode_access_token(token)
    except PyJWTError:
        raise credentials_exception from None

    user = session.execute(select(User).where(User.username == username)).scalar_one_or_none()
    if user is None:
        raise credentials_exception
    return user
