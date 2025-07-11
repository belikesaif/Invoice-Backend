from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
from mangum import Mangum

from .database import engine, Base
from .config import settings
from .api import contracts, invoices, auth, oauth, profile
from .models import User, Contract, Invoice

from loguru import logger

# Create database tables
Base.metadata.create_all(bind=engine)
logger.info("Database tables created successfully")
logger.info(f"Tables in metadata: {Base.metadata.tables.keys()}")

# Configure logging
logging.basicConfig(level=settings.LOG_LEVEL)
logger.add(settings.LOG_FILE, rotation="500 MB", retention="10 days")

# Create FastAPI application
app = FastAPI(
    title=settings.PROJECT_NAME,
    description="API for Smart Invoice Validator",
    version="1.0.0",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    redirect_slashes=False
)

# handler = Mangum(app, lifespan="off")
# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def redirect_middleware(request, call_next):
    response = await call_next(request)
    return response

# Include routers
app.include_router(auth.router, prefix=f"{settings.API_V1_STR}/auth", tags=["Authentication"])
app.include_router(oauth.router, prefix=f"{settings.API_V1_STR}/oauth", tags=["OAuth"])
app.include_router(profile.router, prefix=settings.API_V1_STR, tags=["Profile"])
app.include_router(contracts.router, prefix=settings.API_V1_STR)
app.include_router(invoices.router, prefix=settings.API_V1_STR)

@app.get("/")
async def root():
    """Root endpoint that returns API information."""
    return {
        "message": "Welcome to Smart Invoice Validator API",
        "version": "1.0.0",
        "docs_url": "/docs",
        "redoc_url": "/redoc"
    } 