"""
AIONForge Revenue OS - FastAPI Backend
Main application entry point with middleware, routes, and error handling.
"""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
import os

# Import routers
from app.routers import gumroad, notion, email, products, customers, revenue
from app.core.database import init_db
from app.core.config import settings

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage app lifecycle: startup and shutdown events."""
    # Startup
    logger.info("🚀 AIONForge Revenue OS Starting...")
    try:
        await init_db()
        logger.info("✅ Database initialized successfully")
    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}")
        raise
    
    yield
    
    # Shutdown
    logger.info("🛑 AIONForge Revenue OS Shutting Down...")

# Initialize FastAPI app
app = FastAPI(
    title="AIONForge Revenue OS API",
    description="Backend infrastructure for Multi-AI Revenue Chain product launch automation",
    version="1.0.0",
    lifespan=lifespan
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch-all exception handler with detailed logging."""
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": str(exc) if settings.DEBUG else "An error occurred"
        }
    )

# Health check endpoint
@app.get("/health", tags=["Health"])
async def health_check():
    """System health check endpoint."""
    return {
        "status": "healthy",
        "service": "AIONForge Revenue OS",
        "version": "1.0.0"
    }

# Include routers
app.include_router(gumroad.router, prefix="/api/v1/gumroad", tags=["Gumroad"])
app.include_router(notion.router, prefix="/api/v1/notion", tags=["Notion"])
app.include_router(email.router, prefix="/api/v1/email", tags=["Email"])
app.include_router(products.router, prefix="/api/v1/products", tags=["Products"])
app.include_router(customers.router, prefix="/api/v1/customers", tags=["Customers"])
app.include_router(revenue.router, prefix="/api/v1/revenue", tags=["Revenue"])

# Root endpoint
@app.get("/", tags=["Root"])
async def root():
    """API root with documentation links."""
    return {
        "message": "AIONForge Revenue OS API",
        "docs": "/docs",
        "redoc": "/redoc",
        "openapi": "/openapi.json"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host=settings.API_HOST,
        port=settings.API_PORT,
        log_level=settings.LOG_LEVEL.lower()
    )
