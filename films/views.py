# films/views.py

from rest_framework import viewsets
from django.db.models import Avg, Count, Exists, OuterRef, BooleanField, Value

from .models import Film
from .serializers import FilmSerializer
from favourites.models import Favourite
from watchlist.models import Watchlist


class FilmViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Provides /api/films/  (list)
            /api/films/<id>/ (detail)
    """

    serializer_class = FilmSerializer

    def get_queryset(self):
        user = self.request.user

        qs = Film.objects.all()

        # Review stats
        qs = qs.annotate(
            average_rating=Avg("reviews__rating"),
            review_count=Count("reviews", distinct=True),
        )

        # User-specific flags
        if user.is_authenticated:
            qs = qs.annotate(
                is_favourited=Exists(
                    Favourite.objects.filter(user=user, film=OuterRef("pk"))
                ),
                in_watchlist=Exists(
                    Watchlist.objects.filter(user=user, film=OuterRef("pk"))
                ),
            )
        else:
            qs = qs.annotate(
                is_favourited=Value(False, output_field=BooleanField()),
                in_watchlist=Value(False, output_field=BooleanField()),
            )

        return qs
