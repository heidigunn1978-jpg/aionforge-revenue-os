# System Architecture

## Overview

AIONForge Revenue OS is a production-grade backend for automating digital product launches using AI orchestration.

```
┌─────────────────────────────────────────────┐
│        External Services                     │
├─────────────────────────────────────────────┤
│  Gumroad    │  Notion    │  SendGrid        │
│  (Payments) │ (Dashboard)│  (Email)         │
└────────────────────────────────────────────┐
                   │
                   ↓
┌─────────────────────────────────────────────┐
│        FastAPI Backend                       │
├─────────────────────────────────────────────┤
│  Webhook Handlers │ Async Tasks              │
│  REST APIs       │ Retry Logic              │
│  Error Handling  │ Rate Limiting            │
└────────────────────────────────────────────┐
                   │
                   ↓
┌─────────────────────────────────────────────┐
│      PostgreSQL/Supabase Database            │
├─────────────────────────────────────────────┤
│ Products │ Customers │ Orders │ Revenue    │
│ Email Campaigns │ Email Logs                │
└─────────────────────────────────────────────┘
```

## Components

### API Routes

#### Gumroad Router (`/api/v1/gumroad`)
- `POST /webhook/sale` - Receive payment webhooks
- `GET /sales/summary` - Sales statistics
- `GET /customers/count` - Total customer count
- **Features**: HMAC signature verification, idempotency, auto-customer creation

#### Email Router (`/api/v1/email`)
- `POST /campaigns/send` - Send email with retries
- `GET /logs` - Email delivery logs
- `GET /analytics/open-rate` - Open rate metrics
- **Features**: 3-attempt exponential backoff, provider abstraction (SendGrid/Mailgun)

#### Notion Router (`/api/v1/notion`)
- `POST /sync/order` - Sync order to Notion
- `POST /sync/dashboard` - Update revenue dashboard
- `GET /status` - Check Notion connectivity
- **Features**: Automatic retry on rate limit (429), async requests

#### Products Router (`/api/v1/products`)
- `POST /` - Create product
- `GET /` - List products
- `GET /{id}` - Get product
- `PATCH /{id}` - Update product
- `DELETE /{id}` - Soft delete

#### Customers Router (`/api/v1/customers`)
- `POST /` - Create customer
- `GET /` - List customers
- `GET /{id}` - Get customer with orders
- `GET /search/{email}` - Search by email
- `PATCH /{id}` - Update customer
- `GET /{id}/orders` - Get customer orders

#### Revenue Router (`/api/v1/revenue`)
- `GET /summary` - Revenue summary
- `GET /daily` - Daily breakdown
- `GET /by-product` - Product breakdown
- `GET /cohort` - Weekly cohorts
- `GET /forecast` - Revenue forecast

### Database Models

```
Product
├── id (primary key)
├── name
├── description
├── price
├── tier (main/bump/upsell)
├── gumroad_id (unique)
├── is_active
├── created_at (indexed)
└── updated_at

Customer
├── id (primary key)
├── email (unique, indexed)
├── gumroad_customer_id
├── first_name
├── last_name
├── avatar_url
├── total_spent
├── purchase_count
├── created_at (indexed)
└── updated_at

Order
├── id (primary key)
├── customer_id (FK, indexed)
├── product_id (FK, indexed)
├── gumroad_order_id (unique, indexed)
├── amount
├── currency
├── status (indexed)
├── license_key
├── metadata
├── created_at (indexed)
└── updated_at

Revenue
├── id (primary key)
├── date (unique, indexed)
├── total_revenue
├── total_orders
├── total_customers
├── average_order_value
├── created_at
└── updated_at

EmailCampaign
├── id (primary key)
├── name
├── subject
├── body
├── day_number
├── status (indexed)
├── scheduled_time (indexed)
├── created_at (indexed)
└── updated_at

EmailLog
├── id (primary key)
├── campaign_id (FK)
├── customer_email (indexed)
├── status (indexed)
├── provider_id (unique, indexed)
├── retry_count
├── error_message
├── created_at (indexed)
└── updated_at
```

## Data Flows

### Payment Flow
```
Gumroad Customer Purchase
          ↓
Gumroad Webhook → /api/v1/gumroad/webhook/sale
          ↓
Signature Verification (HMAC)
          ↓
Duplicate Check (idempotency)
          ↓
Create/Update Customer
          ↓
Create Order Record
          ↓
Update Customer Totals (total_spent, purchase_count)
          ↓
Log to Database
          ↓
Notion Sync (async, optional)
          ↓
Send Confirmation Email (async, optional)
```

### Email Campaign Flow
```
/api/v1/email/campaigns/send
          ↓
Validate Email Address
          ↓
Send with Provider (SendGrid/Mailgun)
          ↓
[Success] → Log as "sent", return provider_id
          ↓
[Failure] → Retry with exponential backoff (1s, 2s, 4s)
          ↓
[Max Retries] → Log error, alert
```

### Notion Sync Flow
```
/api/v1/notion/sync/order
          ↓
Fetch Order from Database
          ↓
Format for Notion API
          ↓
Send to Notion
          ↓
[429 Rate Limited] → Exponential backoff retry
          ↓
[Success] → Log page_id
          ↓
[Error] → Log and continue (non-blocking)
```

## Error Handling

All routers implement:
- Try-catch blocks with detailed logging
- Custom HTTPException responses
- Automatic database rollback on error
- Structured error logging with tracebacks
- Rate limit handling (Notion 429s)
- Timeout management (10-30s)
- Retry logic with exponential backoff

## Security

### Webhook Security
- HMAC SHA256 signature verification (Gumroad)
- Constant-time comparison to prevent timing attacks
- Signature validation before processing

### Data Security
- Environment variable secrets (no hardcoded keys)
- SQL injection protection (ORM parameterization)
- Soft deletes (is_active flag)
- Idempotency keys for webhooks

### API Security
- CORS configured
- Input validation (Pydantic)
- HTTP timeout management
- Connection pooling with limits

## Performance

### Async Operations
- All database queries async (AsyncSession)
- All external API calls async (aiohttp)
- Non-blocking email sending
- Concurrent request handling

### Database Optimization
- 15+ indexes on frequently queried columns
- Connection pooling (20 connections, 10 overflow)
- Query efficiency (aggregation at DB level)
- Soft deletes to preserve data integrity

### Caching (Future)
- Redis for customer data
- Cache revenue metrics (5-minute TTL)
- Webhook deduplication cache

## Monitoring

### Logging
- All actions logged to stdout
- Error tracebacks captured
- Request/response logging
- Database query logging (debug mode)

### Metrics
- Revenue dashboard (/api/v1/revenue/summary)
- Email delivery stats (/api/v1/email/analytics/open-rate)
- Customer acquisition (/api/v1/customers/)
- Product performance (/api/v1/revenue/by-product)

### Health Checks
- `/health` endpoint
- Database connectivity tested
- External API status available
- Docker health check configured

## Scaling Strategy

### Horizontal
1. Load balancer (Railway/Heroku handles automatically)
2. Multiple API instances
3. Connection pooling across instances

### Vertical
1. Increase PostgreSQL resources
2. Add PgBouncer for connection pooling
3. Redis for caching
4. CDN for static assets

### Database
1. Partition orders by date range
2. Archive old email logs
3. Aggregate revenue daily
4. Create materialized views for reports

## Testing

Run tests:
```bash
pytest app/
```

Test coverage:
- Unit tests for each route
- Integration tests with PostgreSQL
- Webhook signature verification
- Error handling scenarios
