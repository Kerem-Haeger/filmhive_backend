from rest_framework import viewsets, mixins, permissions
from .models import Favourite
from .serializers import FavouriteSerializer


class FavouriteViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = FavouriteSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return Favourite.objects.none()
        return Favourite.objects.filter(user=user).select_related("film")

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
