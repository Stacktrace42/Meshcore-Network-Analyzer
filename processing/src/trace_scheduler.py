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

            # Calculate loop trace path: Gateway → From → To → Gateway
            # Gateway is the repeater this listener can hear best (from ANY repeater, not just the edge)
            gateway = self._find_best_repeater_for_listener(assigned_listener)

            if not gateway:
                logger.warning(f"No gateway found for listener {assigned_listener.name}")
                continue

            from_hash = edge.from_repeater.hash
            to_hash = edge.to_repeater.hash

            # Try to build full loop path with routes TO and FROM the edge
            # Gateway → (route to from) → From → To → (route from to back to gateway) → Gateway

            # First try: Find if gateway directly connects to from or to
            # If gateway == from or gateway == to, we can do a simple 3-hop loop
            if gateway.hash == from_hash:
                # Gateway is the from repeater: Gateway → To → Gateway
                path_from_to_back = self._find_path_between_repeaters(to_hash, gateway.hash)
                if path_from_to_back and len(path_from_to_back) >=2:
                    calculated_path = [gateway.hash, to_hash] + path_from_to_back[1:]
                else:
                    # Simple 2-hop loop
                    calculated_path = [gateway.hash, to_hash, gateway.hash]
            elif gateway.hash == to_hash:
                # Gateway is the to repeater: Gateway → From → Gateway
                path_to_from = self._find_path_between_repeaters(gateway.hash, from_hash)
                if path_to_from and len(path_to_from) >= 2:
                    calculated_path = path_to_from + [gateway.hash]
                else:
                    # Simple 2-hop loop
                    calculated_path = [gateway.hash, from_hash, gateway.hash]
            else:
                # Gateway is separate - need full routing
                path_to_from = self._find_path_between_repeaters(gateway.hash, from_hash)
                path_from_to_back = self._find_path_between_repeaters(to_hash, gateway.hash)

                if not path_to_from or not path_from_to_back:
                    logger.debug(
                        f"Cannot build full trace path, skipping edge "
                        f"(gateway={gateway.hash}, from={from_hash}, to={to_hash})"
                    )
                    continue

                # Build complete loop: gateway + path_to_from[1:] + [to] + path_from_to_back[1:]
                calculated_path = [gateway.hash] + path_to_from[1:] + [to_hash] + path_from_to_back[1:]

            # Create trace schedule
            trace = TraceSchedule(
                from_repeater_id=edge.from_repeater_id,
                to_repeater_id=edge.to_repeater_id,
                assigned_listener_id=assigned_listener.id,
                status="pending",
                scheduled_at=next_schedule_time,
                calculated_path=calculated_path,
                path_strategy="loop"
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

        Choose the listener with best reception quality from the starting repeater,
        based on message count and average SNR.
        """
        from sqlalchemy import func

        # Get all active listeners
        listeners = self.db.query(Listener).filter(Listener.active == True).all()

        if not listeners:
            logger.warning("No active listeners found")
            return None

        if len(listeners) == 1:
            return listeners[0]

        # Find listener with best reception from from_repeater
        # Look for paths where from_repeater is in the path (anywhere in the route)
        best_listener = None
        best_score = float('-inf')

        for listener in listeners:
            from sqlalchemy import cast, func
            from sqlalchemy.dialects.postgresql import JSONB

            # Query paths from this listener where from_repeater appears
            # Use PostgreSQL's JSONB containment operator: path::jsonb @> '["hash"]'::jsonb
            paths = self.db.query(Path).filter(
                Path.listener_id == listener.id,
                func.cast(Path.path, JSONB).op('@>')(func.cast(f'["{from_repeater.hash}"]', JSONB)),
                Path.snr_source == 'reception'
            ).all()

            if not paths:
                continue

            # Calculate score based on message count and average SNR
            message_count = len(paths)
            avg_snr = sum(p.snr for p in paths if p.snr is not None) / len([p for p in paths if p.snr is not None]) if any(p.snr is not None for p in paths) else 0

            # Score formula: prioritize message count, use SNR as tiebreaker
            # Each message = 1 point, each dB of SNR = 0.1 points
            score = message_count + (avg_snr * 0.1)

            if score > best_score:
                best_score = score
                best_listener = listener

        if best_listener:
            logger.info(
                f"Selected listener {best_listener.name} for trace "
                f"(reception score: {best_score:.1f})"
            )
            return best_listener

        # Fallback: return first active listener
        logger.warning(f"No reception data found for repeater {from_repeater.hash}, using first listener")
        return listeners[0]

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

    def _find_path_between_repeaters(
        self,
        from_hash: str,
        to_hash: str
    ) -> Optional[list]:
        """Find a path from one repeater to another using captured path data.

        Returns a list of hashes representing the route, or None if no path found.
        The returned path includes both from_hash and to_hash.
        """
        # Special case: if from and to are the same, return single-element path
        if from_hash == to_hash:
            return [from_hash]

        # Query all recent paths that contain both repeaters
        from sqlalchemy import cast, func
        from sqlalchemy.dialects.postgresql import JSONB

        # Get paths that contain both hashes
        paths = self.db.query(Path).filter(
            func.cast(Path.path, JSONB).op('@>')(func.cast(f'["{from_hash}", "{to_hash}"]', JSONB))
        ).order_by(Path.timestamp.desc()).limit(50).all()

        if not paths:
            # Try to find any path containing the destination
            # and build a route through multiple hops if needed
            logger.debug(f"No direct path found from {from_hash} to {to_hash}")
            return None

        # Find the shortest segment that goes from from_hash to to_hash
        best_path = None
        min_length = float('inf')

        for path_record in paths:
            path_hashes = path_record.path

            # Find indices of from and to
            try:
                from_idx = path_hashes.index(from_hash)
                to_idx = path_hashes.index(to_hash)

                # We want from to appear before to in the path
                if from_idx < to_idx:
                    segment = path_hashes[from_idx:to_idx + 1]
                    if len(segment) < min_length:
                        min_length = len(segment)
                        best_path = segment
            except ValueError:
                # One of the hashes not in this path (shouldn't happen due to filter)
                continue

        if best_path:
            logger.debug(f"Found path from {from_hash} to {to_hash}: {best_path}")
            return best_path

        logger.debug(f"No valid path found from {from_hash} to {to_hash}")
        return None

    def _find_best_repeater_for_listener(
        self,
        listener: Listener
    ) -> Optional[Repeater]:
        """Find the repeater that this listener can hear best (overall).

        Returns the repeater with best reception quality from this listener.
        """
        from sqlalchemy import cast, func
        from sqlalchemy.dialects.postgresql import JSONB

        # Get all paths from this listener with reception SNR
        paths = self.db.query(Path).filter(
            Path.listener_id == listener.id,
            Path.snr_source == 'reception',
            Path.snr.isnot(None)
        ).all()

        logger.debug(f"Found {len(paths)} reception paths for listener {listener.name} (ID: {listener.id})")

        if not paths:
            logger.warning(f"No reception paths found for listener {listener.name} (ID: {listener.id})")
            # Try without SNR requirement to see if snr_source is the issue
            all_paths = self.db.query(Path).filter(
                Path.listener_id == listener.id,
                Path.snr_source == 'reception'
            ).all()
            logger.debug(f"Total reception paths (including NULL SNR): {len(all_paths)}")
            return None

        # Count messages and calculate avg SNR per repeater
        repeater_stats = {}  # hash -> (message_count, total_snr, snr_count)

        for path in paths:
            # Count each repeater that appears in the path
            for repeater_hash in path.path:
                if repeater_hash not in repeater_stats:
                    repeater_stats[repeater_hash] = [0, 0.0, 0]

                repeater_stats[repeater_hash][0] += 1  # message count
                if path.snr is not None:
                    repeater_stats[repeater_hash][1] += path.snr  # total SNR
                    repeater_stats[repeater_hash][2] += 1  # SNR count

        # Find repeater with best score
        best_hash = None
        best_score = float('-inf')

        for repeater_hash, (msg_count, total_snr, snr_count) in repeater_stats.items():
            avg_snr = total_snr / snr_count if snr_count > 0 else 0
            score = msg_count + (avg_snr * 0.1)

            if score > best_score:
                best_score = score
                best_hash = repeater_hash

        if not best_hash:
            logger.warning(f"No repeaters found in reception paths for listener {listener.name}")
            return None

        # Get the Repeater object
        repeater = self.db.query(Repeater).filter(Repeater.hash == best_hash).first()

        if repeater:
            logger.info(f"Best repeater for listener {listener.name}: {repeater.hash} (score: {best_score:.2f})")
        else:
            logger.warning(f"Repeater {best_hash} not found in database")

        return repeater

    def _find_best_gateway_for_listener(
        self,
        listener: Listener,
        segment: list
    ) -> Optional[Repeater]:
        """Find the best gateway repeater for a specific listener and segment.

        Returns the repeater in the segment that this listener can hear best.
        """
        from sqlalchemy import cast, func
        from sqlalchemy.dialects.postgresql import JSONB

        # Get all repeaters in the segment
        segment_repeaters = self.db.query(Repeater).filter(
            Repeater.hash.in_(segment)
        ).all()

        if not segment_repeaters:
            logger.debug(f"No repeaters found for segment {segment}")
            return None

        # Find repeater with best reception quality from this listener
        best_gateway = None
        best_score = float('-inf')

        for repeater in segment_repeaters:
            # Query paths from this listener where repeater appears
            # Use PostgreSQL's JSONB containment operator: path::jsonb @> '["hash"]'::jsonb
            paths = self.db.query(Path).filter(
                Path.listener_id == listener.id,
                func.cast(Path.path, JSONB).op('@>')(func.cast(f'["{repeater.hash}"]', JSONB)),
                Path.snr_source == 'reception'
            ).all()

            if not paths:
                logger.debug(f"No paths found for repeater {repeater.hash} from listener {listener.name}")
                continue

            message_count = len(paths)
            avg_snr = sum(p.snr for p in paths if p.snr is not None) / len([p for p in paths if p.snr is not None]) if any(p.snr is not None for p in paths) else 0

            score = message_count + (avg_snr * 0.1)
            logger.debug(f"Repeater {repeater.hash}: {message_count} messages, avg SNR {avg_snr:.2f}, score {score:.2f}")

            if score > best_score:
                best_score = score
                best_gateway = repeater

        if best_gateway:
            logger.info(f"Best gateway for listener {listener.name}: {best_gateway.hash} (score: {best_score:.2f})")
        else:
            logger.warning(f"No gateway found for listener {listener.name} in segment {segment}")

        return best_gateway

    def _find_best_gateway_for_segment(self, segment: list) -> Optional[Repeater]:
        """Find the best gateway repeater for a path segment.

        Select the repeater with best reception quality across all listeners.
        """
        # Get all active listeners
        listeners = self.db.query(Listener).filter(Listener.active == True).all()

        if not listeners:
            return None

        # Get all repeaters in the segment
        segment_repeaters = self.db.query(Repeater).filter(
            Repeater.hash.in_(segment)
        ).all()

        if not segment_repeaters:
            return None

        # Find repeater with best reception quality across all listeners
        best_gateway = None
        best_score = float('-inf')

        for repeater in segment_repeaters:
            total_messages = 0
            total_snr = 0
            snr_count = 0

            # Check reception quality from all listeners
            for listener in listeners:
                from sqlalchemy import cast, func
                from sqlalchemy.dialects.postgresql import JSONB

                paths = self.db.query(Path).filter(
                    Path.listener_id == listener.id,
                    func.cast(Path.path, JSONB).op('@>')(func.cast(f'["{repeater.hash}"]', JSONB)),
                    Path.snr_source == 'reception'
                ).all()

                total_messages += len(paths)
                for path in paths:
                    if path.snr is not None:
                        total_snr += path.snr
                        snr_count += 1

            if total_messages == 0:
                continue

            avg_snr = total_snr / snr_count if snr_count > 0 else 0
            score = total_messages + (avg_snr * 0.1)

            if score > best_score:
                best_score = score
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
