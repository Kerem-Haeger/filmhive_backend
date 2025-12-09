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
        request = self.request
        user = request.user
        params = request.query_params

        qs = Film.objects.all()

        # -------- basic filters (no annotations needed) --------
        search = params.get("search")
        if search:
            qs = qs.filter(title__icontains=search)

        year = params.get("year")
        if year:
            qs = qs.filter(year=year)

        # you could also add runtime, year range, etc later

        # -------- annotations: review stats --------
        qs = qs.annotate(
            average_rating=Avg("reviews__rating"),
            review_count=Count("reviews", distinct=True),
        )

        # -------- annotations: user-specific flags --------
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

        # -------- filters that use annotations --------
        min_rating = params.get("min_rating")
        if min_rating:
            try:
                min_rating = float(min_rating)
                qs = qs.filter(average_rating__gte=min_rating)
            except ValueError:
                pass  # ignore bad values silently

        favourited = params.get("favourited")
        if favourited and favourited.lower() == "true" and user.is_authenticated:
            qs = qs.filter(is_favourited=True)

        in_watchlist = params.get("in_watchlist")
        if in_watchlist and in_watchlist.lower() == "true" and user.is_authenticated:
            qs = qs.filter(in_watchlist=True)

        return qs
