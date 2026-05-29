"""Agency subscription and billing endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, EmailStr
from datetime import datetime

from app.core.database import get_db
from app.models import Agency, APIKey, Subscription, SubscriptionTier, SubscriptionStatus
from app.services.stripe_service import create_customer, create_subscription, TIER_PRICING
from app.services.api_key_service import create_api_key, validate_api_key
import bcrypt

router = APIRouter(prefix="/agency", tags=["agency"])


class AgencySignup(BaseModel):
    """Agency signup request."""
    name: str
    email: EmailStr
    password: str
    tier: SubscriptionTier = SubscriptionTier.BLUEPRINT


class AgencyResponse(BaseModel):
    """Agency response."""
    id: int
    name: str
    email: str
    tier: SubscriptionTier
    client_limit: int
    active_clients: int
    created_at: datetime


class APIKeyResponse(BaseModel):
    """API key response."""
    id: int
    name: str
    created_at: datetime
    last_used_at: datetime | None


class SubscriptionResponse(BaseModel):
    """Subscription response."""
    id: int
    tier: SubscriptionTier
    status: SubscriptionStatus
    amount: float
    current_period_start: datetime
    current_period_end: datetime


def hash_password(password: str) -> str:
    """Hash a password."""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hash: str) -> bool:
    """Verify a password."""
    return bcrypt.checkpw(password.encode(), hash.encode())


@router.post("/signup", response_model=dict)
async def signup_agency(
    data: AgencySignup,
    db: AsyncSession = Depends(get_db),
):
    """Sign up a new agency."""
    # Check if email exists
    result = await db.execute(
        select(Agency).where(Agency.email == data.email)
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )
    
    # Create Stripe customer
    stripe_customer_id = await create_customer(data.email, data.name)
    
    # Create agency
    password_hash = hash_password(data.password)
    agency = Agency(
        name=data.name,
        email=data.email,
        password_hash=password_hash,
        stripe_customer_id=stripe_customer_id,
        subscription_tier=data.tier,
        client_limit=TIER_PRICING[data.tier]["client_limit"] or 999,
    )
    db.add(agency)
    await db.commit()
    await db.refresh(agency)
    
    # Create subscription
    sub_data = await create_subscription(stripe_customer_id, data.tier)
    
    subscription = Subscription(
        agency_id=agency.id,
        stripe_subscription_id=sub_data["subscription_id"],
        tier=data.tier,
        status=SubscriptionStatus.ACTIVE,
        amount=TIER_PRICING[data.tier]["amount"],
        current_period_start=datetime.utcnow(),
        current_period_end=datetime.utcnow(),
    )
    db.add(subscription)
    await db.commit()
    
    return {
        "agency_id": agency.id,
        "client_secret": sub_data["client_secret"],
        "subscription_id": sub_data["subscription_id"],
    }


@router.post("/api-keys", response_model=dict)
async def create_new_api_key(
    name: str,
    agency_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Create a new API key for an agency."""
    # Verify agency exists
    result = await db.execute(
        select(Agency).where(Agency.id == agency_id)
    )
    agency = result.scalar_one_or_none()
    if not agency:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agency not found",
        )
    
    # Create API key
    key = await create_api_key(db, agency_id, name)
    
    return {
        "api_key": key,
        "name": name,
        "warning": "Save this key securely. You won't be able to see it again.",
    }


@router.get("/api-keys/{agency_id}", response_model=list[APIKeyResponse])
async def list_api_keys(
    agency_id: int,
    db: AsyncSession = Depends(get_db),
):
    """List API keys for an agency."""
    result = await db.execute(
        select(APIKey).where(
            APIKey.agency_id == agency_id,
            APIKey.is_active == True,
        )
    )
    keys = result.scalars().all()
    return keys


@router.get("/{agency_id}", response_model=AgencyResponse)
async def get_agency(
    agency_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get agency details."""
    result = await db.execute(
        select(Agency).where(Agency.id == agency_id)
    )
    agency = result.scalar_one_or_none()
    if not agency:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agency not found",
        )
    return agency


@router.get("/{agency_id}/subscription", response_model=SubscriptionResponse)
async def get_subscription(
    agency_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get agency subscription details."""
    result = await db.execute(
        select(Subscription).where(Subscription.agency_id == agency_id)
    )
    subscription = result.scalar_one_or_none()
    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription not found",
        )
    return subscription

