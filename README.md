# AIONForge Revenue OS - Backend Infrastructure

Production-grade backend for "The Multi-AI Revenue Chain" digital product launch automation.

## Architecture Overview

- **FastAPI** - Core backend service
- **PostgreSQL/Supabase** - Customer, product, revenue data
- **Gumroad API** - Payment & product management
- **Notion API** - Revenue OS sync
- **Email Service** - 5-day launch sequence automation
- **GitHub Actions** - Scheduled workflow orchestration

## Quick Start

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## Environment Variables

See `.env.example` for required configuration.

## Deployment

See `DEPLOYMENT.md` for production setup instructions.
