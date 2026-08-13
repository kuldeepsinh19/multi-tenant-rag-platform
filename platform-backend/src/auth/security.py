from datetime import UTC, datetime, timedelta
from uuid import UUID

from jose import JWTError, jwt
from passlib.context import CryptContext

from src.auth.models import UserRole
from src.auth.schemas import TokenPayload
from src.core.config import get_settings

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    # passlib is untyped, so mypy sees `Any` here — cast explicitly to keep this
    # module's public signatures honest under `strict`.
    return str(_pwd_context.hash(password))


def verify_password(password: str, password_hash: str) -> bool:
    return bool(_pwd_context.verify(password, password_hash))


def create_access_token(user_id: UUID, role: UserRole, business_id: UUID | None) -> str:
    settings = get_settings()
    expire = datetime.now(UTC) + timedelta(minutes=settings.access_token_ttl_minutes)
    payload = {
        "sub": str(user_id),
        "role": role.value,
        "business_id": str(business_id) if business_id else None,
        "exp": expire,
    }
    return str(jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm))


def decode_access_token(token: str) -> TokenPayload:
    """Raises ValueError on any decode/validation failure — callers must fail closed
    (401), never treat a decode error as an anonymous/guest request."""
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError as exc:
        raise ValueError("invalid token") from exc
    return TokenPayload(
        sub=payload["sub"],
        role=UserRole(payload["role"]),
        business_id=UUID(payload["business_id"]) if payload.get("business_id") else None,
    )
