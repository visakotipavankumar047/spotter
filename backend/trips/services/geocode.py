"""Geocode service — thin Nominatim client.

Proxied through Django to control the required User-Agent header and
rate limiting. Contains no business logic.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

import requests

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
DEFAULT_TIMEOUT = 10  # seconds


@dataclass
class GeocodeResult:
    """A single geocode result."""

    label: str
    lat: float
    lng: float


def geocode(query: str, user_agent: str = "ELD-Trip-Planner/1.0") -> List[GeocodeResult]:
    """Geocode a place name via Nominatim.

    Args:
        query: Place name string (e.g. "Chicago, IL").
        user_agent: Required by Nominatim usage policy.

    Returns:
        List of GeocodeResult, max 5 results.
    """
    if not query or not query.strip():
        return []

    params = {
        "q": query.strip(),
        "format": "json",
        "limit": 5,
        "addressdetails": 1,
        "countrycodes": "us",
    }
    headers = {"User-Agent": user_agent}

    try:
        resp = requests.get(
            NOMINATIM_URL, params=params, headers=headers, timeout=DEFAULT_TIMEOUT
        )
        resp.raise_for_status()
        data = resp.json()
    except (requests.RequestException, ValueError):
        return []

    results: List[GeocodeResult] = []
    for item in data:
        lat = float(item.get("lat", 0))
        lng = float(item.get("lon", 0))
        results.append(
            GeocodeResult(
                label=_format_place_label(item, query),
                lat=lat,
                lng=lng,
            )
        )

    return results


def _format_place_label(item: dict, fallback: str) -> str:
    """Build a short place label from Nominatim address details."""
    address = item.get("address") or {}
    city = (
        address.get("city")
        or address.get("town")
        or address.get("village")
        or address.get("hamlet")
        or address.get("municipality")
        or address.get("county")
        or ""
    )
    state = address.get("state") or address.get("region") or ""
    country_code = (address.get("country_code") or "").upper()

    if city and state:
        if country_code and country_code != "US":
            return f"{city}, {state}, {country_code}"
        return f"{city}, {state}"
    if city:
        return city
    if state:
        return state

    display = item.get("display_name") or fallback
    parts = [p.strip() for p in display.split(",") if p.strip()]
    if len(parts) >= 2:
        return f"{parts[0]}, {parts[1]}"
    return display


def reverse_geocode(
    lat: float, lng: float, user_agent: str = "ELD-Trip-Planner/1.0"
) -> str:
    """Reverse geocode coordinates to a city/state label.

    Args:
        lat: Latitude.
        lng: Longitude.
        user_agent: Required by Nominatim usage policy.

    Returns:
        Human-readable location string (e.g. "Rensselaer, IN").
    """
    params = {
        "lat": lat,
        "lon": lng,
        "format": "json",
        "zoom": 10,
        "addressdetails": 1,
    }
    headers = {"User-Agent": user_agent}

    try:
        resp = requests.get(
            "https://nominatim.openstreetmap.org/reverse",
            params=params,
            headers=headers,
            timeout=DEFAULT_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
    except (requests.RequestException, ValueError):
        return f"{lat:.4f}, {lng:.4f}"

    address = data.get("address", {})
    city = address.get("city") or address.get("town") or address.get("village") or ""
    state = address.get("state", "")

    if city and state:
        return f"{city}, {state}"
    elif city:
        return city
    elif state:
        return state
    return data.get("display_name", f"{lat:.4f}, {lng:.4f}")
