"""API key generation and validation service."""

import secrets
import hashlib
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models import APIKey, Agency


def generate_api_key() -> str:
    """Generate a secure API key."""
    return f"sk_{secrets.token_urlsafe(32)}"


def hash_api_key(key: str) -> str:
    """Hash an API key for storage."""
    return hashlib.sha256(key.encode()).hexdigest()


async def create_api_key(
    db: AsyncSession,
    agency_id: int,
    name: str,
) -> str:
    """Create a new API key for an agency."""
    key = generate_api_key()
    key_hash = hash_api_key(key)
    
    api_key = APIKey(
        agency_id=agency_id,
        key=key_hash,
        name=name,
    )
    db.add(api_key)
    await db.commit()
    
    # Return the unhashed key (only shown once)
    return key


async def validate_api_key(db: AsyncSession, key: str) -> dict:
    """Validate an API key and return agency info."""
    key_hash = hash_api_key(key)
    
    result = await db.execute(
        select(APIKey).where(
            APIKey.key == key_hash,
            APIKey.is_active == True,
        )
    )
    api_key = result.scalar_one_or_none()
    
    if not api_key:
        return None
    
    # Update last_used_at
    api_key.last_used_at = datetime.utcnow()
    await db.commit()
    
    # Get agency info
    result = await db.execute(
        select(Agency).where(Agency.id == api_key.agency_id)
    )
    agency = result.scalar_one_or_none()
    
    if not agency or not agency.is_active:
        return None
    
    return {
        "agency_id": agency.id,
        "agency_name": agency.name,
        "tier": agency.subscription_tier,
        "client_limit": agency.client_limit,
        "active_clients": agency.active_clients,
    }


async def revoke_api_key(db: AsyncSession, agency_id: int, key_id: int) -> bool:
    """Revoke an API key."""
    result = await db.execute(
        select(APIKey).where(
            APIKey.id == key_id,
            APIKey.agency_id == agency_id,
        )
    )
    api_key = result.scalar_one_or_none()
    
    if not api_key:
        return False
    
    api_key.is_active = False
    await db.commit()
    return True

