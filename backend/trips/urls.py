"""URL routes for the trips app."""
from django.urls import path

from . import views

urlpatterns = [
    path("geocode", views.geocode_view),
    path("geocode/", views.geocode_view),
    path("trips", views.create_trip),
    path("trips/", views.create_trip),
    path("trips/<uuid:trip_id>", views.get_trip),
    path("trips/<uuid:trip_id>/", views.get_trip),
]
