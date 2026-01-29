"""API endpoints for Listener components."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime, timedelta
import logging

from ..database import get_db
from ..models import Listener, Path, Repeater, TraceSchedule, APIKey
from ..schemas import (
    ListenerDataSubmission, PendingTraceResponse, TraceResultSubmission
)
from .auth import require_listener

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/listener", tags=["listener"])


@router.post("/data", status_code=status.HTTP_201_CREATED)
async def submit_data(
    submission: ListenerDataSubmission,
    api_key: APIKey = Depends(require_listener),
    db: Session = Depends(get_db)
):
    """
    Receive data from listener components.

    Data types:
    - path: Observed packet path with SNR/RSSI
    - contact: Repeater advertisement/contact info
    - trace_result: Result from trace command execution
    """
    # Verify listener exists and update last_seen
    listener = db.query(Listener).filter(Listener.id == submission.listener_id).first()
    if not listener:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Listener not found"
        )

    listener.last_seen = datetime.utcnow()

    # Update GPS if provided
    if submission.listener_gps:
        listener.gps_lat = submission.listener_gps.lat
        listener.gps_lon = submission.listener_gps.lon

    # Process data based on type
    if submission.data_type == "path":
        await _process_path_data(submission, listener, db)
    elif submission.data_type == "contact":
        await _process_contact_data(submission, db)
    elif submission.data_type == "trace_result":
        await _process_trace_result(submission, db)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown data type: {submission.data_type}"
        )

    db.commit()

    return {"status": "success", "message": "Data received"}


async def _process_path_data(submission: ListenerDataSubmission, listener: Listener, db: Session):
    """Process path observation data."""
    data = submission.data

    # Calculate ISO week number for aggregation
    week_number = submission.timestamp.isocalendar()[1]

    # Create path record
    path = Path(
        listener_id=listener.id,
        source_hash=data.get("source_hash"),
        dest_hash=data.get("dest_hash"),
        path=data.get("path", []),
        snr=data.get("snr"),
        rssi=data.get("rssi"),
        timestamp=submission.timestamp,
        week_number=week_number
    )
    db.add(path)

    logger.info(f"Recorded path: {data.get('path')} with SNR {data.get('snr')}")


async def _process_contact_data(submission: ListenerDataSubmission, db: Session):
    """Process repeater contact/advertisement data."""
    data = submission.data

    # Only process contacts marked as repeaters (type == 2)
    if not data.get("is_repeater", False):
        logger.debug(f"Skipping non-repeater contact: {data.get('name')} ({data.get('hash')})")
        return

    # Check if repeater exists
    repeater = db.query(Repeater).filter(Repeater.hash == data.get("hash")).first()

    if repeater:
        # Update existing repeater
        repeater.last_seen = submission.timestamp
        if data.get("name"):
            repeater.name = data.get("name")
        if data.get("gps_lat") is not None:
            repeater.gps_lat = data.get("gps_lat")
        if data.get("gps_lon") is not None:
            repeater.gps_lon = data.get("gps_lon")
        if data.get("public_key"):
            # Convert hex string to bytes
            repeater.public_key = bytes.fromhex(data.get("public_key").replace("0x", ""))
    else:
        # Create new repeater
        public_key = None
        if data.get("public_key"):
            public_key = bytes.fromhex(data.get("public_key").replace("0x", ""))

        repeater = Repeater(
            public_key=public_key,
            hash=data.get("hash"),
            name=data.get("name"),
            gps_lat=data.get("gps_lat"),
            gps_lon=data.get("gps_lon"),
            first_seen=submission.timestamp,
            last_seen=submission.timestamp
        )
        db.add(repeater)

    logger.info(f"Processed contact for repeater {data.get('hash')}: {data.get('name')}")


async def _process_trace_result(submission: ListenerDataSubmission, db: Session):
    """Process trace command result."""
    data = submission.data
    trace_id = data.get("trace_id")

    trace = db.query(TraceSchedule).filter(TraceSchedule.id == trace_id).first()
    if not trace:
        logger.warning(f"Trace not found: {trace_id}")
        return

    trace.status = "completed" if data.get("success") else "failed"
    trace.completed_at = submission.timestamp
    trace.result = data

    logger.info(f"Trace {trace_id} completed: {data.get('success')}")


@router.get("/traces/pending", response_model=List[PendingTraceResponse])
async def get_pending_traces(
    api_key: APIKey = Depends(require_listener),
    db: Session = Depends(get_db)
):
    """
    Get pending trace commands for this listener.

    Returns traces that are:
    - Status: pending or in_progress (for retry)
    - Assigned to a listener (or can be claimed)
    """
    # Get traces that are pending and not yet completed
    traces = db.query(TraceSchedule).filter(
        TraceSchedule.status.in_(["pending", "in_progress"]),
        TraceSchedule.scheduled_at <= datetime.utcnow()
    ).limit(10).all()

    response = []
    for trace in traces:
        response.append(PendingTraceResponse(
            id=trace.id,
            from_repeater_hash=trace.from_repeater.hash,
            to_repeater_hash=trace.to_repeater.hash,
            from_repeater_public_key=trace.from_repeater.public_key.hex() if trace.from_repeater.public_key else None,
            to_repeater_public_key=trace.to_repeater.public_key.hex() if trace.to_repeater.public_key else None,
            scheduled_at=trace.scheduled_at
        ))

    return response


@router.post("/traces/{trace_id}/claim")
async def claim_trace(
    trace_id: str,
    listener_id: str,
    api_key: APIKey = Depends(require_listener),
    db: Session = Depends(get_db)
):
    """Claim a trace command for execution."""
    trace = db.query(TraceSchedule).filter(TraceSchedule.id == trace_id).first()
    if not trace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Trace not found"
        )

    if trace.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Trace already claimed or completed"
        )

    trace.status = "in_progress"
    trace.assigned_listener_id = listener_id
    db.commit()

    return {"status": "success", "message": "Trace claimed"}


@router.post("/traces/{trace_id}/result")
async def submit_trace_result(
    trace_id: str,
    result: TraceResultSubmission,
    api_key: APIKey = Depends(require_listener),
    db: Session = Depends(get_db)
):
    """Submit trace command result."""
    trace = db.query(TraceSchedule).filter(TraceSchedule.id == trace_id).first()
    if not trace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Trace not found"
        )

    trace.status = "completed" if result.success else "failed"
    trace.completed_at = datetime.utcnow()

    # Convert result to dict and ensure UUIDs are serialized as strings
    result_dict = result.dict()
    result_dict["trace_id"] = str(result_dict["trace_id"])
    trace.result = result_dict

    # If successful, create a Path entry and update GraphEdge
    if result.success and result.path and len(result.path) > 1:
        # Create Path entry for this trace result
        from ..models import Path
        week_number = datetime.utcnow().isocalendar()[1]

        path_entry = Path(
            listener_id=trace.assigned_listener_id,
            source_hash=result.path[0] if len(result.path) > 0 else None,
            dest_hash=result.path[-1] if len(result.path) > 0 else None,
            path=result.path,
            snr=result.snr_values[0] if result.snr_values and len(result.snr_values) > 0 else None,
            rssi=None,  # Trace doesn't provide RSSI
            timestamp=datetime.utcnow(),
            week_number=week_number
        )
        db.add(path_entry)

        # Update GraphEdge with trace result (if edge exists for from→to)
        if result.formatted_path:
            from ..models import GraphEdge
            edge = db.query(GraphEdge).filter(
                GraphEdge.from_repeater_id == trace.from_repeater_id,
                GraphEdge.to_repeater_id == trace.to_repeater_id,
                GraphEdge.week_number == week_number
            ).first()

            if edge:
                edge.last_trace_at = datetime.utcnow()
                edge.last_trace_path = result.formatted_path

    db.commit()

    logger.info(f"Trace {trace_id} result submitted: {result.success}")

    return {"status": "success", "message": "Trace result recorded"}
