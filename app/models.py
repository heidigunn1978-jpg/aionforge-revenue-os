"""SQLAlchemy ORM models for database tables."""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, ForeignKey, Text, Enum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
import enum
import secrets

Base = declarative_base()


class SubscriptionTier(str, enum.Enum):
    """Agency subscription tiers."""
    BLUEPRINT = "blueprint"  # $497/month - 5 clients
    GHOST_FACTORY = "ghost_factory"  # $1,497/month - 20 clients
    SOVEREIGN_SUBSTRATE = "sovereign_substrate"  # $4,997/month - unlimited


class SubscriptionStatus(str, enum.Enum):
    """Subscription status."""
    ACTIVE = "active"
    PAUSED = "paused"
    CANCELLED = "cancelled"
    PAST_DUE = "past_due"


class ProductTier(str, enum.Enum):
    """Product tier classification."""
    MAIN = "main"
    BUMP = "bump"
    UPSELL = "upsell"


class OrderStatus(str, enum.Enum):
    """Order status tracking."""
    PENDING = "pending"
    COMPLETED = "completed"
    REFUNDED = "refunded"
    FAILED = "failed"


class EmailCampaignStatus(str, enum.Enum):
    """Email campaign status."""
    DRAFT = "draft"
    SCHEDULED = "scheduled"
    SENT = "sent"
    FAILED = "failed"


class Agency(Base):
    """Agency/Partner account."""
    __tablename__ = "agencies"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    stripe_customer_id = Column(String(255), unique=True, index=True)
    subscription_tier = Column(Enum(SubscriptionTier), default=SubscriptionTier.BLUEPRINT)
    subscription_status = Column(Enum(SubscriptionStatus), default=SubscriptionStatus.ACTIVE)
    stripe_subscription_id = Column(String(255), unique=True, index=True)
    client_limit = Column(Integer, default=5)  # Based on tier
    active_clients = Column(Integer, default=0)
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    api_keys = relationship("APIKey", back_populates="agency", cascade="all, delete-orphan")
    subscriptions = relationship("Subscription", back_populates="agency", cascade="all, delete-orphan")


class APIKey(Base):
    """API keys for agency authentication."""
    __tablename__ = "api_keys"

    id = Column(Integer, primary_key=True, index=True)
    agency_id = Column(Integer, ForeignKey("agencies.id"), nullable=False, index=True)
    key = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True, index=True)
    last_used_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    agency = relationship("Agency", back_populates="api_keys")


class Subscription(Base):
    """Subscription billing records."""
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    agency_id = Column(Integer, ForeignKey("agencies.id"), nullable=False, index=True)
    stripe_subscription_id = Column(String(255), unique=True, nullable=False, index=True)
    tier = Column(Enum(SubscriptionTier), nullable=False)
    status = Column(Enum(SubscriptionStatus), default=SubscriptionStatus.ACTIVE)
    amount = Column(Float, nullable=False)  # Monthly amount in cents
    current_period_start = Column(DateTime, nullable=False)
    current_period_end = Column(DateTime, nullable=False)
    cancel_at_period_end = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    agency = relationship("Agency", back_populates="subscriptions")


class Product(Base):
    """Product table."""
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    price = Column(Float, nullable=False)
    tier = Column(Enum(ProductTier), default=ProductTier.MAIN)
    gumroad_id = Column(String(255), unique=True, index=True)
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    orders = relationship("Order", back_populates="product")


class Customer(Base):
    """Customer table."""
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    gumroad_customer_id = Column(String(255), unique=True, index=True)
    first_name = Column(String(255))
    last_name = Column(String(255))
    avatar_url = Column(String(500))
    total_spent = Column(Float, default=0.0)
    purchase_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    orders = relationship("Order", back_populates="customer")


class Order(Base):
    """Order table."""
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False, index=True)
    gumroad_order_id = Column(String(255), unique=True, nullable=False, index=True)
    amount = Column(Float, nullable=False)
    currency = Column(String(3), default="USD")
    status = Column(Enum(OrderStatus), default=OrderStatus.COMPLETED, index=True)
    license_key = Column(String(255))
    order_metadata = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    customer = relationship("Customer", back_populates="orders")
    product = relationship("Product", back_populates="orders")


class Revenue(Base):
    """Revenue aggregation table."""
    __tablename__ = "revenue"

    id = Column(Integer, primary_key=True, index=True)
    date = Column(DateTime, nullable=False, unique=True, index=True)
    total_revenue = Column(Float, default=0.0)
    total_orders = Column(Integer, default=0)
    total_customers = Column(Integer, default=0)
    average_order_value = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class EmailCampaign(Base):
    """Email campaign template."""
    __tablename__ = "email_campaigns"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    subject = Column(String(500), nullable=False)
    body = Column(Text, nullable=False)
    day_number = Column(Integer)  # 1-5 for launch sequence
    status = Column(Enum(EmailCampaignStatus), default=EmailCampaignStatus.DRAFT, index=True)
    scheduled_time = Column(DateTime, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class EmailLog(Base):
    """Email delivery tracking."""
    __tablename__ = "email_logs"

    id = Column(Integer, primary_key=True, index=True)
    campaign_id = Column(Integer, ForeignKey("email_campaigns.id"), index=True)
    customer_email = Column(String(255), nullable=False, index=True)
    status = Column(String(50), nullable=False, index=True)  # sent, delivered, bounced, opened, clicked
    provider_id = Column(String(255), unique=True, index=True)  # SendGrid message ID
    retry_count = Column(Integer, default=0)
    error_message = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

