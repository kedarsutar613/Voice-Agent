from datetime import datetime, timedelta, timezone
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pwdlib import PasswordHash
from app.core.config import settings
from app.database.session import db_session
from app.models.entities import User

passwords = PasswordHash.recommended()
bearer = HTTPBearer()


def token(user):
    return jwt.encode(
        {"sub": str(user.id), "exp": datetime.now(timezone.utc) + timedelta(hours=8)},
        settings.jwt_secret,
        algorithm="HS256",
    )


def decode(value):
    try:
        return int(jwt.decode(value, settings.jwt_secret, algorithms=["HS256"])["sub"])
    except (jwt.PyJWTError, ValueError, KeyError):
        raise HTTPException(401, "Invalid or expired session")


def current_user(
    auth: HTTPAuthorizationCredentials = Depends(bearer), db=Depends(db_session)
):
    user = db.get(User, decode(auth.credentials))
    if not user:
        raise HTTPException(401, "User not found")
    return user


def admin(user=Depends(current_user)):
    if user.role != "admin":
        raise HTTPException(403, "Administrator access required")
    return user
