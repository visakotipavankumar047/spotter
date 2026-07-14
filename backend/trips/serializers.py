"""DRF serializers for the ELD Trip Planner."""
from rest_framework import serializers

from .models import Trip


class TripCreateSerializer(serializers.Serializer):
    """Input serializer for POST /api/trips/."""

    current_location = serializers.CharField(max_length=500)
    pickup_location = serializers.CharField(max_length=500)
    dropoff_location = serializers.CharField(max_length=500)
    current_cycle_used_hours = serializers.FloatField(min_value=0, max_value=70)
    trip_start_datetime = serializers.DateTimeField(required=False)


class GeocodeSerializer(serializers.Serializer):
    """Input serializer for POST /api/geocode/."""

    q = serializers.CharField(max_length=500)


class TripResponseSerializer(serializers.ModelSerializer):
    """Output serializer for trip responses."""

    trip_id = serializers.UUIDField(source="id", read_only=True)

    class Meta:
        model = Trip
        fields = [
            "trip_id",
            "current_location",
            "pickup_location",
            "dropoff_location",
            "current_cycle_used_hours",
            "trip_start_datetime",
            "total_distance_miles",
            "total_drive_hours",
            "total_duty_hours",
            "num_days",
            "cycle_hours_remaining",
            "restarts_required",
            "route_geometry",
            "route_stops",
            "daily_logs_data",
        ]
