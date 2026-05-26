"""Gumroad API integration - webhook receiver and sales tracking."""

import hmac
import hashlib
import json
import logging
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.config import settings
from app.core.database import get_db
from app.models import Order, Customer, Product, OrderStatus

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/gumroad", tags=["gumroad"])


def verify_gumroad_signature(signature: str, body: str) -> bool:
    """Verify Gumroad webhook signature."""
    try:
        expected_signature = hmac.new(
            settings.GUMROAD_WEBHOOK_SECRET.encode(),
            body.encode(),
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(signature, expected_signature)
    except Exception as e:
        logger.error(f"Signature verification error: {e}")
        return False


@router.post("/webhook/sale")
async def gumroad_webhook_sale(request: Request, db: AsyncSession = Depends(get_db)):
    """Receive Gumroad sale webhook."""
    try:
        # Get raw body for signature verification
        body = await request.body()
        signature = request.headers.get("x-gumroad-signature")

        if not signature:
            logger.warning("Missing signature header")
            raise HTTPException(status_code=400, detail="Missing signature")

        if not verify_gumroad_signature(signature, body.decode()):
            logger.warning("Invalid signature")
            raise HTTPException(status_code=401, detail="Invalid signature")

        data = await request.json()
        payload = data.get("data", {})

        # Extract order data
        gumroad_customer_id = payload.get("customer_id")
        gumroad_order_id = payload.get("id")
        email = payload.get("email")
        product_id = payload.get("product_id")
        amount = float(payload.get("price", 0))
        license_key = payload.get("license_key")

        # Check for duplicate
        existing = await db.execute(
            select(Order).filter(Order.gumroad_order_id == gumroad_order_id)
        )
        if existing.scalar_one_or_none():
            logger.info(f"Duplicate order: {gumroad_order_id}")
            return {"status": "duplicate", "order_id": gumroad_order_id}

        # Get or create customer
        customer = await db.execute(
            select(Customer).filter(Customer.email == email)
        )
        customer = customer.scalar_one_or_none()

        if not customer:
            customer = Customer(
                email=email,
                gumroad_customer_id=gumroad_customer_id,
                first_name=payload.get("name", "").split()[0] if payload.get("name") else None,
            )
            db.add(customer)
            await db.flush()
        else:
            customer.gumroad_customer_id = gumroad_customer_id

        # Get product
        product = await db.execute(
            select(Product).filter(Product.gumroad_id == product_id)
        )
        product = product.scalar_one_or_none()

        if not product:
            logger.warning(f"Product not found: {product_id}")
            # Create a default product
            product = Product(name=f"Product {product_id}", price=amount, gumroad_id=product_id)
            db.add(product)
            await db.flush()

        # Create order
        order = Order(
            customer_id=customer.id,
            product_id=product.id,
            gumroad_order_id=gumroad_order_id,
            amount=amount,
            license_key=license_key,
            status=OrderStatus.COMPLETED,
        )
        db.add(order)

        # Update customer totals
        customer.total_spent = (customer.total_spent or 0) + amount
        customer.purchase_count = (customer.purchase_count or 0) + 1

        await db.commit()
        logger.info(f"Order created: {gumroad_order_id} for {email}")

        return {
            "status": "success",
            "order_id": gumroad_order_id,
            "customer_id": customer.id,
        }

    except Exception as e:
        logger.error(f"Webhook error: {e}", exc_info=True)
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sales/summary")
async def get_sales_summary(db: AsyncSession = Depends(get_db)):
    """Get sales summary."""
    try:
        # Total revenue
        total_revenue = await db.execute(
            select(func.sum(Order.amount)).filter(Order.status == OrderStatus.COMPLETED)
        )
        total_revenue = total_revenue.scalar() or 0.0

        # Total orders
        total_orders = await db.execute(
            select(func.count(Order.id)).filter(Order.status == OrderStatus.COMPLETED)
        )
        total_orders = total_orders.scalar() or 0

        # Total customers
        total_customers = await db.execute(select(func.count(Customer.id)))
        total_customers = total_customers.scalar() or 0

        # AOV
        aov = total_revenue / total_orders if total_orders > 0 else 0

        return {
            "total_revenue": float(total_revenue),
            "total_orders": total_orders,
            "total_customers": total_customers,
            "average_order_value": float(aov),
        }
    except Exception as e:
        logger.error(f"Error fetching sales summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/customers/count")
async def get_customer_count(db: AsyncSession = Depends(get_db)):
    """Get total customer count."""
    try:
        count = await db.execute(select(func.count(Customer.id)))
        count = count.scalar() or 0
        return {"total_customers": count}
    except Exception as e:
        logger.error(f"Error fetching customer count: {e}")
        raise HTTPException(status_code=500, detail=str(e))
