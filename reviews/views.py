from rest_framework import viewsets, permissions, mixins
from .models import Review, ReviewLike
from .serializers import ReviewSerializer, ReviewLikeSerializer


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
    serializer_class = ReviewSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsOwnerOrReadOnly]

    def get_queryset(self):
        qs = Review.objects.select_related("user", "film").all()

        film_id = self.request.query_params.get("film")
        user_id = self.request.query_params.get("user")

        if film_id:
            qs = qs.filter(film_id=film_id)
        if user_id:
            qs = qs.filter(user_id=user_id)

        return qs.order_by("-created_at")

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class ReviewLikeViewSet(
    mixins.CreateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """
    POST /api/review-likes/  -> like a review
    DELETE /api/review-likes/<id>/ -> unlike (only own like)
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
