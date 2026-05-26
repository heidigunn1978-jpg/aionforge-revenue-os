# Production Deployment Guide

## Prerequisites
- Python 3.11+
- PostgreSQL 14+ (or Supabase)
- API keys: Gumroad, Notion, SendGrid/Mailgun

## Local Development

```bash
# Clone repository
git clone https://github.com/heidigunn1978-jpg/aionforge-revenue-os.git
cd aionforge-revenue-os

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy and configure environment
cp .env.example .env
# Edit .env with your API keys

# Run with Docker Compose
docker-compose up -d

# Run migrations (if using Alembic)
alembic upgrade head

# Start development server
uvicorn app.main:app --reload
```

API will be available at `http://localhost:8000`
Docs at `http://localhost:8000/docs`

## Production Deployment (Railway)

### Step 1: Install Railway CLI
```bash
npm install -g @railway/cli
railway login
```

### Step 2: Initialize Project
```bash
cd aionforge-revenue-os
railway init
```

### Step 3: Add Environment Variables
```bash
railway variable set DATABASE_URL "postgresql://user:pass@host:5432/aionforge_revenue_os"
railway variable set GUMROAD_API_KEY "your-key"
railway variable set GUMROAD_WEBHOOK_SECRET "your-secret"
railway variable set NOTION_API_KEY "your-key"
railway variable set NOTION_DATABASE_ID "your-id"
railway variable set EMAIL_API_KEY "your-key"
railway variable set ENVIRONMENT "production"
```

### Step 4: Deploy
```bash
railway up
```

Railway will automatically:
- Detect Python project
- Install dependencies
- Build Docker image
- Deploy to production
- Assign domain (e.g., `aionforge-revenue-os-prod.railway.app`)

## Production Deployment (Heroku)

### Step 1: Login to Heroku
```bash
heroku login
```

### Step 2: Create App
```bash
heroku create aionforge-revenue-os
```

### Step 3: Add Buildpack
```bash
heroku buildpacks:add heroku/python
```

### Step 4: Set Environment Variables
```bash
heroku config:set DATABASE_URL="postgresql://..."
heroku config:set GUMROAD_API_KEY="your-key"
heroku config:set GUMROAD_WEBHOOK_SECRET="your-secret"
heroku config:set NOTION_API_KEY="your-key"
heroku config:set NOTION_DATABASE_ID="your-id"
heroku config:set EMAIL_API_KEY="your-key"
heroku config:set ENVIRONMENT="production"
```

### Step 5: Deploy
```bash
git push heroku main
```

## Gumroad Webhook Configuration

1. Go to Gumroad Settings → Webhooks
2. Add webhook URL: `https://your-app.railway.app/api/v1/gumroad/webhook/sale`
3. Copy webhook secret to `GUMROAD_WEBHOOK_SECRET` environment variable

## Notion Database Setup

1. Create new Notion database (or use existing)
2. Create Notion Integration at https://www.notion.com/my-integrations
3. Copy API key to `NOTION_API_KEY`
4. Share database with integration
5. Get database ID from URL: `notion.com/workspace/{DATABASE_ID}?v=...`

## Email Service Setup

### SendGrid
1. Create account at sendgrid.com
2. Generate API key from Settings → API Keys
3. Set `EMAIL_API_KEY` and `EMAIL_PROVIDER=sendgrid`

### Mailgun
1. Create account at mailgun.com
2. Get API key from Account Settings
3. Set `EMAIL_API_KEY` and `EMAIL_PROVIDER=mailgun`

## Database

### Using Supabase (Recommended)
1. Create project at supabase.com
2. Get connection string from Settings → Database
3. Set `DATABASE_URL` to Supabase connection string

### Using PostgreSQL
1. Install PostgreSQL locally or use managed service
2. Create database: `createdb aionforge_revenue_os`
3. Set `DATABASE_URL` to your connection string

## Health Check

```bash
curl https://your-app.railway.app/health
# Response: {"status": "healthy", "version": "1.0.0", ...}
```

## Monitoring

Railway provides:
- Real-time logs
- Error tracking
- Metrics dashboard
- Email alerts

View logs:
```bash
railway logs
```

## Troubleshooting

### Database Connection Failed
- Verify DATABASE_URL is correct
- Check firewall rules allow connection
- Test with: `psql $DATABASE_URL`

### Webhook Not Receiving
- Verify webhook URL is correct
- Check Gumroad signature matches
- View logs: `railway logs` or `heroku logs --tail`

### Email Not Sending
- Verify EMAIL_API_KEY
- Check email logs: `/api/v1/email/logs`
- Test with curl:

```bash
curl -X POST http://localhost:8000/api/v1/email/campaigns/send \
  -H "Content-Type: application/json" \
  -d '{
    "to_email": "test@example.com",
    "subject": "Test",
    "body": "<h1>Test Email</h1>",
    "campaign_id": 1
  }'
```

## Scaling

Railway auto-scales based on CPU/memory. For high-volume:
1. Increase PostgreSQL resources
2. Enable connection pooling (PgBouncer)
3. Add Redis for caching
4. Use async workers
