"""Resolve repeater hash collisions using GPS distance."""
from typing import List, Optional
from sqlalchemy.orm import Session
from geopy.distance import geodesic
import logging

from .models import Repeater

logger = logging.getLogger(__name__)


def resolve_repeater_collision(
    candidate_repeaters: List[Repeater],
    neighbor_repeaters: List[Repeater],
    db: Session
) -> Optional[Repeater]:
    """
    Resolve repeater hash collision using GPS distance.

    When multiple repeaters share the same hash (first byte of public key),
    choose the one closest to the neighboring repeaters in the path.

    Args:
        candidate_repeaters: List of repeaters with the same hash
        neighbor_repeaters: List of neighboring repeaters in the path
        db: Database session

    Returns:
        The most likely repeater, or None if unable to resolve
    """
    if len(candidate_repeaters) == 1:
        return candidate_repeaters[0]

    if not candidate_repeaters:
        return None

    # Filter repeaters with GPS coordinates
    candidates_with_gps = [
        r for r in candidate_repeaters
        if r.gps_lat is not None and r.gps_lon is not None
    ]

    neighbors_with_gps = [
        r for r in neighbor_repeaters
        if r.gps_lat is not None and r.gps_lon is not None
    ]

    if not candidates_with_gps:
        # No GPS data, return first candidate
        logger.warning(
            f"No GPS data for candidates with hash {candidate_repeaters[0].hash}, "
            f"returning first candidate"
        )
        return candidate_repeaters[0]

    if not neighbors_with_gps:
        # No neighbor GPS data, return first candidate with GPS
        logger.warning(
            f"No neighbor GPS data for collision resolution, "
            f"returning first candidate with GPS"
        )
        return candidates_with_gps[0]

    # Calculate average distance to all neighbors for each candidate
    best_repeater = None
    min_avg_distance = float('inf')

    for candidate in candidates_with_gps:
        candidate_coords = (candidate.gps_lat, candidate.gps_lon)
        distances = []

        for neighbor in neighbors_with_gps:
            neighbor_coords = (neighbor.gps_lat, neighbor.gps_lon)
            try:
                distance = geodesic(candidate_coords, neighbor_coords).kilometers
                distances.append(distance)
            except Exception as e:
                logger.error(f"Error calculating distance: {e}")
                continue

        if distances:
            avg_distance = sum(distances) / len(distances)

            if avg_distance < min_avg_distance:
                min_avg_distance = avg_distance
                best_repeater = candidate

    if best_repeater:
        logger.info(
            f"Resolved collision for hash {best_repeater.hash}: "
            f"selected {best_repeater.name or best_repeater.id} "
            f"with avg distance {min_avg_distance:.2f} km"
        )
        return best_repeater

    # Fallback to first candidate
    logger.warning(f"Could not resolve collision, returning first candidate")
    return candidates_with_gps[0]


def calculate_distance(repeater1: Repeater, repeater2: Repeater) -> Optional[float]:
    """
    Calculate geodesic distance between two repeaters.

    Returns:
        Distance in kilometers, or None if GPS data is missing
    """
    if not all([
        repeater1.gps_lat, repeater1.gps_lon,
        repeater2.gps_lat, repeater2.gps_lon
    ]):
        return None

    try:
        coords1 = (repeater1.gps_lat, repeater1.gps_lon)
        coords2 = (repeater2.gps_lat, repeater2.gps_lon)
        return geodesic(coords1, coords2).kilometers
    except Exception as e:
        logger.error(f"Error calculating distance: {e}")
        return None
