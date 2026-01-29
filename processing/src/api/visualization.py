"""API endpoints for Visualization component."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from typing import Optional, List
from datetime import datetime

from ..database import get_db
from ..models import Repeater, GraphEdge, Path, TraceSchedule, Listener
from ..schemas import (
    GraphResponse, RepeaterResponse, GraphEdgeResponse, SystemStats,
    TraceScheduleResponse, TraceSchedulerStatus
)
from .auth import require_visualization

router = APIRouter(prefix="/api/v1", tags=["visualization"])


@router.get("/graph", response_model=GraphResponse)
async def get_graph(
    week_number: Optional[int] = Query(None, description="ISO week number, defaults to current week"),
    api_key = Depends(require_visualization),
    db: Session = Depends(get_db)
):
    """
    Get network graph for visualization.

    Returns all repeaters and edges for the specified week.
    """
    if week_number is None:
        week_number = datetime.utcnow().isocalendar()[1]

    # Get all repeaters
    repeaters = db.query(Repeater).all()

    # Get edges for the specified week
    edges = db.query(GraphEdge).filter(
        GraphEdge.week_number == week_number
    ).all()

    # For each edge, find a sample path that demonstrates the connection
    edge_responses = []
    for edge in edges:
        # Find the from and to repeaters
        from_repeater = db.query(Repeater).filter(Repeater.id == edge.from_repeater_id).first()
        to_repeater = db.query(Repeater).filter(Repeater.id == edge.to_repeater_id).first()

        if not from_repeater or not to_repeater:
            continue

        # Find a path that contains this edge (A->B as consecutive hops)
        # An edge A->B means A immediately followed by B in the path array
        sample_path = None
        sample_path_record = None

        # Get paths from this week and check if they contain the edge
        all_paths = db.query(Path).filter(Path.week_number == week_number).limit(200).all()
        for p in all_paths:
            if not p.path or not isinstance(p.path, list):
                continue

            # Check if path contains both hashes as consecutive elements
            try:
                # Look for the edge A->B in the path
                for i in range(len(p.path) - 1):
                    if p.path[i] == from_repeater.hash and p.path[i + 1] == to_repeater.hash:
                        # Found the edge! Use this path as the sample
                        sample_path = p.path
                        sample_path_record = p
                        break

                if sample_path:
                    break

            except (ValueError, AttributeError, IndexError):
                continue

        # Create response with sample path
        edge_dict = {
            "id": edge.id,
            "from_repeater_id": edge.from_repeater_id,
            "to_repeater_id": edge.to_repeater_id,
            "message_count": edge.message_count,
            "avg_snr": edge.avg_snr,
            "week_number": edge.week_number,
            "last_updated": edge.last_updated,
            "sample_path": sample_path
        }
        edge_responses.append(GraphEdgeResponse(**edge_dict))

    return GraphResponse(
        repeaters=[RepeaterResponse.model_validate(r) for r in repeaters],
        edges=edge_responses
    )


@router.get("/repeaters", response_model=list[RepeaterResponse])
async def get_repeaters(
    api_key = Depends(require_visualization),
    db: Session = Depends(get_db)
):
    """Get all repeaters in the network."""
    repeaters = db.query(Repeater).all()
    return [RepeaterResponse.model_validate(r) for r in repeaters]


@router.get("/repeaters/{repeater_id}", response_model=RepeaterResponse)
async def get_repeater(
    repeater_id: str,
    api_key = Depends(require_visualization),
    db: Session = Depends(get_db)
):
    """Get details for a specific repeater."""
    repeater = db.query(Repeater).filter(Repeater.id == repeater_id).first()
    if not repeater:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Repeater not found")

    return RepeaterResponse.model_validate(repeater)


@router.get("/stats", response_model=SystemStats)
async def get_stats(
    api_key = Depends(require_visualization),
    db: Session = Depends(get_db)
):
    """Get system statistics."""
    from ..models import Listener, TraceSchedule

    current_week = datetime.utcnow().isocalendar()[1]

    # Count totals
    total_repeaters = db.query(func.count(Repeater.id)).scalar()
    total_listeners = db.query(func.count(Listener.id)).scalar()
    active_listeners = db.query(func.count(Listener.id)).filter(Listener.active == True).scalar()
    total_paths = db.query(func.count(Path.id)).scalar()
    paths_this_week = db.query(func.count(Path.id)).filter(Path.week_number == current_week).scalar()

    # Trace statistics
    total_traces = db.query(func.count(TraceSchedule.id)).scalar()
    pending_traces = db.query(func.count(TraceSchedule.id)).filter(TraceSchedule.status == "pending").scalar()
    completed_traces = db.query(func.count(TraceSchedule.id)).filter(TraceSchedule.status == "completed").scalar()
    failed_traces = db.query(func.count(TraceSchedule.id)).filter(TraceSchedule.status == "failed").scalar()

    # Last graph update
    last_edge_update = db.query(func.max(GraphEdge.last_updated)).scalar()

    return SystemStats(
        total_repeaters=total_repeaters or 0,
        total_listeners=total_listeners or 0,
        active_listeners=active_listeners or 0,
        total_paths=total_paths or 0,
        paths_this_week=paths_this_week or 0,
        total_traces=total_traces or 0,
        pending_traces=pending_traces or 0,
        completed_traces=completed_traces or 0,
        failed_traces=failed_traces or 0,
        last_graph_update=last_edge_update
    )


@router.get("/traces", response_model=List[TraceScheduleResponse])
async def get_traces(
    status_filter: Optional[str] = Query(None, description="Filter by status: pending, in_progress, completed, failed"),
    limit: int = Query(100, le=1000, description="Maximum number of traces to return"),
    offset: int = Query(0, ge=0, description="Number of traces to skip"),
    api_key = Depends(require_visualization),
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
            result=trace.result
        ))

    return results


@router.get("/traces/status", response_model=TraceSchedulerStatus)
async def get_trace_scheduler_status(
    api_key = Depends(require_visualization),
    db: Session = Depends(get_db)
):
    """Get trace scheduler status and statistics."""
    from .admin import is_trace_scheduler_paused

    total = db.query(func.count(TraceSchedule.id)).scalar()
    pending = db.query(func.count(TraceSchedule.id)).filter(TraceSchedule.status == "pending").scalar()
    in_progress = db.query(func.count(TraceSchedule.id)).filter(TraceSchedule.status == "in_progress").scalar()
    completed = db.query(func.count(TraceSchedule.id)).filter(TraceSchedule.status == "completed").scalar()
    failed = db.query(func.count(TraceSchedule.id)).filter(TraceSchedule.status == "failed").scalar()

    return TraceSchedulerStatus(
        enabled=True,
        paused=is_trace_scheduler_paused(),
        total_scheduled=total or 0,
        pending=pending or 0,
        in_progress=in_progress or 0,
        completed=completed or 0,
        failed=failed or 0
    )
