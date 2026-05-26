"""Product management API."""

import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from app.core.database import get_db
from app.models import Product, ProductTier

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/products", tags=["products"])


class ProductCreate(BaseModel):
    """Product creation schema."""
    name: str
    description: str = None
    price: float
    tier: ProductTier = ProductTier.MAIN
    gumroad_id: str = None


class ProductUpdate(BaseModel):
    """Product update schema."""
    name: str = None
    description: str = None
    price: float = None
    tier: ProductTier = None


class ProductResponse(BaseModel):
    """Product response schema."""
    id: int
    name: str
    description: str
    price: float
    tier: str
    gumroad_id: str
    is_active: bool

    class Config:
        from_attributes = True


@router.post("/", response_model=ProductResponse)
async def create_product(product: ProductCreate, db: AsyncSession = Depends(get_db)):
    """Create a new product."""
    try:
        db_product = Product(**product.dict())
        db.add(db_product)
        await db.commit()
        await db.refresh(db_product)
        logger.info(f"Product created: {db_product.name}")
        return db_product
    except Exception as e:
        logger.error(f"Error creating product: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/", response_model=list[ProductResponse])
async def list_products(db: AsyncSession = Depends(get_db), skip: int = 0, limit: int = 100):
    """List all products."""
    try:
        result = await db.execute(
            select(Product).filter(Product.is_active == True).offset(skip).limit(limit)
        )
        products = result.scalars().all()
        return products
    except Exception as e:
        logger.error(f"Error listing products: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{product_id}", response_model=ProductResponse)
async def get_product(product_id: int, db: AsyncSession = Depends(get_db)):
    """Get a specific product."""
    try:
        result = await db.execute(select(Product).filter(Product.id == product_id))
        product = result.scalar_one_or_none()
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
        return product
    except Exception as e:
        logger.error(f"Error fetching product: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{product_id}", response_model=ProductResponse)
async def update_product(
    product_id: int, product_update: ProductUpdate, db: AsyncSession = Depends(get_db)
):
    """Update a product."""
    try:
        result = await db.execute(select(Product).filter(Product.id == product_id))
        product = result.scalar_one_or_none()
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")

        update_data = product_update.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(product, field, value)

        db.add(product)
        await db.commit()
        await db.refresh(product)
        logger.info(f"Product updated: {product.name}")
        return product
    except Exception as e:
        logger.error(f"Error updating product: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{product_id}")
async def delete_product(product_id: int, db: AsyncSession = Depends(get_db)):
    """Delete a product (soft delete)."""
    try:
        result = await db.execute(select(Product).filter(Product.id == product_id))
        product = result.scalar_one_or_none()
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")

        product.is_active = False
        db.add(product)
        await db.commit()
        logger.info(f"Product deleted: {product.name}")
        return {"status": "deleted", "product_id": product_id}
    except Exception as e:
        logger.error(f"Error deleting product: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
