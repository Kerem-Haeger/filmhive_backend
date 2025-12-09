from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import FilmViewSet, BlendView

router = DefaultRouter()
router.register(r"films", FilmViewSet, basename="film")

urlpatterns = [
    path("blend/", BlendView.as_view(), name="film-blend"),
    path("", include(router.urls)),
]
