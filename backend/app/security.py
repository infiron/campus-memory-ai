import base64
import hashlib
import hmac
import json
import time
from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session
from .config import settings
from .database import get_db
from .models import User


def hash_password(password: str, salt: bytes | None = None) -> str:
    salt = salt or __import__('secrets').token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 240_000)
    return base64.urlsafe_b64encode(salt).decode().rstrip("=") + "$" + base64.urlsafe_b64encode(digest).decode().rstrip("=")


def verify_password(password: str, encoded: str) -> bool:
    try:
        salt_s, digest_s = encoded.split("$", 1)
        pad = lambda s: s + "=" * (-len(s) % 4)
        salt, expected = base64.urlsafe_b64decode(pad(salt_s)), base64.urlsafe_b64decode(pad(digest_s))
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 240_000)
        return hmac.compare_digest(actual, expected)
    except Exception:
        return False


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def issue_token(user: User) -> str:
    payload = {"sub": user.id, "exp": int(time.time()) + settings.token_ttl_hours * 3600}
    body = _b64(json.dumps(payload, separators=(",", ":")).encode())
    signature = _b64(hmac.new(settings.secret_key.encode(), body.encode(), hashlib.sha256).digest())
    return body + "." + signature


def decode_token(token: str) -> dict:
    try:
        body, signature = token.split(".", 1)
        expected = _b64(hmac.new(settings.secret_key.encode(), body.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(signature, expected):
            raise ValueError("signature")
        pad = lambda s: s + "=" * (-len(s) % 4)
        payload = json.loads(base64.urlsafe_b64decode(pad(body)))
        if int(payload.get("exp", 0)) < int(time.time()):
            raise ValueError("expired")
        return payload
    except Exception as exc:
        raise HTTPException(status_code=401, detail="登录已失效，请重新登录") from exc


def get_current_user(authorization: str | None = Header(default=None), db: Session = Depends(get_db)) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="此操作需要登录")
    payload = decode_token(authorization[7:])
    user = db.get(User, int(payload["sub"]))
    if not user or not user.active:
        raise HTTPException(status_code=401, detail="用户不存在或已停用")
    return user


def require_roles(*roles: str):
    def dependency(user: User = Depends(get_current_user)) -> User:
        if not set(roles).intersection(user.roles or []):
            raise HTTPException(status_code=403, detail=f"需要以下角色之一：{'、'.join(roles)}")
        return user
    return dependency


def serialize_user(user: User) -> dict:
    return {"id": user.id, "username": user.username, "display_name": user.display_name, "roles": user.roles, "active": user.active}
