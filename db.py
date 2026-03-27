import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import text
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Base(DeclarativeBase):
    pass


engine = None
SessionLocal = None


def init_db(database_url: str | None) -> None:
    """
    Initialize database connection with PostgreSQL
    """
    global engine, SessionLocal

    # If no database_url provided, try to get from environment
    if not database_url:
        database_url = os.getenv("DATABASE_URL")
    
    # If still no database_url, raise error (PostgreSQL required)
    if not database_url:
        raise RuntimeError(
            "DATABASE_URL is not set. Please create a .env file with "
            "DATABASE_URL=postgresql://username:password@localhost:1234/database_name"
        )

    try:
        # Ensure PostgreSQL URL format
        if not database_url.startswith('postgresql://'):
            if database_url.startswith('postgres://'):
                database_url = database_url.replace('postgres://', 'postgresql://', 1)
            else:
                raise ValueError(f"Invalid database URL. Expected PostgreSQL URL, got: {database_url}")

        logger.info(f"🔌 Connecting to PostgreSQL database: {database_url.split('@')[0].split('://')[0]}://...@{database_url.split('@')[1] if '@' in database_url else '...'}")

        # Create engine with PostgreSQL-specific optimizations
        engine = create_engine(
            database_url,
            echo=False,  # Set to True for SQL query logging
            future=True,
            pool_size=5,  # Number of connections to maintain in pool
            max_overflow=10,  # Maximum overflow connections
            pool_pre_ping=True,  # Verify connections before using
            pool_recycle=3600,  # Recycle connections after 1 hour
            connect_args={
                'connect_timeout': 10,  # Connection timeout in seconds
                'keepalives': 1,  # Enable TCP keepalive
                'keepalives_idle': 30,  # Idle time before sending keepalive
                'keepalives_interval': 10,  # Interval between keepalives
                'keepalives_count': 5  # Number of keepalives before failure
            }
        )
        
        # Create session factory
        SessionLocal = sessionmaker(
            bind=engine,
            autoflush=False,
            autocommit=False,
            future=True,
            expire_on_commit=False  # Prevent expired object issues
        )

        # Import models and create tables
        from . import models
        Base.metadata.create_all(bind=engine)
        
        # Test connection
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version()")).scalar()
            logger.info(f"✅ Connected to PostgreSQL: {result.split(',')[0]}")
        
    except SQLAlchemyError as e:
        logger.error(f"❌ PostgreSQL connection failed: {e}")
        logger.error("Please check:")
        logger.error("  1. PostgreSQL is running (pg_ctl status)")
        logger.error("  2. Database 'Steward' exists (createdb Steward)")
        logger.error("  3. Username/password is correct")
        logger.error("  4. Port 5432 is correct")
        raise
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}")
        raise


def get_db():
    """
    Get database session for requests
    """
    if SessionLocal is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    
    db = SessionLocal()
    try:
        yield db
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error: {e}")
        raise
    finally:
        db.close()


def check_db_connection():
    """
    Utility function to check database connection
    """
    try:
        with engine.connect() as conn:
            conn.execute("SELECT 1")
        return True, "Database connection is healthy"
    except Exception as e:
        return False, str(e)