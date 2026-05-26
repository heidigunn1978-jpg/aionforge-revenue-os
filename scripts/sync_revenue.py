"""
Script to sync revenue data to Notion dashboard.
Run via GitHub Actions hourly or manually.
"""

import asyncio
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import async_session
from app.api.notion import NotionService


async def main():
    """Sync revenue to Notion."""
    async with async_session() as session:
        print("Syncing revenue to Notion...")
        result = await NotionService.update_revenue_dashboard(session)
        
        if result.get("success"):
            print(f"✓ Revenue dashboard synced successfully")
            print(f"  Page ID: {result.get('page_id')}")
        else:
            print(f"✗ Sync failed: {result.get('error')}")
            sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
