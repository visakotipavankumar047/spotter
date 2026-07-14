"""Root URL configuration — delegates to the trips app."""
from django.urls import path, include

urlpatterns = [
    path("api/", include("trips.urls")),
]
