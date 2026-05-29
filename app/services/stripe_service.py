"""Stripe payment processing service."""

import stripe
from typing import Optional
from app.core.config import settings
from app.models import SubscriptionTier

stripe.api_key = settings.STRIPE_API_KEY

# Pricing mapping
TIER_PRICING = {
    SubscriptionTier.BLUEPRINT: {
        "price_id": "price_blueprint",  # Set in Stripe dashboard
        "amount": 49700,  # $497 in cents
        "client_limit": 5,
    },
    SubscriptionTier.GHOST_FACTORY: {
        "price_id": "price_ghost_factory",
        "amount": 149700,  # $1,497 in cents
        "client_limit": 20,
    },
    SubscriptionTier.SOVEREIGN_SUBSTRATE: {
        "price_id": "price_sovereign_substrate",
        "amount": 499700,  # $4,997 in cents
        "client_limit": None,  # Unlimited
    },
}


async def create_customer(email: str, name: str) -> str:
    """Create a Stripe customer."""
    customer = stripe.Customer.create(
        email=email,
        name=name,
    )
    return customer.id


async def create_subscription(
    customer_id: str,
    tier: SubscriptionTier,
) -> dict:
    """Create a Stripe subscription."""
    pricing = TIER_PRICING[tier]
    
    subscription = stripe.Subscription.create(
        customer=customer_id,
        items=[{"price": pricing["price_id"]}],
        payment_behavior="default_incomplete",
        expand=["latest_invoice.payment_intent"],
    )
    
    return {
        "subscription_id": subscription.id,
        "client_secret": subscription.latest_invoice.payment_intent.client_secret,
        "status": subscription.status,
    }


async def cancel_subscription(subscription_id: str) -> dict:
    """Cancel a subscription at period end."""
    subscription = stripe.Subscription.modify(
        subscription_id,
        cancel_at_period_end=True,
    )
    return {
        "subscription_id": subscription.id,
        "status": subscription.status,
        "cancel_at": subscription.cancel_at,
    }


async def get_subscription(subscription_id: str) -> dict:
    """Get subscription details."""
    subscription = stripe.Subscription.retrieve(subscription_id)
    return {
        "subscription_id": subscription.id,
        "status": subscription.status,
        "current_period_start": subscription.current_period_start,
        "current_period_end": subscription.current_period_end,
        "cancel_at_period_end": subscription.cancel_at_period_end,
    }


def verify_webhook_signature(payload: bytes, sig_header: str) -> dict:
    """Verify Stripe webhook signature."""
    try:
        event = stripe.Webhook.construct_event(
            payload,
            sig_header,
            settings.STRIPE_WEBHOOK_SECRET,
        )
        return event
    except ValueError:
        raise ValueError("Invalid payload")
    except stripe.error.SignatureVerificationError:
        raise ValueError("Invalid signature")

