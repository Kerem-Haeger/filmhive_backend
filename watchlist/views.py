from rest_framework import viewsets, mixins, permissions
from .models import Watchlist
from .serializers import WatchlistSerializer


class WatchlistViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """
    - GET    /api/watchlist/           -> list my watchlist items
    - POST   /api/watchlist/           -> add film to my (named) watchlist
    - DELETE /api/watchlist/<id>/      -> remove from watchlist
    """

    serializer_class = WatchlistSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return Watchlist.objects.none()

        qs = Watchlist.objects.filter(user=user).select_related("film")

        # Optional filter by list name (e.g. ?name=Halloween Picks)
        name = self.request.query_params.get("name")
        if name:
            qs = qs.filter(name=name)

        return qs.order_by("name", "position", "-created_at")

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
