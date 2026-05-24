"""Revenue Analytics Router"""
import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import datetime, timedelta

from app.core.database import get_db
from app.models import Order, Product, Customer

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/summary")
async def get_revenue_summary(
    days: int = Query(90),
    db: AsyncSession = Depends(get_db)
):
    """
    Get overall revenue summary for the last N days
    Returns: total revenue, orders, customers, AOV
    """
    try:
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        # Total revenue
        stmt = select(func.sum(Order.amount)).where(
            (Order.status == "completed") & (Order.created_at >= cutoff_date)
        )
        total_revenue = (await db.execute(stmt)).scalar() or 0
        
        # Total orders
        stmt = select(func.count(Order.id)).where(
            (Order.status == "completed") & (Order.created_at >= cutoff_date)
        )
        total_orders = (await db.execute(stmt)).scalar() or 0
        
        # Unique customers
        stmt = select(func.count(func.distinct(Order.customer_id))).where(
            (Order.status == "completed") & (Order.created_at >= cutoff_date)
        )
        total_customers = (await db.execute(stmt)).scalar() or 0
        
        aov = round(total_revenue / total_orders, 2) if total_orders > 0 else 0
        
        return {
            "period_days": days,
            "total_revenue": round(total_revenue, 2),
            "total_orders": total_orders,
            "total_customers": total_customers,
            "average_order_value": aov
        }
        
    except Exception as e:
        logger.error(f"Revenue summary error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/daily")
async def get_daily_revenue(
    days: int = Query(30),
    db: AsyncSession = Depends(get_db)
):
    """
    Get daily revenue breakdown for the last N days
    Returns: daily totals with trend analysis
    """
    try:
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        # Raw SQL aggregation by day
        stmt = select(
            func.date(Order.created_at).label("date"),
            func.sum(Order.amount).label("revenue"),
            func.count(Order.id).label("orders")
        ).where(
            (Order.status == "completed") & (Order.created_at >= cutoff_date)
        ).group_by(
            func.date(Order.created_at)
        ).order_by(
            func.date(Order.created_at).desc()
        )
        
        results = (await db.execute(stmt)).all()
        
        daily_data = [
            {
                "date": str(row[0]),
                "revenue": round(float(row[1] or 0), 2),
                "orders": row[2]
            }
            for row in results
        ]
        
        return {
            "period_days": days,
            "daily_data": daily_data
        }
        
    except Exception as e:
        logger.error(f"Daily revenue error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/by-product")
async def get_revenue_by_product(
    days: int = Query(90),
    db: AsyncSession = Depends(get_db)
):
    """
    Get revenue breakdown by product (Main, Bump, Upsell)
    """
    try:
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        stmt = select(
            Product.name,
            Product.tier,
            func.sum(Order.amount).label("revenue"),
            func.count(Order.id).label("orders"),
            func.count(func.distinct(Order.customer_id)).label("customers")
        ).join(
            Order, Order.product_id == Product.id
        ).where(
            (Order.status == "completed") & (Order.created_at >= cutoff_date)
        ).group_by(
            Product.id, Product.name, Product.tier
        )
        
        results = (await db.execute(stmt)).all()
        
        product_data = [
            {
                "product_name": row[0],
                "tier": row[1],
                "revenue": round(float(row[2] or 0), 2),
                "orders": row[3],
                "customers": row[4]
            }
            for row in results
        ]
        
        return {
            "period_days": days,
            "by_product": product_data
        }
        
    except Exception as e:
        logger.error(f"Revenue by product error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cohort")
async def get_cohort_analysis(
    groupby: str = Query("week"),  # week or month
    db: AsyncSession = Depends(get_db)
):
    """
    Get cohort analysis grouped by week or month
    """
    try:
        if groupby == "week":
            date_func = func.date_trunc('week', Order.created_at)
        else:
            date_func = func.date_trunc('month', Order.created_at)
        
        stmt = select(
            date_func.label("period"),
            func.count(func.distinct(Order.customer_id)).label("new_customers"),
            func.count(Order.id).label("orders"),
            func.sum(Order.amount).label("revenue")
        ).where(
            Order.status == "completed"
        ).group_by(
            date_func
        ).order_by(
            date_func.desc()
        ).limit(12)
        
        results = (await db.execute(stmt)).all()
        
        cohort_data = [
            {
                "period": str(row[0]) if row[0] else "Unknown",
                "new_customers": row[1],
                "orders": row[2],
                "revenue": round(float(row[3] or 0), 2)
            }
            for row in results
        ]
        
        return {
            "groupby": groupby,
            "cohorts": cohort_data
        }
        
    except Exception as e:
        logger.error(f"Cohort analysis error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/forecast")
async def get_revenue_forecast(
    days_ahead: int = Query(30),
    db: AsyncSession = Depends(get_db)
):
    """
    Simple revenue forecast based on last 30 days average
    """
    try:
        # Get average daily revenue from last 30 days
        cutoff_date = datetime.utcnow() - timedelta(days=30)
        
        stmt = select(
            func.sum(Order.amount) / func.count(func.distinct(func.date(Order.created_at)))
        ).where(
            (Order.status == "completed") & (Order.created_at >= cutoff_date)
        )
        
        avg_daily_revenue = (await db.execute(stmt)).scalar() or 0
        
        # Forecast
        forecasted_revenue = avg_daily_revenue * days_ahead
        
        return {
            "forecast_days": days_ahead,
            "avg_daily_revenue": round(float(avg_daily_revenue), 2),
            "forecasted_revenue": round(float(forecasted_revenue), 2)
        }
        
    except Exception as e:
        logger.error(f"Revenue forecast error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
