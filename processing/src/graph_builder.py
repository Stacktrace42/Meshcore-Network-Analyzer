"""Graph building logic for network visualization."""
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime
from typing import List, Dict, Tuple, Optional
import logging
from geopy.distance import geodesic

from .models import Path, Repeater, GraphEdge

logger = logging.getLogger(__name__)


def resolve_hash_in_path_context(
    hash_value: str,
    prev_repeater: Optional[Repeater],
    next_repeater: Optional[Repeater],
    db: Session
) -> Optional[Repeater]:
    """
    Resolve a repeater hash using GPS distance to its neighbors in the path.

    For a path like A->B->C->D, when resolving B:
    - Find all repeaters with hash B
    - Calculate distance from each candidate to A (previous hop)
    - Calculate distance from each candidate to C (next hop)
    - Choose the candidate with minimum total distance

    Args:
        hash_value: The hash to resolve
        prev_repeater: The previous repeater in the path (already resolved)
        next_repeater: The next repeater in the path (already resolved)
        db: Database session

    Returns:
        The best matching repeater, or None if not found
    """
    # Get all repeaters matching this hash
    candidates = db.query(Repeater).filter(Repeater.hash == hash_value).all()

    if not candidates:
        logger.warning(f"No repeater found for hash {hash_value}")
        return None

    if len(candidates) == 1:
        return candidates[0]

    # Filter candidates with GPS coordinates
    candidates_with_gps = [
        r for r in candidates
        if r.gps_lat is not None and r.gps_lon is not None
    ]

    if not candidates_with_gps:
        logger.warning(f"No GPS data for hash {hash_value}, using first candidate")
        return candidates[0]

    # If no neighbors have GPS, return first candidate with GPS
    neighbors_with_gps = []
    if prev_repeater and prev_repeater.gps_lat is not None:
        neighbors_with_gps.append(prev_repeater)
    if next_repeater and next_repeater.gps_lat is not None:
        neighbors_with_gps.append(next_repeater)

    if not neighbors_with_gps:
        logger.debug(f"No neighbor GPS data for hash {hash_value}, using first candidate with GPS")
        return candidates_with_gps[0]

    # Calculate total distance to all neighbors for each candidate
    best_repeater = None
    min_total_distance = float('inf')

    for candidate in candidates_with_gps:
        candidate_coords = (candidate.gps_lat, candidate.gps_lon)
        total_distance = 0
        valid_distances = 0

        for neighbor in neighbors_with_gps:
            neighbor_coords = (neighbor.gps_lat, neighbor.gps_lon)
            try:
                distance = geodesic(candidate_coords, neighbor_coords).kilometers
                total_distance += distance
                valid_distances += 1
            except Exception as e:
                logger.error(f"Error calculating distance: {e}")
                continue

        if valid_distances > 0:
            avg_distance = total_distance / valid_distances

            if avg_distance < min_total_distance:
                min_total_distance = avg_distance
                best_repeater = candidate

    if best_repeater:
        logger.debug(
            f"Resolved hash {hash_value} to {best_repeater.name or best_repeater.id} "
            f"(avg distance: {min_total_distance:.2f} km)"
        )
        return best_repeater

    # Fallback to first candidate with GPS
    logger.warning(f"Could not resolve collision for hash {hash_value}, using first candidate")
    return candidates_with_gps[0]


def build_graph(db: Session, week_number: int = None):
    """
    Build network graph from observed paths.

    Process:
    1. Query all paths for the given week
    2. For each path, resolve repeater hashes using GPS distance to neighbors
    3. Extract edges from resolved paths
    4. Aggregate message counts and SNR per edge
    5. Update graph_edges table
    """
    if week_number is None:
        week_number = datetime.utcnow().isocalendar()[1]

    logger.info(f"Building graph for week {week_number}")

    # Query paths for this week
    paths = db.query(Path).filter(Path.week_number == week_number).all()

    if not paths:
        logger.info("No paths found for this week")
        return

    # Dictionary to accumulate edge data: (from_id, to_id) -> {'messages': count, 'snr_values': []}
    edge_data: Dict[Tuple[str, str], Dict] = {}

    # Process each path
    for path in paths:
        path_hashes = path.path

        if len(path_hashes) < 2:
            continue  # Need at least 2 hops to form an edge

        # Resolve all hashes in this path to actual repeaters
        resolved_repeaters: List[Optional[Repeater]] = []

        for i, hash_value in enumerate(path_hashes):
            # Get previous and next repeaters (already resolved)
            prev_repeater = resolved_repeaters[i - 1] if i > 0 else None

            # For next, we need to peek ahead and resolve it first if needed
            # We'll do a simpler approach: resolve each hash considering already-resolved neighbors
            next_hash = path_hashes[i + 1] if i < len(path_hashes) - 1 else None

            # Get potential next repeater(s) for context
            next_candidates = None
            if next_hash:
                next_candidates = db.query(Repeater).filter(Repeater.hash == next_hash).all()
                # Use first candidate with GPS as hint for next neighbor
                next_hint = None
                if next_candidates:
                    next_with_gps = [r for r in next_candidates if r.gps_lat is not None]
                    next_hint = next_with_gps[0] if next_with_gps else next_candidates[0]
            else:
                next_hint = None

            # Resolve this hop using its neighbors
            repeater = resolve_hash_in_path_context(hash_value, prev_repeater, next_hint, db)
            resolved_repeaters.append(repeater)

        # Now extract edges from the resolved path
        for i in range(len(resolved_repeaters) - 1):
            from_repeater = resolved_repeaters[i]
            to_repeater = resolved_repeaters[i + 1]

            if not from_repeater or not to_repeater:
                continue  # Skip if resolution failed

            edge_key = (str(from_repeater.id), str(to_repeater.id))

            if edge_key not in edge_data:
                edge_data[edge_key] = {'messages': 0, 'snr_values': []}

            # Count every path that uses this edge (regardless of SNR source)
            edge_data[edge_key]['messages'] += 1

            # Only use SNR from trace responses, not reception SNR
            # Reception SNR is how well the listener heard the packet, not edge quality
            if path.snr is not None and path.snr_source == 'trace':
                edge_data[edge_key]['snr_values'].append(path.snr)

    logger.info(f"Found {len(edge_data)} unique edges after resolving collisions")

    # Create or update graph edges
    for (from_id, to_id), data in edge_data.items():
        # Calculate statistics
        message_count = data['messages']
        snr_values = data['snr_values']
        avg_snr = sum(snr_values) / len(snr_values) if snr_values else None

        # Update or create graph edge
        edge = db.query(GraphEdge).filter(
            GraphEdge.from_repeater_id == from_id,
            GraphEdge.to_repeater_id == to_id,
            GraphEdge.week_number == week_number
        ).first()

        if edge:
            # Update existing edge
            edge.message_count = message_count
            edge.avg_snr = avg_snr
            edge.last_updated = datetime.utcnow()
        else:
            # Create new edge
            edge = GraphEdge(
                from_repeater_id=from_id,
                to_repeater_id=to_id,
                message_count=message_count,
                avg_snr=avg_snr,
                week_number=week_number
            )
            db.add(edge)

    db.commit()
    logger.info(f"Graph building complete for week {week_number}")


def get_graph_summary(db: Session, week_number: int = None) -> Dict:
    """Get summary statistics for the graph."""
    if week_number is None:
        week_number = datetime.utcnow().isocalendar()[1]

    edge_count = db.query(func.count(GraphEdge.id)).filter(
        GraphEdge.week_number == week_number
    ).scalar()

    repeater_count = db.query(func.count(Repeater.id)).scalar()

    avg_snr = db.query(func.avg(GraphEdge.avg_snr)).filter(
        GraphEdge.week_number == week_number
    ).scalar()

    return {
        "week_number": week_number,
        "edge_count": edge_count or 0,
        "repeater_count": repeater_count or 0,
        "avg_snr": float(avg_snr) if avg_snr else None
    }


def triangulate_repeater_positions(db: Session):
    """
    Estimate positions for repeaters without GPS using triangulation.

    For each repeater without GPS coordinates:
    1. Find neighbors from paths where repeater appears
    2. Filter neighbors to those with known GPS
    3. If >= 3 neighbors with GPS, calculate centroid
    4. Store in estimated_gps_lat/lon
    5. Set position_confidence = 'triangulated'
    """
    logger.info("Starting position triangulation")

    # Query repeaters without GPS
    repeaters_without_gps = db.query(Repeater).filter(
        Repeater.gps_lat.is_(None)
    ).all()

    if not repeaters_without_gps:
        logger.info("No repeaters without GPS found")
        return

    logger.info(f"Found {len(repeaters_without_gps)} repeaters without GPS")

    triangulated_count = 0

    for repeater in repeaters_without_gps:
        # Find all paths containing this repeater
        paths = db.query(Path).filter(
            func.json_array_length(Path.path) > 0
        ).all()

        # Extract neighbors (repeaters that appear adjacent in paths)
        neighbor_hashes = set()
        for path in paths:
            path_hashes = path.path
            if repeater.hash in path_hashes:
                idx = path_hashes.index(repeater.hash)
                # Add previous and next hashes
                if idx > 0:
                    neighbor_hashes.add(path_hashes[idx - 1])
                if idx < len(path_hashes) - 1:
                    neighbor_hashes.add(path_hashes[idx + 1])

        if not neighbor_hashes:
            continue

        # Get repeaters for these hashes with GPS coordinates
        neighbors_with_gps = db.query(Repeater).filter(
            Repeater.hash.in_(list(neighbor_hashes)),
            Repeater.gps_lat.isnot(None),
            Repeater.gps_lon.isnot(None)
        ).all()

        if len(neighbors_with_gps) < 3:
            logger.debug(
                f"Repeater {repeater.hash} has only {len(neighbors_with_gps)} neighbors with GPS, "
                f"need at least 3 for triangulation"
            )
            continue

        # Calculate centroid
        total_lat = sum(n.gps_lat for n in neighbors_with_gps)
        total_lon = sum(n.gps_lon for n in neighbors_with_gps)
        avg_lat = total_lat / len(neighbors_with_gps)
        avg_lon = total_lon / len(neighbors_with_gps)

        # Update repeater
        repeater.estimated_gps_lat = avg_lat
        repeater.estimated_gps_lon = avg_lon
        repeater.position_confidence = 'triangulated'
        repeater.triangulation_neighbors = [str(n.id) for n in neighbors_with_gps]

        triangulated_count += 1
        logger.info(
            f"Triangulated position for {repeater.hash}: "
            f"({avg_lat:.6f}, {avg_lon:.6f}) from {len(neighbors_with_gps)} neighbors"
        )

    # Set position_confidence for repeaters with GPS
    repeaters_with_gps = db.query(Repeater).filter(
        Repeater.gps_lat.isnot(None),
        Repeater.gps_lon.isnot(None)
    ).all()

    for repeater in repeaters_with_gps:
        if not repeater.position_confidence:
            repeater.position_confidence = 'known'

    db.commit()
    logger.info(f"Triangulation complete: {triangulated_count} repeaters positioned")
