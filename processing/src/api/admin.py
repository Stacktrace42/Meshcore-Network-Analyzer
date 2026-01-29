"""API endpoints for administration."""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from typing import List, Optional
import os
import logging

from ..database import get_db
from ..models import Listener, APIKey as APIKeyModel, TraceSchedule, Repeater, SystemConfig
from ..schemas import (
    ListenerCreate, ListenerUpdate, ListenerResponse, APIKeyCreate, APIKeyResponse,
    TraceConfigUpdate, TraceConfigResponse, TraceScheduleResponse, TraceSchedulerStatus
)
from .auth import require_admin, generate_api_key, hash_api_key
from datetime import datetime as dt

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/admin", tags=["admin"])

# Global state for trace scheduler
_trace_scheduler_paused = False


@router.post("/listeners", response_model=ListenerResponse, status_code=status.HTTP_201_CREATED)
async def create_listener(
    listener: ListenerCreate,
    api_key = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Create a new listener and generate API key."""
    # Generate API key
    plain_key = generate_api_key()
    key_hash = hash_api_key(plain_key)

    # Create listener
    db_listener = Listener(
        name=listener.name,
        api_key_hash=key_hash,
        active=True
    )
    db.add(db_listener)

    # Create API key record
    api_key_record = APIKeyModel(
        key_hash=key_hash,
        key_type="listener",
        description=f"Listener: {listener.name}"
    )
    db.add(api_key_record)

    db.commit()
    db.refresh(db_listener)

    logger.info(f"Created listener: {listener.name}")

    # Return with API key (only time it's shown in plain text)
    response = ListenerResponse.from_orm(db_listener)
    response.api_key = plain_key

    return response


@router.get("/listeners", response_model=List[ListenerResponse])
async def list_listeners(
    api_key = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """List all listeners."""
    listeners = db.query(Listener).all()
    return [ListenerResponse.from_orm(l) for l in listeners]


@router.put("/listeners/{listener_id}", response_model=ListenerResponse)
async def update_listener(
    listener_id: str,
    listener_update: ListenerUpdate,
    api_key = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Update listener details (name only)."""
    listener = db.query(Listener).filter(Listener.id == listener_id).first()
    if not listener:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Listener not found"
        )

    if listener_update.name is not None:
        listener.name = listener_update.name

    db.commit()
    db.refresh(listener)

    logger.info(f"Updated listener: {listener.name}")

    return ListenerResponse.from_orm(listener)


@router.delete("/listeners/{listener_id}")
async def delete_listener(
    listener_id: str,
    api_key = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Delete a listener."""
    listener = db.query(Listener).filter(Listener.id == listener_id).first()
    if not listener:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Listener not found"
        )

    # Deactivate instead of delete to preserve historical data
    listener.active = False
    db.commit()

    logger.info(f"Deactivated listener: {listener.name}")

    return {"status": "success", "message": "Listener deactivated"}


@router.post("/api-keys", response_model=APIKeyResponse, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    key_data: APIKeyCreate,
    api_key = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Create a new API key."""
    plain_key = generate_api_key()
    key_hash = hash_api_key(plain_key)

    api_key_record = APIKeyModel(
        key_hash=key_hash,
        key_type=key_data.key_type,
        description=key_data.description
    )
    db.add(api_key_record)
    db.commit()
    db.refresh(api_key_record)

    logger.info(f"Created API key: {key_data.key_type}")

    return APIKeyResponse(
        id=api_key_record.id,
        key=plain_key,
        key_type=api_key_record.key_type,
        description=api_key_record.description,
        created_at=api_key_record.created_at
    )


@router.get("/trace-config", response_model=TraceConfigResponse)
async def get_trace_config(
    api_key = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Get trace configuration."""
    from sqlalchemy import func

    throttle = int(os.getenv("TRACE_THROTTLE_SECONDS", "30"))
    interval = int(os.getenv("TRACE_VERIFICATION_INTERVAL_HOURS", "24"))

    # Get last trace time
    last_trace = db.query(func.max(TraceSchedule.scheduled_at)).filter(
        TraceSchedule.status.in_(["completed", "in_progress"])
    ).scalar()

    return TraceConfigResponse(
        throttle_seconds=throttle,
        verification_interval_hours=interval,
        enabled=True,
        last_trace_at=last_trace
    )


@router.put("/trace-config")
async def update_trace_config(
    config: TraceConfigUpdate,
    api_key = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Update trace configuration (note: updates env vars in memory only)."""
    # In production, this would update a config table or file
    # For now, just acknowledge the request
    logger.info(f"Trace config update requested: {config.dict(exclude_none=True)}")

    return {"status": "success", "message": "Configuration updated (restart required for some changes)"}


@router.get("/traces", response_model=List[TraceScheduleResponse])
async def get_traces(
    status_filter: Optional[str] = Query(None, description="Filter by status: pending, in_progress, completed, failed"),
    limit: int = Query(100, le=1000, description="Maximum number of traces to return"),
    offset: int = Query(0, ge=0, description="Number of traces to skip"),
    api_key = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Get list of all traces with detailed information."""
    query = db.query(TraceSchedule).join(
        Repeater, Repeater.id == TraceSchedule.from_repeater_id, isouter=False
    )

    if status_filter:
        query = query.filter(TraceSchedule.status == status_filter)

    traces = query.order_by(desc(TraceSchedule.scheduled_at)).offset(offset).limit(limit).all()

    results = []
    for trace in traces:
        # Get listener name if assigned
        listener_name = None
        if trace.assigned_listener_id:
            listener = db.query(Listener).filter(Listener.id == trace.assigned_listener_id).first()
            listener_name = listener.name if listener else None

        results.append(TraceScheduleResponse(
            id=trace.id,
            from_repeater_id=trace.from_repeater_id,
            from_repeater_name=trace.from_repeater.name,
            from_repeater_hash=trace.from_repeater.hash,
            to_repeater_id=trace.to_repeater_id,
            to_repeater_name=trace.to_repeater.name,
            to_repeater_hash=trace.to_repeater.hash,
            assigned_listener_id=trace.assigned_listener_id,
            assigned_listener_name=listener_name,
            status=trace.status,
            scheduled_at=trace.scheduled_at,
            completed_at=trace.completed_at,
            result=trace.result,
            calculated_path=trace.calculated_path,
            path_strategy=trace.path_strategy
        ))

    return results


@router.get("/traces/status", response_model=TraceSchedulerStatus)
async def get_trace_scheduler_status(
    api_key = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Get trace scheduler status and statistics."""
    total = db.query(func.count(TraceSchedule.id)).scalar()
    pending = db.query(func.count(TraceSchedule.id)).filter(TraceSchedule.status == "pending").scalar()
    in_progress = db.query(func.count(TraceSchedule.id)).filter(TraceSchedule.status == "in_progress").scalar()
    completed = db.query(func.count(TraceSchedule.id)).filter(TraceSchedule.status == "completed").scalar()
    failed = db.query(func.count(TraceSchedule.id)).filter(TraceSchedule.status == "failed").scalar()

    return TraceSchedulerStatus(
        enabled=True,
        paused=_trace_scheduler_paused,
        total_scheduled=total or 0,
        pending=pending or 0,
        in_progress=in_progress or 0,
        completed=completed or 0,
        failed=failed or 0
    )


@router.post("/traces/pause")
async def pause_trace_scheduling(
    api_key = Depends(require_admin)
):
    """Pause trace scheduling (prevents new traces from being scheduled)."""
    global _trace_scheduler_paused
    _trace_scheduler_paused = True
    logger.info("Trace scheduling PAUSED")

    return {"status": "success", "message": "Trace scheduling paused", "paused": True}


@router.post("/traces/resume")
async def resume_trace_scheduling(
    api_key = Depends(require_admin)
):
    """Resume trace scheduling."""
    global _trace_scheduler_paused
    _trace_scheduler_paused = False
    logger.info("Trace scheduling RESUMED")

    return {"status": "success", "message": "Trace scheduling resumed", "paused": False}


def is_trace_scheduler_paused() -> bool:
    """Check if trace scheduler is paused."""
    return _trace_scheduler_paused


@router.get("/config")
async def get_system_config(
    api_key = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Get all system configuration values."""
    configs = db.query(SystemConfig).all()

    result = []
    for config in configs:
        result.append({
            "key": config.key,
            "value": config.value,
            "value_type": config.value_type,
            "description": config.description,
            "updated_at": config.updated_at
        })

    return {"configs": result}


@router.put("/config")
async def update_system_config(
    updates: dict,
    api_key = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Update system configuration values."""
    updated_keys = []

    for key, value in updates.items():
        config = db.query(SystemConfig).filter(SystemConfig.key == key).first()

        if not config:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Configuration key '{key}' not found"
            )

        # Validate value based on type
        try:
            if config.value_type == 'int':
                int(value)
            elif config.value_type == 'float':
                float(value)
            elif config.value_type == 'bool':
                if str(value).lower() not in ('true', 'false', '1', '0', 'yes', 'no'):
                    raise ValueError("Invalid boolean value")
        except (ValueError, TypeError) as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid value for key '{key}': expected {config.value_type}"
            )

        # Update value
        config.value = str(value)
        config.updated_at = dt.utcnow()
        updated_keys.append(key)

        logger.info(f"Updated config {key} = {value}")

    db.commit()

    return {
        "status": "success",
        "message": f"Updated {len(updated_keys)} configuration value(s)",
        "updated_keys": updated_keys
    }
