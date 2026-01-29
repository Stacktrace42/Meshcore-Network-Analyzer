#!/usr/bin/env python3
"""
Database initialization script for Meshcore Network Analyzer.
Runs automatically on container startup to initialize database schema,
seed configuration, and create initial API keys.
"""
import os
import sys
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Import models and database
sys.path.insert(0, os.path.dirname(__file__))
from src.database import Base
from src.models import SystemConfig, APIKey, Listener
from src.api.auth import hash_api_key, generate_api_key


def wait_for_db(database_url: str, max_retries=30):
    """Wait for database to be available."""
    import time
    engine = create_engine(database_url)
    for i in range(max_retries):
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            logger.info("Database is ready")
            return True
        except Exception as e:
            if i < max_retries - 1:
                logger.info(f"Waiting for database... ({i+1}/{max_retries})")
                time.sleep(2)
            else:
                logger.error(f"Database not available after {max_retries} attempts")
                raise
    return False


def init_database(database_url: str):
    """Initialize database tables if they don't exist."""
    engine = create_engine(database_url)

    # Check if tables already exist
    with engine.connect() as conn:
        result = conn.execute(text(
            "SELECT COUNT(*) FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_name = 'system_config'"
        ))
        table_exists = result.scalar() > 0

    if not table_exists:
        logger.info("Creating database tables...")
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully")
    else:
        logger.info("Database tables already exist")

    return engine


def seed_system_config(session):
    """Seed initial system configuration if not present."""
    config_count = session.query(SystemConfig).count()

    if config_count == 0:
        logger.info("Seeding system configuration...")
        configs = [
            SystemConfig(
                key="trace_throttle_seconds",
                value="30",
                value_type="int",
                description="Seconds between scheduled trace commands",
                updated_at=datetime.utcnow()
            ),
            SystemConfig(
                key="trace_verification_interval_hours",
                value="24",
                value_type="int",
                description="Hours before re-verifying an edge with a new trace",
                updated_at=datetime.utcnow()
            ),
            SystemConfig(
                key="max_pending_traces_per_listener",
                value="50",
                value_type="int",
                description="Maximum number of pending traces per listener",
                updated_at=datetime.utcnow()
            )
        ]
        for config in configs:
            session.add(config)
        session.commit()
        logger.info(f"Seeded {len(configs)} configuration values")
    else:
        logger.info(f"System configuration already exists ({config_count} values)")


def create_admin_key(session, admin_key: str):
    """Create admin API key if not present."""
    existing_admin = session.query(APIKey).filter(APIKey.key_type == "admin").first()

    if not existing_admin:
        logger.info("Creating admin API key...")
        # Truncate key if too long for bcrypt
        if len(admin_key.encode()) > 72:
            admin_key = admin_key[:60]
            logger.warning("Admin key truncated to fit bcrypt requirements")

        key_hash = hash_api_key(admin_key)
        api_key = APIKey(
            key_hash=key_hash,
            key_type="admin",
            description="Initial admin key from environment",
            active=True
        )
        session.add(api_key)
        session.commit()
        logger.info("Admin API key created successfully")
    else:
        logger.info("Admin API key already exists")


def create_listener_if_needed(session):
    """Create listener and API key if environment variables are set."""
    # Check for listener initialization env vars
    listener_name = os.getenv("INIT_LISTENER_NAME")
    listener_api_key = os.getenv("INIT_LISTENER_API_KEY")

    # Both must be set to auto-create listener
    if not all([listener_name, listener_api_key]):
        logger.info("Listener auto-creation skipped (env vars not set)")
        return

    # Check if listener already exists with this name
    existing_listener = session.query(Listener).filter(Listener.name == listener_name).first()

    if existing_listener:
        logger.info(f"Listener '{listener_name}' already exists (ID: {existing_listener.id})")
        return

    logger.info(f"Creating listener: {listener_name}...")

    # Hash the API key
    key_hash = hash_api_key(listener_api_key)

    try:
        # Create API key
        api_key_record = APIKey(
            key_hash=key_hash,
            key_type="listener",
            description=f"Auto-created: {listener_name}",
            active=True
        )
        session.add(api_key_record)

        # Create listener
        listener = Listener(
            name=listener_name,
            api_key_hash=key_hash,
            active=True
        )
        session.add(listener)

        session.commit()
        logger.info(f"Listener '{listener_name}' created successfully (ID: {listener.id})")
        logger.info(f"Remember to set LISTENER_ID={listener.id} in your .env file")
    except Exception as e:
        session.rollback()
        logger.error(f"Failed to create listener: {e}")
        raise


def main():
    """Main initialization routine."""
    logger.info("Starting database initialization...")

    # Get database URL
    database_url = os.getenv(
        "DATABASE_URL",
        "postgresql://meshcore:password@postgres:5432/meshcore_analyzer"
    )

    try:
        # Wait for database
        wait_for_db(database_url)

        # Initialize database tables
        engine = init_database(database_url)

        # Create session
        SessionLocal = sessionmaker(bind=engine)
        session = SessionLocal()

        try:
            # Seed system configuration
            seed_system_config(session)

            # Create admin API key
            admin_key = os.getenv("ADMIN_API_KEY")
            if admin_key:
                create_admin_key(session, admin_key)
            else:
                logger.warning("ADMIN_API_KEY not set in environment")

            # Create listener if env vars are set
            create_listener_if_needed(session)

            logger.info("Database initialization completed successfully!")
            return 0

        finally:
            session.close()

    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
