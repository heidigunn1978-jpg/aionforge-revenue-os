"""FastAPI application entry point with lifecycle management."""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging

from app.core.config import settings
from app.core.database import init_db, close_db
from app.api import routers

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle."""
    # Startup
    logger.info("Starting AIONForge Revenue OS API")
    await init_db()
    yield
    # Shutdown
    logger.info("Shutting down AIONForge Revenue OS API")
    await close_db()


app = FastAPI(
    title="AIONForge Revenue OS",
    description="Backend API for Multi-AI Revenue Chain product launch automation",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return JSONResponse(
        status_code=200,
        content={
            "status": "healthy",
            "version": "1.0.0",
            "environment": settings.ENVIRONMENT,
        },
    )


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "AIONForge Revenue OS API",
        "docs": "/docs",
        "version": "1.0.0",
    }


# Include routers
app.include_router(routers.gumroad.router)
app.include_router(routers.email.router)
app.include_router(routers.notion.router)
app.include_router(routers.products.router)
app.include_router(routers.customers.router)
app.include_router(routers.revenue.router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host=settings.API_HOST,
        port=settings.API_PORT,
        log_level=settings.LOG_LEVEL.lower(),
    )
