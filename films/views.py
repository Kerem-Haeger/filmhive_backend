from rest_framework import viewsets
from django.db.models import Avg, Count
from .models import Film
from .serializers import FilmSerializer


class FilmViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Provides /api/films/  (list)
            /api/films/<id>/ (detail)
    """

    serializer_class = FilmSerializer

    def get_queryset(self):
        # Base queryset
        qs = Film.objects.all()

        # Add review statistics
        qs = qs.annotate(
            average_rating=Avg("reviews__rating"),
            review_count=Count("reviews", distinct=True)
        )

        return qs
