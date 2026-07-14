"""API views for the ELD Trip Planner."""
from datetime import datetime, timezone

from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import Trip
from .serializers import (
    TripCreateSerializer,
    GeocodeSerializer,
    TripResponseSerializer,
)
from .services.geocode import geocode, reverse_geocode
from .services.routing import get_route
from .services.hos_engine import (
    build_duty_timeline,
    LatLng,
    DutyStatus,
)
from .services.log_builder import build_daily_logs, daily_log_to_dict


def _geocode_location(query: str) -> LatLng:
    """Geocode a location string, returning the first result's coords."""
    results = geocode(query)
    if not results:
        raise ValueError(f"Could not geocode: {query}")
    return LatLng(lat=results[0].lat, lng=results[0].lng)


def _build_trip_response(trip: Trip) -> dict:
    """Build the full API response dict for a Trip."""
    return {
        "trip_id": str(trip.id),
        "current_location": trip.current_location,
        "pickup_location": trip.pickup_location,
        "dropoff_location": trip.dropoff_location,
        "current_cycle_used_hours": trip.current_cycle_used_hours,
        "trip_start_datetime": trip.trip_start_datetime.isoformat(),
        "summary": {
            "total_distance_miles": trip.total_distance_miles,
            "total_drive_hours": trip.total_drive_hours,
            "total_duty_hours": trip.total_duty_hours,
            "num_days": trip.num_days,
            "cycle_hours_remaining_at_finish": trip.cycle_hours_remaining,
            "restarts_required": trip.restarts_required,
        },
        "route": {
            "geometry": trip.route_geometry,
            "stops": trip.route_stops,
        },
        "daily_logs": trip.daily_logs_data,
    }


@api_view(["POST"])
def geocode_view(request):
    """POST /api/geocode/ — geocode a location query via Nominatim."""
    serializer = GeocodeSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    query = serializer.validated_data["q"]
    results = geocode(query)

    return Response(
        [
            {"label": r.label, "lat": r.lat, "lng": r.lng}
            for r in results
        ]
    )


@api_view(["POST"])
def create_trip(request):
    """POST /api/trips/ — create a new trip with HOS-compliant timeline."""
    serializer = TripCreateSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    data = serializer.validated_data

    # Trip start datetime (defaults to now)
    start_dt = data.get("trip_start_datetime") or datetime.now(timezone.utc)

    try:
        # 1. Geocode all three locations
        current_coords = _geocode_location(data["current_location"])
        pickup_coords = _geocode_location(data["pickup_location"])
        dropoff_coords = _geocode_location(data["dropoff_location"])

        # 2. Get routes from OSRM
        leg1 = get_route(current_coords, pickup_coords)
        leg2 = get_route(pickup_coords, dropoff_coords)
        legs = [leg1, leg2]

        # 3. Build HOS-compliant duty timeline
        segments, summary = build_duty_timeline(
            legs=legs,
            start_datetime=start_dt,
            current_cycle_used_hours=data["current_cycle_used_hours"],
        )

        # 4. Build daily logs
        daily_logs = build_daily_logs(
            segments=segments,
            reverse_geocode_fn=reverse_geocode,
        )

        # 5. Build route geometry and stops
        route_geometry = {
            "type": "LineString",
            "coordinates": leg1.geometry + leg2.geometry,
        }

        stops = []
        miles_driven = 0.0
        for seg in segments:
            if seg.status == DutyStatus.DRIVING:
                miles_driven += seg.distance_miles

            if not seg.label or not seg.start_latlng:
                continue

            label_l = seg.label.lower()
            stop_type = None
            if label_l == "pickup":
                stop_type = "pickup"
            elif label_l == "dropoff":
                stop_type = "dropoff"
            elif label_l == "fuel stop" or label_l.startswith("fuel"):
                stop_type = "fuel"
            elif (
                "break" in label_l
                or "reset" in label_l
                or "restart" in label_l
            ):
                stop_type = "rest"

            if not stop_type:
                continue

            if stop_type == "pickup":
                location = data["pickup_location"]
            elif stop_type == "dropoff":
                location = data["dropoff_location"]
            else:
                location = data["current_location"]

            stops.append(
                {
                    "type": stop_type,
                    "label": seg.label,
                    "location": location,
                    "lat": seg.start_latlng.lat,
                    "lng": seg.start_latlng.lng,
                    "arrival": seg.start_datetime.isoformat(),
                    "duration_min": int(round(seg.duration_hours * 60)),
                    "mile_marker": int(round(miles_driven)),
                }
            )

        # 6. Save trip
        trip = Trip.objects.create(
            current_location=data["current_location"],
            pickup_location=data["pickup_location"],
            dropoff_location=data["dropoff_location"],
            current_cycle_used_hours=data["current_cycle_used_hours"],
            trip_start_datetime=start_dt,
            total_distance_miles=summary.total_distance_miles,
            total_drive_hours=summary.total_drive_hours,
            total_duty_hours=summary.total_duty_hours,
            num_days=summary.num_days,
            cycle_hours_remaining=summary.cycle_hours_remaining_at_finish,
            restarts_required=summary.restarts_required,
            route_geometry=route_geometry,
            route_stops=stops,
            daily_logs_data=[daily_log_to_dict(log) for log in daily_logs],
        )

        return Response(
            _build_trip_response(trip),
            status=status.HTTP_201_CREATED,
        )

    except ValueError as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_400_BAD_REQUEST,
        )
    except Exception as e:
        return Response(
            {"error": f"Trip planning failed: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["GET"])
def get_trip(request, trip_id: str):
    """GET /api/trips/{id}/ — retrieve a saved trip."""
    try:
        trip = Trip.objects.get(id=trip_id)
    except Trip.DoesNotExist:
        return Response(
            {"error": "Trip not found"},
            status=status.HTTP_404_NOT_FOUND,
        )

    return Response(_build_trip_response(trip))
