from django.db.models import Count
from rest_framework import viewsets, permissions, mixins
from .models import Review, ReviewLike, ReviewReport
from .serializers import ReviewSerializer, ReviewLikeSerializer, ReviewReportSerializer


class IsOwnerOrReadOnly(permissions.BasePermission):
    """
    Read: everyone
    Write: only the owner of the review
    """

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return obj.user == request.user


class ReviewViewSet(viewsets.ModelViewSet):
    """
    /api/reviews/
    - GET: public
    - POST: authenticated
    - PATCH/PUT/DELETE: owner only
    """

    serializer_class = ReviewSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsOwnerOrReadOnly]

    def get_queryset(self):
        qs = (
            Review.objects.select_related("user", "film")
            .annotate(likes_count=Count("likes", distinct=True))
        )

        film_id = self.request.query_params.get("film")
        user_id = self.request.query_params.get("user")

        if film_id:
            qs = qs.filter(film_id=film_id)
        if user_id:
            qs = qs.filter(user_id=user_id)

        # If logged in, hide reviews this user reported
        user = self.request.user
        if user.is_authenticated:
            reported_ids = ReviewReport.objects.filter(user=user).values_list(
                "review_id", flat=True
            )
            qs = qs.exclude(id__in=reported_ids)

        return qs.order_by("-created_at")

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class ReviewLikeViewSet(
    mixins.CreateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """
    POST   /api/review-likes/        -> like a review (body: { "review": "<uuid>" })
    DELETE /api/review-likes/<id>/   -> unlike (only own like)
    """

    serializer_class = ReviewLikeSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """
        Limit queryset so users can only see/delete their own likes.
        """
        user = self.request.user
        if not user.is_authenticated:
            return ReviewLike.objects.none()
        return ReviewLike.objects.filter(user=user).select_related("review")

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class ReviewReportViewSet(
    mixins.CreateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """
    POST   /api/review-reports/        -> report a review (body: { "review": "<uuid>" })
    DELETE /api/review-reports/<id>/   -> undo report (only own report)
    """

    serializer_class = ReviewReportSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # Users may only delete their own reports
        user = self.request.user
        if not user.is_authenticated:
            return ReviewReport.objects.none()
        return ReviewReport.objects.filter(user=user).select_related("review")

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

