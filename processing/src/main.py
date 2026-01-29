"""Main FastAPI application for Meshcore Network Analyzer Processing component."""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
import logging
import os

from .database import init_db, SessionLocal
from .api import listeners, visualization, admin
from .graph_builder import build_graph, triangulate_repeater_positions
from .trace_scheduler import TraceSchedulerService
from .models import APIKey
from .api.auth import hash_api_key

# Configure logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Background scheduler
scheduler = AsyncIOScheduler()


def rebuild_graph_job():
    """Background job to rebuild the graph."""
    logger.info("Starting graph rebuild job")
    db = SessionLocal()
    try:
        build_graph(db)
        logger.info("Graph rebuild completed")
        # Run position triangulation after graph rebuild
        triangulate_repeater_positions(db)
        logger.info("Position triangulation completed")
    except Exception as e:
        logger.error(f"Error rebuilding graph: {e}")
    finally:
        db.close()


def schedule_traces_job():
    """Background job to schedule new traces."""
    # Check if trace scheduling is paused
    from .api.admin import is_trace_scheduler_paused
    if is_trace_scheduler_paused():
        logger.info("Trace scheduling is PAUSED, skipping this cycle")
        return

    logger.info("Starting trace scheduling job")
    db = SessionLocal()
    try:
        scheduler_service = TraceSchedulerService(db)
        scheduler_service.schedule_traces_for_week()
        logger.info("Trace scheduling completed")
    except Exception as e:
        logger.error(f"Error scheduling traces: {e}")
    finally:
        db.close()


def cleanup_job():
    """Background job to clean up old data."""
    logger.info("Starting cleanup job")
    db = SessionLocal()
    try:
        scheduler_service = TraceSchedulerService(db)
        scheduler_service.cleanup_old_traces(days_old=30)
        logger.info("Cleanup completed")
    except Exception as e:
        logger.error(f"Error during cleanup: {e}")
    finally:
        db.close()


def init_admin_key():
    """Initialize admin API key from environment."""
    admin_key = os.getenv("ADMIN_API_KEY")
    if not admin_key:
        logger.warning("ADMIN_API_KEY not set in environment")
        return

    # Truncate key if too long for bcrypt (max 72 bytes)
    if len(admin_key.encode()) > 72:
        admin_key = admin_key[:60]  # Use first 60 characters to be safe
        logger.warning("Admin key truncated to fit bcrypt requirements")

    db = SessionLocal()
    try:
        # Check if admin key already exists
        existing_key = db.query(APIKey).filter(APIKey.key_type == "admin").first()
        if existing_key:
            logger.info("Admin API key already exists")
            return

        # Create admin key
        key_hash = hash_api_key(admin_key)
        api_key = APIKey(
            key_hash=key_hash,
            key_type="admin",
            description="Initial admin key from environment",
            active=True
        )
        db.add(api_key)
        db.commit()
        logger.info("Admin API key created successfully")
    except Exception as e:
        logger.error(f"Error creating admin API key: {e}")
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("Starting Meshcore Network Analyzer Processing Service")

    # Initialize database
    init_db()
    logger.info("Database initialized")

    # Initialize admin API key
    init_admin_key()

    # Start background scheduler
    graph_rebuild_minutes = int(os.getenv("GRAPH_REBUILD_INTERVAL_MINUTES", "5"))
    scheduler.add_job(
        rebuild_graph_job,
        IntervalTrigger(minutes=graph_rebuild_minutes),
        id="rebuild_graph",
        replace_existing=True
    )

    scheduler.add_job(
        schedule_traces_job,
        IntervalTrigger(minutes=1),
        id="schedule_traces",
        replace_existing=True
    )

    scheduler.add_job(
        cleanup_job,
        CronTrigger(hour=0, minute=0),  # Daily at midnight
        id="cleanup",
        replace_existing=True
    )

    scheduler.start()
    logger.info("Background scheduler started")

    yield

    # Shutdown
    scheduler.shutdown()
    logger.info("Shutting down")


# Create FastAPI app
app = FastAPI(
    title="Meshcore Network Analyzer API",
    description="Processing component for Meshcore network traffic analysis and visualization",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(listeners.router)
app.include_router(visualization.router)
app.include_router(admin.router)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "Meshcore Network Analyzer - Processing",
        "version": "1.0.0",
        "status": "operational"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    from sqlalchemy import text
    db = SessionLocal()
    try:
        # Test database connection
        db.execute(text("SELECT 1"))
        db_status = "healthy"
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        db_status = "unhealthy"
        raise HTTPException(status_code=503, detail="Database unavailable")
    finally:
        db.close()

    return {
        "status": "healthy",
        "database": db_status,
        "scheduler": "running" if scheduler.running else "stopped"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
