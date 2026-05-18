import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from typing import Any

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from services import db_service


security = HTTPBearer(auto_error=False)


def _secret_key() -> str:
    return os.getenv("AUTH_SECRET_KEY") or "dev-only-auth-secret"


def _token_ttl_seconds() -> int:
    return int(os.getenv("AUTH_TOKEN_TTL_SECONDS", "86400"))


def _encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def _sign(payload: str) -> str:
    signature = hmac.new(_secret_key().encode("utf-8"), payload.encode("ascii"), hashlib.sha256).digest()
    return _encode(signature)


def hash_password(password: str, salt: str | None = None) -> str:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("ascii"), 200_000)
    return f"pbkdf2_sha256${salt}${digest.hex()}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        algorithm, salt, expected = password_hash.split("$", 2)
    except ValueError:
        return False
    if algorithm != "pbkdf2_sha256":
        return False
    return hmac.compare_digest(hash_password(password, salt), password_hash)


def create_access_token(username: str, user_id: int | None = None) -> str:
    payload = {
        "sub": username,
        "exp": int(time.time()) + _token_ttl_seconds(),
    }
    if user_id is not None:
        payload["uid"] = user_id
    encoded_payload = _encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    return f"{encoded_payload}.{_sign(encoded_payload)}"


def verify_access_token(token: str) -> dict[str, Any]:
    try:
        encoded_payload, signature = token.split(".", 1)
        expected_signature = _sign(encoded_payload)
        if not hmac.compare_digest(signature, expected_signature):
            raise ValueError("invalid signature")
        payload = json.loads(_decode(encoded_payload))
    except (ValueError, json.JSONDecodeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
        )

    if int(payload.get("exp", 0)) < int(time.time()):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token has expired",
        )

    return payload


def authenticate_user(username: str, password: str) -> bool:
    user = db_service.get_user_by_username(username)
    if user:
        return verify_password(password, user["password_hash"])
    return False


def authenticate_user_record(username: str, password: str) -> dict[str, Any] | None:
    user = db_service.get_user_by_username(username)
    if user and verify_password(password, user["password_hash"]):
        return {"id": user["id"], "username": user["username"]}
    return None


def register_user(username: str, password: str) -> dict[str, Any]:
    if db_service.get_user_by_username(username):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username is already registered")
    return db_service.create_user(username, hash_password(password))


def require_auth(credentials: HTTPAuthorizationCredentials | None = Depends(security)) -> dict[str, Any]:
    if not credentials or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    payload = verify_access_token(credentials.credentials)
    user_id = payload.get("uid")
    if not user_id or not db_service.get_user_by_id(int(user_id)):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication user no longer exists",
        )
    return payload
