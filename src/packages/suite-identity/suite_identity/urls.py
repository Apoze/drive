"""Identical paths behind each application's existing API prefix."""

from django.urls import path

from .views import CatalogueView, LogoutView

urlpatterns = [
    path("catalogue/", CatalogueView.as_view(), name="suite_catalogue"),
    path("logout/", LogoutView.as_view(), name="suite_logout"),
]
