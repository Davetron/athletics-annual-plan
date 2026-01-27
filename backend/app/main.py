"""
FastAPI application entry point.
Configures CORS, routers, and application lifecycle.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.models.database import init_db
from app.routers import auth, chat, plan, competitions


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler - runs on startup and shutdown."""
    # Startup: Initialize database
    await init_db()
    yield
    # Shutdown: cleanup if needed


app = FastAPI(
    title="Athletics Annual Plan API",
    description="Backend API for generating 52-week periodized training plans",
    version="1.0.0",
    lifespan=lifespan,
)

# Configure CORS
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix="/api", tags=["auth"])
app.include_router(chat.router, prefix="/api", tags=["chat"])
app.include_router(plan.router, prefix="/api", tags=["plan"])
app.include_router(competitions.router, prefix="/api", tags=["competitions"])


@app.get("/")
async def root():
    """Health check endpoint."""
    return {"status": "ok", "service": "Athletics Annual Plan API"}


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}
