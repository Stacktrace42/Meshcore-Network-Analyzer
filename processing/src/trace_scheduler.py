"""Trace scheduling for path verification."""
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import Optional
import logging
import os

from .models import TraceSchedule, GraphEdge, Repeater, Listener, SystemConfig, Path
from .repeater_resolver import calculate_distance

logger = logging.getLogger(__name__)


class TraceSchedulerService:
    """Service for scheduling and managing trace commands."""

    def __init__(self, db: Session):
        self.db = db
        self.enabled = True
        self._load_config()

    def _load_config(self):
        """Load configuration from database with fallback to environment variables."""
        # Helper to get config value
        def get_config(key: str, default: str, value_type: str = 'int'):
            config = self.db.query(SystemConfig).filter(SystemConfig.key == key).first()
            if config:
                if value_type == 'int':
                    return int(config.value)
                elif value_type == 'float':
                    return float(config.value)
                elif value_type == 'bool':
                    return config.value.lower() in ('true', '1', 'yes')
                return config.value
            # Fallback to environment variable
            env_value = os.getenv(key.upper(), default)
            if value_type == 'int':
                return int(env_value)
            elif value_type == 'float':
                return float(env_value)
            elif value_type == 'bool':
                return env_value.lower() in ('true', '1', 'yes')
            return env_value

        self.throttle_seconds = get_config("trace_throttle_seconds", "30", "int")
        self.verification_interval_hours = get_config("trace_verification_interval_hours", "24", "int")
        self.max_pending_per_listener = get_config("max_pending_traces_per_listener", "50", "int")

    def schedule_traces_for_week(self, week_number: int = None):
        """
        Schedule traces for all edges in the graph.

        Traces are scheduled once per day with 30-second throttle between them.
        """
        if not self.enabled:
            logger.info("Trace scheduling is disabled")
            return

        if week_number is None:
            week_number = datetime.utcnow().isocalendar()[1]

        # 1. Clean up stale in_progress traces (over 5 minutes old)
        stale_cutoff = datetime.utcnow() - timedelta(minutes=5)
        stale_count = self.db.query(TraceSchedule).filter(
            TraceSchedule.status == "in_progress",
            TraceSchedule.scheduled_at < stale_cutoff
        ).update({
            "status": "failed",
            "completed_at": datetime.utcnow(),
            "result": {"error": "Timeout - stale trace"}
        })

        # 2. Clean up very old pending traces (over 1 hour old)
        old_pending_cutoff = datetime.utcnow() - timedelta(hours=1)
        old_pending_count = self.db.query(TraceSchedule).filter(
            TraceSchedule.status == "pending",
            TraceSchedule.scheduled_at < old_pending_cutoff
        ).update({
            "status": "failed",
            "completed_at": datetime.utcnow(),
            "result": {"error": "Expired - not executed in time"}
        })

        # 3. Delete old completed/failed traces (over 7 days)
        old_completed_cutoff = datetime.utcnow() - timedelta(days=7)
        deleted_count = self.db.query(TraceSchedule).filter(
            TraceSchedule.status.in_(["completed", "failed"]),
            TraceSchedule.completed_at < old_completed_cutoff
        ).delete()

        if stale_count or old_pending_count or deleted_count:
            self.db.commit()
            logger.info(
                f"Cleanup: {stale_count} stale, {old_pending_count} expired pending, "
                f"{deleted_count} old completed/failed"
            )

        # Get all edges for this week
        edges = self.db.query(GraphEdge).filter(
            GraphEdge.week_number == week_number
        ).all()

        if not edges:
            logger.info(f"No edges found for week {week_number}")
            return

        logger.info(f"Scheduling traces for {len(edges)} edges")

        # Check when last trace was scheduled
        last_trace = self.db.query(TraceSchedule).order_by(
            TraceSchedule.scheduled_at.desc()
        ).first()

        if last_trace:
            next_schedule_time = last_trace.scheduled_at + timedelta(seconds=self.throttle_seconds)
        else:
            next_schedule_time = datetime.utcnow()

        # Get count of pending traces per listener to enforce limits
        from sqlalchemy import func
        pending_counts = dict(
            self.db.query(
                TraceSchedule.assigned_listener_id,
                func.count(TraceSchedule.id)
            )
            .filter(TraceSchedule.status == "pending")
            .group_by(TraceSchedule.assigned_listener_id)
            .all()
        )

        scheduled_count = 0
        skipped_duplicate = 0
        skipped_listener_limit = 0

        for edge in edges:
            # Check if this edge already has a pending, in_progress, or recent trace
            existing_trace = self.db.query(TraceSchedule).filter(
                TraceSchedule.from_repeater_id == edge.from_repeater_id,
                TraceSchedule.to_repeater_id == edge.to_repeater_id
            ).filter(
                (TraceSchedule.status.in_(["pending", "in_progress"])) |
                (
                    (TraceSchedule.status.in_(["completed", "failed"])) &
                    (TraceSchedule.scheduled_at >= datetime.utcnow() - timedelta(hours=self.verification_interval_hours))
                )
            ).first()

            if existing_trace:
                skipped_duplicate += 1
                continue  # Skip, already has pending/in_progress or recent trace

            # Select best listener for this trace
            assigned_listener = self._select_listener_for_trace(
                edge.from_repeater,
                edge.to_repeater
            )

            if not assigned_listener:
                continue  # No listener available

            # Check if listener has too many pending traces
            listener_pending = pending_counts.get(assigned_listener.id, 0)
            if listener_pending >= self.max_pending_per_listener:
                skipped_listener_limit += 1
                continue  # Listener at capacity

            # Create trace schedule
            trace = TraceSchedule(
                from_repeater_id=edge.from_repeater_id,
                to_repeater_id=edge.to_repeater_id,
                assigned_listener_id=assigned_listener.id,
                status="pending",
                scheduled_at=next_schedule_time
            )
            self.db.add(trace)

            # Update pending count for this listener
            pending_counts[assigned_listener.id] = listener_pending + 1

            next_schedule_time += timedelta(seconds=self.throttle_seconds)
            scheduled_count += 1

        self.db.commit()
        logger.info(
            f"Scheduled {scheduled_count} new traces "
            f"(skipped: {skipped_duplicate} duplicates, {skipped_listener_limit} at capacity)"
        )

    def _select_listener_for_trace(
        self,
        from_repeater: Repeater,
        to_repeater: Repeater
    ) -> Optional[Listener]:
        """
        Select the best listener to execute a trace.

        Choose the listener closest to the starting repeater.
        """
        # Get all active listeners with GPS coordinates
        listeners = self.db.query(Listener).filter(
            Listener.active == True,
            Listener.gps_lat.isnot(None),
            Listener.gps_lon.isnot(None)
        ).all()

        if not listeners:
            logger.warning("No active listeners with GPS found")
            return None

        if not from_repeater.gps_lat or not from_repeater.gps_lon:
            # No GPS for repeater, just return first listener
            return listeners[0]

        # Find closest listener
        best_listener = None
        min_distance = float('inf')

        for listener in listeners:
            # Create a temporary repeater object to use distance calculation
            listener_as_repeater = Repeater(
                gps_lat=listener.gps_lat,
                gps_lon=listener.gps_lon
            )

            distance = calculate_distance(from_repeater, listener_as_repeater)

            if distance is not None and distance < min_distance:
                min_distance = distance
                best_listener = listener

        if best_listener:
            logger.info(
                f"Selected listener {best_listener.name} "
                f"(distance: {min_distance:.2f} km) for trace"
            )

        return best_listener or listeners[0]

    def get_pending_traces_for_listener(
        self,
        listener_id: str,
        limit: int = 10
    ) -> list:
        """Get pending traces for a specific listener."""
        traces = self.db.query(TraceSchedule).filter(
            TraceSchedule.assigned_listener_id == listener_id,
            TraceSchedule.status == "pending",
            TraceSchedule.scheduled_at <= datetime.utcnow()
        ).limit(limit).all()

        return traces

    def cleanup_old_traces(self, days_old: int = 30):
        """Clean up old completed traces."""
        cutoff_date = datetime.utcnow() - timedelta(days=days_old)

        deleted = self.db.query(TraceSchedule).filter(
            TraceSchedule.status.in_(["completed", "failed"]),
            TraceSchedule.completed_at < cutoff_date
        ).delete()

        self.db.commit()
        logger.info(f"Cleaned up {deleted} old traces")

    def extract_traces_from_paths(self, week_number: int = None):
        """
        Extract viable trace candidates from captured paths.

        Analyzes 2-hop and 3-hop segments from observed paths and generates
        loop traces for verification.
        """
        if week_number is None:
            week_number = datetime.utcnow().isocalendar()[1]

        # Get all paths from current week
        paths = self.db.query(Path).filter(
            Path.week_number == week_number
        ).all()

        if not paths:
            logger.info(f"No paths found for week {week_number}")
            return []

        logger.info(f"Extracting traces from {len(paths)} paths")

        trace_candidates = []
        seen_paths = set()

        for path_record in paths:
            path = path_record.path
            if not path or len(path) < 2:
                continue

            # Extract 2-hop and 3-hop segments
            for i in range(len(path) - 1):
                # 2-hop segment: path[i] -> path[i+1]
                segment = path[i:i+2]
                if len(segment) == 2:
                    trace_candidate = self._create_loop_trace_from_segment(segment, seen_paths)
                    if trace_candidate:
                        trace_candidates.append(trace_candidate)

                # 3-hop segment: path[i] -> path[i+1] -> path[i+2]
                if i < len(path) - 2:
                    segment = path[i:i+3]
                    trace_candidate = self._create_loop_trace_from_segment(segment, seen_paths)
                    if trace_candidate:
                        trace_candidates.append(trace_candidate)

        logger.info(f"Extracted {len(trace_candidates)} unique trace candidates")
        return trace_candidates

    def _create_loop_trace_from_segment(self, segment: list, seen_paths: set) -> Optional[dict]:
        """
        Create a loop trace from a path segment.

        For segment [A, B] or [A, B, C], creates loop: Gateway -> ... -> A -> Gateway
        """
        if len(segment) < 2:
            return None

        # Create normalized path hash for deduplication
        path_hash = tuple(sorted(segment))
        if path_hash in seen_paths:
            return None
        seen_paths.add(path_hash)

        # Get repeaters for the segment
        from_hash = segment[0]
        to_hash = segment[-1]

        from_repeater = self.db.query(Repeater).filter(Repeater.hash == from_hash).first()
        to_repeater = self.db.query(Repeater).filter(Repeater.hash == to_hash).first()

        if not from_repeater or not to_repeater:
            return None

        # Find best gateway repeater (closest to any active listener)
        gateway = self._find_best_gateway_for_segment(segment)
        if not gateway:
            return None

        # Build loop trace path
        # For segment [A, B]: Gateway -> B -> A -> Gateway
        # For segment [A, B, C]: Gateway -> C -> B -> A -> Gateway
        calculated_path = [gateway.hash] + list(reversed(segment)) + [gateway.hash]

        # Check if this trace already exists
        existing = self._check_existing_trace(from_repeater.id, to_repeater.id)
        if existing:
            return None

        return {
            "from_repeater_id": from_repeater.id,
            "to_repeater_id": to_repeater.id,
            "calculated_path": calculated_path,
            "path_strategy": "loop",
            "gateway_hash": gateway.hash
        }

    def _find_best_gateway_for_segment(self, segment: list) -> Optional[Repeater]:
        """Find the best gateway repeater for a path segment."""
        # Get all active listeners
        listeners = self.db.query(Listener).filter(
            Listener.active == True,
            Listener.gps_lat.isnot(None),
            Listener.gps_lon.isnot(None)
        ).all()

        if not listeners:
            return None

        # Get all repeaters in the segment
        segment_repeaters = self.db.query(Repeater).filter(
            Repeater.hash.in_(segment)
        ).all()

        if not segment_repeaters:
            return None

        # Find repeater closest to any listener
        best_gateway = None
        min_distance = float('inf')

        for repeater in segment_repeaters:
            if not repeater.gps_lat or not repeater.gps_lon:
                continue

            for listener in listeners:
                listener_as_repeater = Repeater(
                    gps_lat=listener.gps_lat,
                    gps_lon=listener.gps_lon
                )
                distance = calculate_distance(repeater, listener_as_repeater)
                if distance is not None and distance < min_distance:
                    min_distance = distance
                    best_gateway = repeater

        return best_gateway

    def _check_existing_trace(self, from_repeater_id, to_repeater_id) -> bool:
        """Check if a trace already exists (pending, in_progress, or recent)."""
        existing = self.db.query(TraceSchedule).filter(
            TraceSchedule.from_repeater_id == from_repeater_id,
            TraceSchedule.to_repeater_id == to_repeater_id
        ).filter(
            (TraceSchedule.status.in_(["pending", "in_progress"])) |
            (
                (TraceSchedule.status.in_(["completed", "failed"])) &
                (TraceSchedule.scheduled_at >= datetime.utcnow() - timedelta(hours=self.verification_interval_hours))
            )
        ).first()
        return existing is not None
