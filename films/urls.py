from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import FilmViewSet, BlendView, ForYouView, CompromiseView

router = DefaultRouter()
router.register(r"films", FilmViewSet, basename="film")

urlpatterns = [
    path("films/blend/", BlendView.as_view(), name="film-blend"),
    path("films/for-you/", ForYouView.as_view(), name="film-for-you"),
    path("compromise/", CompromiseView.as_view(), name="film-compromise"),
    path("", include(router.urls)),
]
