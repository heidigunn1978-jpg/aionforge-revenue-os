"""Notion API integration for Revenue OS sync."""

import logging
import asyncio
import aiohttp
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.config import settings
from app.core.database import get_db
from app.models import Order, Customer, Revenue

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/notion", tags=["notion"])


class NotionService:
    """Notion API client with error handling and retries."""

    BASE_URL = "https://api.notion.com/v1"
    MAX_RETRIES = 3

    @classmethod
    async def _make_request(
        cls,
        method: str,
        endpoint: str,
        payload: dict = None,
        retry_count: int = 0,
    ) -> dict:
        """Make request with exponential backoff retry."""
        headers = {
            "Authorization": f"Bearer {settings.NOTION_API_KEY}",
            "Notion-Version": settings.NOTION_VERSION,
            "Content-Type": "application/json",
        }

        try:
            async with aiohttp.ClientSession() as session:
                url = f"{cls.BASE_URL}{endpoint}"
                async with session.request(
                    method,
                    url,
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as resp:
                    if resp.status == 429:  # Rate limit
                        if retry_count < cls.MAX_RETRIES:
                            wait_time = (2 ** retry_count)
                            logger.warning(f"Rate limited. Retrying in {wait_time}s")
                            await asyncio.sleep(wait_time)
                            return await cls._make_request(method, endpoint, payload, retry_count + 1)
                        else:
                            raise Exception("Max retries exceeded")

                    elif resp.status >= 400:
                        error_text = await resp.text()
                        logger.error(f"Notion API error {resp.status}: {error_text}")
                        raise Exception(f"Notion API error: {resp.status}")

                    return await resp.json()
        except asyncio.TimeoutError:
            logger.error("Notion API request timeout")
            raise Exception("Request timeout")
        except Exception as e:
            logger.error(f"Notion request error: {e}")
            raise

    @classmethod
    async def create_order_page(cls, order_data: dict) -> dict:
        """Create a page in Notion for an order."""
        try:
            payload = {
                "parent": {"database_id": settings.NOTION_DATABASE_ID},
                "properties": {
                    "Title": {"title": [{"text": {"content": f"Order {order_data.get('order_id', 'N/A')}"}}]},
                    "Email": {"email": order_data.get("email")},
                    "Amount": {"number": order_data.get("amount", 0)},
                    "Date": {"date": {"start": datetime.utcnow().isoformat()}},
                },
            }

            result = await cls._make_request("POST", "/pages", payload)
            return {"success": True, "page_id": result.get("id")}
        except Exception as e:
            logger.error(f"Failed to create Notion page: {e}")
            return {"success": False, "error": str(e)}

    @classmethod
    async def update_revenue_dashboard(cls, db: AsyncSession) -> dict:
        """Update revenue dashboard in Notion."""
        try:
            # Fetch current revenue stats
            result = await db.execute(select(func.sum(Order.amount), func.count(Order.id)))
            total_revenue, total_orders = result.one()

            payload = {
                "parent": {"database_id": settings.NOTION_DATABASE_ID},
                "properties": {
                    "Title": {"title": [{"text": {"content": f"Revenue Dashboard - {datetime.utcnow().isoformat()}"}}]},
                    "Total Revenue": {"number": float(total_revenue or 0)},
                    "Total Orders": {"number": int(total_orders or 0)},
                    "Updated": {"date": {"start": datetime.utcnow().isoformat()}},
                },
            }

            result = await cls._make_request("POST", "/pages", payload)
            return {"success": True, "page_id": result.get("id")}
        except Exception as e:
            logger.error(f"Failed to update Notion dashboard: {e}")
            return {"success": False, "error": str(e)}


@router.post("/sync/order")
async def sync_order_to_notion(order_id: int, db: AsyncSession = Depends(get_db)):
    """Sync an order to Notion."""
    try:
        from app.models import Order
        result = await db.execute(select(Order).filter(Order.id == order_id))
        order = result.scalar_one_or_none()

        if not order:
            raise HTTPException(status_code=404, detail="Order not found")

        order_data = {
            "order_id": order.gumroad_order_id,
            "email": order.customer.email,
            "amount": order.amount,
        }

        result = await NotionService.create_order_page(order_data)
        return result
    except Exception as e:
        logger.error(f"Error syncing order: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sync/dashboard")
async def sync_dashboard_to_notion(db: AsyncSession = Depends(get_db)):
    """Sync revenue dashboard to Notion."""
    try:
        result = await NotionService.update_revenue_dashboard(db)
        return result
    except Exception as e:
        logger.error(f"Error syncing dashboard: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def check_notion_status():
    """Check Notion API connectivity."""
    try:
        headers = {
            "Authorization": f"Bearer {settings.NOTION_API_KEY}",
            "Notion-Version": settings.NOTION_VERSION,
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{NotionService.BASE_URL}/databases/{settings.NOTION_DATABASE_ID}",
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status == 200:
                    return {"status": "connected", "database_id": settings.NOTION_DATABASE_ID}
                else:
                    return {"status": "error", "code": resp.status}
    except Exception as e:
        logger.error(f"Notion status check error: {e}")
        return {"status": "error", "error": str(e)}
