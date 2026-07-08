import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

_pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")


# --- Password hashing ---
def hash_password(password: str) -> str:
    return _pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _pwd_context.verify(password, password_hash)
    except Exception:
        return False


# --- JWT session tokens ---
def create_access_token(subject: str, extra: dict | None = None) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_expire_minutes),
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError:
        return None


# --- Signed OAuth state (CSRF + PKCE carrier) ---
_OAUTH_STATE_PURPOSE = "oauth_state"


def sign_oauth_state(payload: dict) -> str:
    """Sign a short-lived OAuth state blob (provider, nonce, PKCE verifier)."""
    now = datetime.now(timezone.utc)
    body = {
        **payload,
        "purpose": _OAUTH_STATE_PURPOSE,
        "iat": now,
        "exp": now + timedelta(seconds=settings.oauth_state_ttl_seconds),
    }
    return jwt.encode(body, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def verify_oauth_state(token: str) -> dict | None:
    try:
        claims = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError:
        return None
    if claims.get("purpose") != _OAUTH_STATE_PURPOSE:
        return None
    return claims


# --- Opaque tokens (API tokens, share tokens) ---
def generate_token(prefix: str) -> str:
    """Return a plaintext opaque token like ``pd_live_<random>``."""
    return f"{prefix}{secrets.token_urlsafe(32)}"


def hash_token(plaintext: str) -> str:
    """HMAC-SHA256 with the server pepper. Only the hash is stored."""
    return hmac.new(
        settings.token_pepper.encode(), plaintext.encode(), hashlib.sha256
    ).hexdigest()


def verify_token_hash(plaintext: str, token_hash: str) -> bool:
    return hmac.compare_digest(hash_token(plaintext), token_hash)
