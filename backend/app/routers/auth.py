from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.config import get_settings
from backend.app.db import get_db
from backend.app.models import User
from backend.app.schemas import (AccountDelete, LoginIn, PasswordChange, RegisterIn, TokenOut, UserOut,
                                 UserUpdate)
from backend.app.security import (client_ip, create_access_token, dummy_verify, find_user_by_email,
                                  get_current_user, get_token_payload, hash_password, limiter, revoke,
                                  verify_password)

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(body: RegisterIn, request: Request, db: Session = Depends(get_db)):
    limiter.check(f"register:{client_ip(request)}", get_settings().LOGIN_RATE_LIMIT_PER_MINUTE)
    email = body.email.lower()
    if find_user_by_email(db, email):
        raise HTTPException(status_code=409, detail="An account with this email already exists")
    user = User(email=email, full_name=body.full_name, password_hash=hash_password(body.password))
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="An account with this email already exists") from None
    db.refresh(user)
    return user


@router.post("/login", response_model=TokenOut)
def login(body: LoginIn, request: Request, db: Session = Depends(get_db)):
    s = get_settings()
    limiter.check(f"login:{client_ip(request)}", s.LOGIN_RATE_LIMIT_PER_MINUTE)
    limiter.check(f"login-email:{body.email.lower()}", s.LOGIN_RATE_LIMIT_PER_MINUTE)
    user = find_user_by_email(db, body.email)
    if user is None:
        dummy_verify()  # similar response time whether or not the email exists
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    if not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    token, exp = create_access_token(user.id)
    return TokenOut(access_token=token, expires_at=exp)


@router.post("/logout", status_code=204)
def logout(payload: dict = Depends(get_token_payload), db: Session = Depends(get_db)):
    revoke(db, payload)
    return Response(status_code=204)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user


@router.patch("/me", response_model=UserOut)
def update_me(body: UserUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if body.full_name is not None:
        name = " ".join(body.full_name.split())
        if not name:
            raise HTTPException(status_code=422, detail="Name cannot be blank")
        user.full_name = name
    if body.email_alerts_enabled is not None:
        user.email_alerts_enabled = body.email_alerts_enabled
    db.commit()
    db.refresh(user)
    return user


@router.post("/change-password", status_code=204)
def change_password(body: PasswordChange, payload: dict = Depends(get_token_payload),
                    user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    user.password_hash = hash_password(body.new_password)
    db.commit()
    revoke(db, payload)  # force re-login with the new password
    return Response(status_code=204)


@router.delete("/me", status_code=204)
def delete_account(body: AccountDelete, payload: dict = Depends(get_token_payload),
                   user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Permanently delete the account and all its predictions/alerts (privacy right to erasure)."""
    if not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=400, detail="Password is incorrect")
    revoke(db, payload)
    db.delete(user)
    db.commit()
    return Response(status_code=204)
