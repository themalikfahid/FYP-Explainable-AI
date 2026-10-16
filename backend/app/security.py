"""Password hashing (bcrypt), JWT issue/verify, auth dependency and a small rate limiter."""
from __future__ import annotations

import threading
import time
import uuid
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from backend.app.config import get_settings
from backend.app.db import get_db
from backend.app.models import RevokedToken, User

ALGORITHM = "HS256"
BCRYPT_ROUNDS = 12
_bearer = HTTPBearer(auto_error=False)


# ------------------------------------------------------------- passwords
def hash_password(password: str) -> str:
    # bcrypt only uses the first 72 bytes; the API caps passwords at 72 bytes (schemas.py)
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=BCRYPT_ROUNDS)).decode("ascii")


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("ascii"))
    except ValueError:
        return False


# a real hash used to equalise timing when the email does not exist
_DUMMY_HASH = bcrypt.hashpw(b"timing-equaliser", bcrypt.gensalt(rounds=BCRYPT_ROUNDS)).decode("ascii")


def dummy_verify() -> None:
    verify_password("not-the-password", _DUMMY_HASH)


# ------------------------------------------------------------------ JWT
def create_access_token(user_id: int) -> tuple[str, datetime]:
    s = get_settings()
    now = datetime.now(timezone.utc)
    exp = now + timedelta(minutes=s.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": str(user_id), "iat": int(now.timestamp()), "exp": int(exp.timestamp()),
               "jti": uuid.uuid4().hex, "type": "access"}
    return jwt.encode(payload, s.SECRET_KEY, algorithm=ALGORITHM), exp


def decode_token(token: str) -> dict:
    s = get_settings()
    return jwt.decode(token, s.SECRET_KEY, algorithms=[ALGORITHM],
                      options={"require": ["exp", "iat", "sub", "jti"]})


def _unauthorized(detail: str = "Not authenticated") -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail,
                         headers={"WWW-Authenticate": "Bearer"})


def get_token_payload(creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
                      db: Session = Depends(get_db)) -> dict:
    if creds is None or creds.scheme.lower() != "bearer":
        raise _unauthorized()
    try:
        payload = decode_token(creds.credentials)
    except jwt.ExpiredSignatureError:
        raise _unauthorized("Session expired, please log in again") from None
    except jwt.PyJWTError:
        raise _unauthorized("Invalid token") from None
    if payload.get("type") != "access":
        raise _unauthorized("Invalid token")
    if db.get(RevokedToken, payload["jti"]) is not None:
        raise _unauthorized("Session has been logged out")
    return payload


def get_current_user(payload: dict = Depends(get_token_payload), db: Session = Depends(get_db)) -> User:
    user = db.get(User, int(payload["sub"]))
    if user is None:
        raise _unauthorized("Account no longer exists")
    return user


def revoke(db: Session, payload: dict) -> None:
    exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
    if db.get(RevokedToken, payload["jti"]) is None:
        db.add(RevokedToken(jti=payload["jti"], expires_at=exp))
    # housekeeping: drop denylist rows whose tokens have expired anyway
    db.execute(delete(RevokedToken).where(RevokedToken.expires_at < datetime.now(timezone.utc)))
    db.commit()


def find_user_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == email.lower()))


# ------------------------------------------------------------ rate limit
class RateLimiter:
    """In-memory sliding-window limiter (per process). Adequate for a local
    single-process deployment; use a shared store (e.g. Redis) if scaled out."""

    def __init__(self):
        self._hits: dict[str, deque] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str, limit: int, window_s: float = 60.0) -> None:
        now = time.monotonic()
        with self._lock:
            q = self._hits[key]
            while q and now - q[0] > window_s:
                q.popleft()
            if len(q) >= limit:
                retry = int(window_s - (now - q[0])) + 1
                raise HTTPException(status_code=429, detail="Too many requests, please wait and try again.",
                                    headers={"Retry-After": str(retry)})
            q.append(now)

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


limiter = RateLimiter()


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"
