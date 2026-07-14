"""Django models for the ELD Trip Planner."""
import uuid

from django.db import models


class Trip(models.Model):
    """A single trip plan request."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    current_location = models.CharField(max_length=500)
    pickup_location = models.CharField(max_length=500)
    dropoff_location = models.CharField(max_length=500)
    current_cycle_used_hours = models.FloatField()
    trip_start_datetime = models.DateTimeField()

    # Cached route data
    total_distance_miles = models.FloatField(default=0.0)
    total_drive_hours = models.FloatField(default=0.0)
    total_duty_hours = models.FloatField(default=0.0)
    num_days = models.IntegerField(default=1)
    cycle_hours_remaining = models.FloatField(default=0.0)
    restarts_required = models.IntegerField(default=0)

    # Full JSON response cache
    route_geometry = models.JSONField(default=dict, blank=True)
    route_stops = models.JSONField(default=list, blank=True)
    daily_logs_data = models.JSONField(default=list, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "trips"

    def __str__(self) -> str:
        return f"Trip {self.id} — {self.current_location} → {self.dropoff_location}"
