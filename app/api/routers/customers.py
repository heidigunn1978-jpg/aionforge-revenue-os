"""Customer management API."""

import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pydantic import BaseModel, EmailStr

from app.core.database import get_db
from app.models import Customer, Order

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/customers", tags=["customers"])


class CustomerCreate(BaseModel):
    """Customer creation schema."""
    email: EmailStr
    first_name: str = None
    last_name: str = None
    avatar_url: str = None


class CustomerUpdate(BaseModel):
    """Customer update schema."""
    first_name: str = None
    last_name: str = None
    avatar_url: str = None


class OrderSummary(BaseModel):
    """Order summary schema."""
    id: int
    amount: float
    created_at: str

    class Config:
        from_attributes = True


class CustomerResponse(BaseModel):
    """Customer response schema."""
    id: int
    email: str
    first_name: str
    last_name: str
    total_spent: float
    purchase_count: int
    created_at: str

    class Config:
        from_attributes = True


class CustomerDetailResponse(CustomerResponse):
    """Customer with orders response schema."""
    orders: list[OrderSummary]


@router.post("/", response_model=CustomerResponse)
async def create_customer(customer: CustomerCreate, db: AsyncSession = Depends(get_db)):
    """Create a new customer."""
    try:
        # Check if email already exists
        result = await db.execute(select(Customer).filter(Customer.email == customer.email))
        if result.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Customer with this email already exists")

        db_customer = Customer(**customer.dict())
        db.add(db_customer)
        await db.commit()
        await db.refresh(db_customer)
        logger.info(f"Customer created: {customer.email}")
        return db_customer
    except Exception as e:
        logger.error(f"Error creating customer: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/", response_model=list[CustomerResponse])
async def list_customers(db: AsyncSession = Depends(get_db), skip: int = 0, limit: int = 100):
    """List all customers."""
    try:
        result = await db.execute(select(Customer).offset(skip).limit(limit))
        customers = result.scalars().all()
        return customers
    except Exception as e:
        logger.error(f"Error listing customers: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{customer_id}", response_model=CustomerDetailResponse)
async def get_customer(customer_id: int, db: AsyncSession = Depends(get_db)):
    """Get a specific customer with orders."""
    try:
        result = await db.execute(select(Customer).filter(Customer.id == customer_id))
        customer = result.scalar_one_or_none()
        if not customer:
            raise HTTPException(status_code=404, detail="Customer not found")
        return customer
    except Exception as e:
        logger.error(f"Error fetching customer: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/search/{email}")
async def search_customer_by_email(email: str, db: AsyncSession = Depends(get_db)):
    """Search customer by email."""
    try:
        result = await db.execute(select(Customer).filter(Customer.email == email))
        customer = result.scalar_one_or_none()
        if not customer:
            raise HTTPException(status_code=404, detail="Customer not found")
        return customer
    except Exception as e:
        logger.error(f"Error searching customer: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{customer_id}", response_model=CustomerResponse)
async def update_customer(
    customer_id: int, customer_update: CustomerUpdate, db: AsyncSession = Depends(get_db)
):
    """Update a customer."""
    try:
        result = await db.execute(select(Customer).filter(Customer.id == customer_id))
        customer = result.scalar_one_or_none()
        if not customer:
            raise HTTPException(status_code=404, detail="Customer not found")

        update_data = customer_update.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(customer, field, value)

        db.add(customer)
        await db.commit()
        await db.refresh(customer)
        logger.info(f"Customer updated: {customer.email}")
        return customer
    except Exception as e:
        logger.error(f"Error updating customer: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{customer_id}/orders", response_model=list[OrderSummary])
async def get_customer_orders(customer_id: int, db: AsyncSession = Depends(get_db)):
    """Get all orders for a customer."""
    try:
        result = await db.execute(select(Order).filter(Order.customer_id == customer_id))
        orders = result.scalars().all()
        return orders
    except Exception as e:
        logger.error(f"Error fetching customer orders: {e}")
        raise HTTPException(status_code=500, detail=str(e))
