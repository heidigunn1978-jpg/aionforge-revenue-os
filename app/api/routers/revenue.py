"""Revenue analytics and dashboard API."""

import logging
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from pydantic import BaseModel

from app.core.database import get_db
from app.models import Order, Customer, Product, OrderStatus

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/revenue", tags=["revenue"])


class RevenueSummary(BaseModel):
    """Revenue summary response schema."""
    total_revenue: float
    total_orders: int
    total_customers: int
    average_order_value: float
    period: str = "all_time"


class DailyRevenue(BaseModel):
    """Daily revenue data."""
    date: str
    revenue: float
    orders: int
    customers: int


class ProductRevenue(BaseModel):
    """Product-specific revenue."""
    product_id: int
    product_name: str
    revenue: float
    orders: int
    average_price: float


@router.get("/summary", response_model=RevenueSummary)
async def get_revenue_summary(days: int = None, db: AsyncSession = Depends(get_db)):
    """Get revenue summary."""
    try:
        query = select(
            func.sum(Order.amount),
            func.count(Order.id),
            func.count(func.distinct(Order.customer_id)),
        ).filter(Order.status == OrderStatus.COMPLETED)

        if days:
            cutoff = datetime.utcnow() - timedelta(days=days)
            query = query.filter(Order.created_at >= cutoff)

        result = await db.execute(query)
        total_revenue, total_orders, total_customers = result.one()

        total_revenue = float(total_revenue or 0)
        total_orders = int(total_orders or 0)
        total_customers = int(total_customers or 0)
        aov = total_revenue / total_orders if total_orders > 0 else 0

        return {
            "total_revenue": total_revenue,
            "total_orders": total_orders,
            "total_customers": total_customers,
            "average_order_value": aov,
            "period": f"last_{days}_days" if days else "all_time",
        }
    except Exception as e:
        logger.error(f"Error fetching revenue summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/daily", response_model=list[DailyRevenue])
async def get_daily_revenue(days: int = 30, db: AsyncSession = Depends(get_db)):
    """Get daily revenue breakdown."""
    try:
        cutoff = datetime.utcnow() - timedelta(days=days)
        result = await db.execute(
            select(
                func.date(Order.created_at),
                func.sum(Order.amount),
                func.count(Order.id),
                func.count(func.distinct(Order.customer_id)),
            )
            .filter(and_(Order.status == OrderStatus.COMPLETED, Order.created_at >= cutoff))
            .group_by(func.date(Order.created_at))
            .order_by(func.date(Order.created_at).desc())
        )

        rows = result.all()
        return [
            {
                "date": str(row[0]),
                "revenue": float(row[1] or 0),
                "orders": int(row[2] or 0),
                "customers": int(row[3] or 0),
            }
            for row in rows
        ]
    except Exception as e:
        logger.error(f"Error fetching daily revenue: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/by-product", response_model=list[ProductRevenue])
async def get_revenue_by_product(db: AsyncSession = Depends(get_db)):
    """Get revenue breakdown by product."""
    try:
        result = await db.execute(
            select(
                Product.id,
                Product.name,
                func.sum(Order.amount),
                func.count(Order.id),
                func.avg(Order.amount),
            )
            .join(Order, Order.product_id == Product.id)
            .filter(Order.status == OrderStatus.COMPLETED)
            .group_by(Product.id, Product.name)
        )

        rows = result.all()
        return [
            {
                "product_id": row[0],
                "product_name": row[1],
                "revenue": float(row[2] or 0),
                "orders": int(row[3] or 0),
                "average_price": float(row[4] or 0),
            }
            for row in rows
        ]
    except Exception as e:
        logger.error(f"Error fetching product revenue: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cohort")
async def get_cohort_analysis(db: AsyncSession = Depends(get_db)):
    """Get weekly cohort analysis."""
    try:
        result = await db.execute(
            select(
                func.date_trunc("week", Order.created_at),
                func.count(func.distinct(Order.customer_id)),
                func.sum(Order.amount),
            )
            .filter(Order.status == OrderStatus.COMPLETED)
            .group_by(func.date_trunc("week", Order.created_at))
            .order_by(func.date_trunc("week", Order.created_at).desc())
        )

        rows = result.all()
        return [
            {
                "week": str(row[0]),
                "customers": int(row[1] or 0),
                "revenue": float(row[2] or 0),
            }
            for row in rows
        ]
    except Exception as e:
        logger.error(f"Error fetching cohort analysis: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/forecast")
async def get_revenue_forecast(days_ahead: int = 7, db: AsyncSession = Depends(get_db)):
    """Get simple revenue forecast based on 30-day average."""
    try:
        cutoff = datetime.utcnow() - timedelta(days=30)
        result = await db.execute(
            select(func.avg(Order.amount))
            .filter(and_(Order.status == OrderStatus.COMPLETED, Order.created_at >= cutoff))
        )
        avg_order_value = float(result.scalar() or 0)

        # Simple forecast: assume 1 order per day average
        projected_revenue = avg_order_value * days_ahead

        return {
            "forecast_days": days_ahead,
            "average_order_value": avg_order_value,
            "projected_revenue": projected_revenue,
            "basis": "30-day average",
        }
    except Exception as e:
        logger.error(f"Error generating forecast: {e}")
        raise HTTPException(status_code=500, detail=str(e))
