"""Routing service — thin OSRM client.

Calls the OSRM public demo API for driving routes. Returns distance,
duration, and geometry. Contains no business logic.
"""

from __future__ import annotations

from typing import List, Tuple

import requests

from .hos_engine import RouteLeg, LatLng

OSRM_URL = "https://router.project-osrm.org/route/v1/driving"
DEFAULT_TIMEOUT = 30  # seconds


def _meters_to_miles(meters: float) -> float:
    return meters * 0.000621371


def _seconds_to_hours(seconds: float) -> float:
    return seconds / 3600.0


def get_route(
    start: LatLng, end: LatLng, user_agent: str = "ELD-Trip-Planner/1.0"
) -> RouteLeg:
    """Get a driving route from OSRM between two coordinates.

    Args:
        start: Starting coordinate.
        end: Ending coordinate.
        user_agent: User-Agent header for the request.

    Returns:
        RouteLeg with distance (miles), duration (hours), and geometry.

    Raises:
        requests.RequestException: If the OSRM API call fails.
        ValueError: If the response is malformed or has no route.
    """
    coords_str = f"{start.lng},{start.lat};{end.lng},{end.lat}"
    params = {
        "overview": "full",
        "geometries": "geojson",
    }
    headers = {"User-Agent": user_agent}

    resp = requests.get(
        f"{OSRM_URL}/{coords_str}",
        params=params,
        headers=headers,
        timeout=DEFAULT_TIMEOUT,
    )
    resp.raise_for_status()
    data = resp.json()

    if data.get("code") != "Ok" or not data.get("routes"):
        raise ValueError(f"OSRM routing failed: {data.get('code', 'unknown')}")

    route = data["routes"][0]
    distance_miles = _meters_to_miles(route["distance"])
    duration_hours = _seconds_to_hours(route["duration"])
    geometry: List[Tuple[float, float]] = [
        (coord[0], coord[1]) for coord in route["geometry"]["coordinates"]
    ]

    return RouteLeg(
        distance_miles=distance_miles,
        duration_hours=duration_hours,
        geometry=geometry,
        start_coords=start,
        end_coords=end,
    )
