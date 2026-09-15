from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.service import create_access_token, verify_password
from app.db.models import User
from app.db.session import get_db
from app.schemas.auth import TokenResponse

router = APIRouter()


@router.post("/auth/login", response_model=TokenResponse)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(), session: Session = Depends(get_db)
) -> TokenResponse:
    user = session.execute(
        select(User).where(User.username == form_data.username)
    ).scalar_one_or_none()

    # Identical error whether the username doesn't exist or the password is
    # wrong — distinguishing them would let a caller enumerate valid usernames
    # by observing which error they get back.
    if user is None or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect username or password"
        )

    access_token = create_access_token(user.username)
    return TokenResponse(access_token=access_token, token_type="bearer")
