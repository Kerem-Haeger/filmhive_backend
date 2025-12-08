from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ReviewViewSet, ReviewLikeViewSet, ReviewReportViewSet

router = DefaultRouter()
router.register(r"reviews", ReviewViewSet, basename="review")
router.register(r"review-likes", ReviewLikeViewSet, basename="review-like")
router.register(r"review-reports", ReviewReportViewSet, basename="review-report")

urlpatterns = [
    path("", include(router.urls)),
]
