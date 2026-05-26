"""Email automation engine for 5-day launch sequence."""

import logging
import asyncio
import aiohttp
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pydantic import BaseModel, EmailStr

from app.core.config import settings
from app.core.database import get_db
from app.models import EmailCampaign, EmailLog, Customer, EmailCampaignStatus

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/email", tags=["email"])


class EmailCampaignCreate(BaseModel):
    """Email campaign creation schema."""
    name: str
    subject: str
    body: str
    day_number: int
    scheduled_time: datetime


class SendEmailRequest(BaseModel):
    """Send email request schema."""
    to_email: EmailStr
    subject: str
    body: str
    campaign_id: int = None


async def send_email_with_retry(to_email: str, subject: str, body: str, max_retries: int = 3) -> dict:
    """Send email with exponential backoff retry logic."""
    base_wait = 1

    for attempt in range(max_retries):
        try:
            async with aiohttp.ClientSession() as session:
                if settings.EMAIL_PROVIDER == "sendgrid":
                    headers = {"Authorization": f"Bearer {settings.EMAIL_API_KEY}"}
                    payload = {
                        "personalizations": [{"to": [{"email": to_email}]}],
                        "from": {"email": settings.EMAIL_FROM, "name": settings.EMAIL_FROM_NAME},
                        "subject": subject,
                        "content": [{"type": "text/html", "value": body}],
                    }

                    async with session.post(
                        "https://api.sendgrid.com/v3/mail/send",
                        json=payload,
                        headers=headers,
                        timeout=aiohttp.ClientTimeout(total=10),
                    ) as resp:
                        if resp.status == 202:
                            return {"success": True, "provider_id": resp.headers.get("X-Message-ID")}
                        elif resp.status >= 500:
                            raise Exception(f"Server error: {resp.status}")
                        else:
                            error_text = await resp.text()
                            logger.error(f"SendGrid error: {error_text}")
                            return {"success": False, "error": error_text}

                elif settings.EMAIL_PROVIDER == "mailgun":
                    async with session.post(
                        f"https://api.mailgun.net/v3/{settings.MAILGUN_DOMAIN}/messages",
                        data={"from": settings.EMAIL_FROM, "to": to_email, "subject": subject, "html": body},
                        auth=aiohttp.BasicAuth("api", settings.EMAIL_API_KEY),
                        timeout=aiohttp.ClientTimeout(total=10),
                    ) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            return {"success": True, "provider_id": data.get("id")}
                        elif resp.status >= 500:
                            raise Exception(f"Server error: {resp.status}")
                        else:
                            error_text = await resp.text()
                            return {"success": False, "error": error_text}

        except Exception as e:
            logger.warning(f"Email send attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                wait_time = base_wait * (2 ** attempt)
                await asyncio.sleep(wait_time)
            else:
                return {"success": False, "error": str(e), "retries_exhausted": True}

    return {"success": False, "error": "All retries exhausted"}


@router.post("/campaigns/send")
async def send_campaign(
    request: SendEmailRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Send email campaign."""
    try:
        result = await send_email_with_retry(request.to_email, request.subject, request.body)

        if result["success"]:
            # Log email
            email_log = EmailLog(
                campaign_id=request.campaign_id,
                customer_email=request.to_email,
                status="sent",
                provider_id=result.get("provider_id"),
            )
            db.add(email_log)
            await db.commit()

            logger.info(f"Email sent to {request.to_email}")
            return {"status": "sent", "email": request.to_email}
        else:
            raise HTTPException(status_code=500, detail=result.get("error", "Failed to send email"))
    except Exception as e:
        logger.error(f"Error sending email: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/logs")
async def get_email_logs(db: AsyncSession = Depends(get_db), limit: int = 100):
    """Get email logs."""
    try:
        result = await db.execute(select(EmailLog).limit(limit).order_by(EmailLog.created_at.desc()))
        logs = result.scalars().all()
        return [{"id": log.id, "email": log.customer_email, "status": log.status, "created_at": log.created_at} for log in logs]
    except Exception as e:
        logger.error(f"Error fetching email logs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analytics/open-rate")
async def get_open_rate(campaign_id: int = None, db: AsyncSession = Depends(get_db)):
    """Get email open rate."""
    try:
        query = select(func.count(EmailLog.id)).filter(EmailLog.status.in_(["opened", "clicked"]))
        if campaign_id:
            query = query.filter(EmailLog.campaign_id == campaign_id)

        opened = await db.execute(query)
        opened_count = opened.scalar() or 0

        query = select(func.count(EmailLog.id)).filter(EmailLog.status == "sent")
        if campaign_id:
            query = query.filter(EmailLog.campaign_id == campaign_id)

        sent = await db.execute(query)
        sent_count = sent.scalar() or 0

        open_rate = (opened_count / sent_count * 100) if sent_count > 0 else 0
        return {"open_rate": open_rate, "opened": opened_count, "sent": sent_count}
    except Exception as e:
        logger.error(f"Error calculating open rate: {e}")
        raise HTTPException(status_code=500, detail=str(e))
