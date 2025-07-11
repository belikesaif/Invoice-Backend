from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from .config import settings
from loguru import logger
import os

# Configure logging
logger.add(
    settings.LOG_FILE,
    rotation="500 MB",
    retention="10 days",
    level=settings.LOG_LEVEL,
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}"
)

# Create SQLAlchemy engine with database-specific configuration
def create_database_engine():
    """Create database engine with appropriate configuration for the database type."""
    database_url = settings.DATABASE_URL
    
    # Check if we're using SQLite (for local development)
    if database_url.startswith("sqlite"):
        engine = create_engine(
            database_url,
            connect_args={"check_same_thread": False}  # Required for SQLite
        )
    else:
        # For PostgreSQL (production/AWS RDS)
        engine = create_engine(
            database_url,
            pool_pre_ping=True,  # Verify connections before use
            pool_recycle=300,    # Recycle connections every 5 minutes
            pool_size=10,        # Number of connections to maintain
            max_overflow=20      # Maximum number of connections to create beyond pool_size
        )
    
    return engine

# Create SQLAlchemy engine
engine = create_database_engine()

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create base class for models
Base = declarative_base()

def get_db():
    """Dependency for getting database session."""
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        logger.error(f"Database error: {str(e)}")
        raise
    finally:
        db.close() 