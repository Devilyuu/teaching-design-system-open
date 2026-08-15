from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone
from functools import lru_cache
import hashlib
import hmac
import json
import logging
import os
import secrets

from fastapi import Depends, Header, HTTPException
from sqlmodel import Session, select

from app.db import get_session
from app.models import User, UserMajorLink

PASSWORD_ITERATIONS = 210_000
TOKEN_TTL_HOURS = int(os.getenv("ACCESS_TOKEN_TTL_HOURS", "168"))


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PASSWORD_ITERATIONS)
    return "pbkdf2_sha256${iterations}${salt}${digest}".format(
        iterations=PASSWORD_ITERATIONS,
        salt=base64.urlsafe_b64encode(salt).decode("ascii"),
        digest=base64.urlsafe_b64encode(digest).decode("ascii"),
    )


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        algorithm, iterations_text, salt_text, digest_text = stored_hash.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        salt = base64.urlsafe_b64decode(salt_text.encode("ascii"))
        expected = base64.urlsafe_b64decode(digest_text.encode("ascii"))
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, int(iterations_text))
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(actual, expected)


def create_access_token(user: User) -> str:
    if user.id is None:
        raise ValueError("User must be persisted before creating a token")
    expires_at = datetime.now(timezone.utc) + timedelta(hours=TOKEN_TTL_HOURS)
    payload = {"sub": user.id, "role": user.role, "exp": int(expires_at.timestamp())}
    body = _b64encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signature = _sign(body)
    return f"{body}.{signature}"


def decode_access_token(token: str) -> int:
    try:
        body, signature = token.split(".", 1)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="Invalid token") from exc
    if not hmac.compare_digest(signature, _sign(body)):
        raise HTTPException(status_code=401, detail="Invalid token")
    try:
        payload = json.loads(base64.urlsafe_b64decode(_pad_b64(body)).decode("utf-8"))
    except (ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=401, detail="Invalid token") from exc
    if int(payload.get("exp", 0)) < int(datetime.now(timezone.utc).timestamp()):
        raise HTTPException(status_code=401, detail="Token expired")
    user_id = payload.get("sub")
    if not isinstance(user_id, int):
        raise HTTPException(status_code=401, detail="Invalid token")
    return user_id


def get_current_user(
    authorization: str | None = Header(default=None),
    session: Session = Depends(get_session),
) -> User:
    token = _extract_bearer_token(authorization)
    user_id = decode_access_token(token)
    user = session.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="User is inactive or not found")
    return user


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin permission required")
    return current_user


def user_major_ids(user: User, session: Session) -> list[int]:
    if user.id is None:
        return []
    links = session.exec(select(UserMajorLink).where(UserMajorLink.user_id == user.id)).all()
    return [link.major_id for link in links]


def _extract_bearer_token(authorization: str | None) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    return authorization.removeprefix("Bearer ").strip()


def _sign(body: str) -> str:
    digest = hmac.new(_secret_key(), body.encode("ascii"), hashlib.sha256).digest()
    return _b64encode(digest)


def _secret_key() -> bytes:
    """The key that signs access tokens.

    A default baked into the source is a default every install shares, and this
    repository is public: anyone could mint a token for anyone. So an unset
    ``APP_SECRET_KEY`` falls back to a per-process random key instead. Local
    development and tests keep working; the cost is that tokens stop being valid
    across a restart, and that several worker processes would each sign with a
    different key. Any real deployment must set it -- see ``.env.example``.
    """
    configured = os.getenv("APP_SECRET_KEY", "").strip()
    if configured:
        return configured.encode("utf-8")
    return _ephemeral_secret_key()


@lru_cache(maxsize=1)
def _ephemeral_secret_key() -> bytes:
    logging.getLogger(__name__).warning(
        "APP_SECRET_KEY 未设置，本次启动使用随机签名密钥："
        "重启后所有登录状态失效，且多进程部署会互相不认。生产环境请在 .env 中设置 APP_SECRET_KEY。"
    )
    return secrets.token_bytes(32)


def _b64encode(content: bytes) -> str:
    return base64.urlsafe_b64encode(content).decode("ascii").rstrip("=")


def _pad_b64(content: str) -> bytes:
    return (content + "=" * (-len(content) % 4)).encode("ascii")
