"""API key authentication middleware."""
from fastapi import HTTPException, Security, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from passlib.context import CryptContext
import secrets

from ..database import get_db
from ..models import APIKey

security = HTTPBearer()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_api_key(key: str) -> str:
    """Hash an API key for storage."""
    return pwd_context.hash(key)


def verify_api_key(plain_key: str, hashed_key: str) -> bool:
    """Verify an API key against its hash."""
    return pwd_context.verify(plain_key, hashed_key)


def generate_api_key() -> str:
    """Generate a secure random API key."""
    return secrets.token_urlsafe(32)


async def get_current_api_key(
    credentials: HTTPAuthorizationCredentials = Security(security),
    db: Session = Depends(get_db)
) -> APIKey:
    """Validate API key and return the key object."""
    token = credentials.credentials

    # Query all active API keys
    api_keys = db.query(APIKey).filter(APIKey.active == True).all()

    for api_key in api_keys:
        if verify_api_key(token, api_key.key_hash):
            return api_key

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired API key"
    )


async def require_admin(api_key: APIKey = Depends(get_current_api_key)) -> APIKey:
    """Require admin API key."""
    if api_key.key_type != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return api_key


async def require_listener(api_key: APIKey = Depends(get_current_api_key)) -> APIKey:
    """Require listener API key."""
    if api_key.key_type not in ["listener", "admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Listener or admin access required"
        )
    return api_key


async def require_visualization(api_key: APIKey = Depends(get_current_api_key)) -> APIKey:
    """Require visualization API key."""
    if api_key.key_type not in ["visualization", "admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Visualization or admin access required"
        )
    return api_key
