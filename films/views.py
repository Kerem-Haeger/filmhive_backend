from rest_framework import viewsets
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from django.db.models import (
    Avg,
    Count,
    Exists,
    OuterRef,
    BooleanField,
    Value,
    Q,
)

from django.contrib.auth import get_user_model

from .models import Film
from .serializers import FilmSerializer
from favourites.models import Favourite
from watchlist.models import Watchlist

User = get_user_model()


class FilmViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Provides /api/films/  (list)
            /api/films/<id>/ (detail)

    Supports filters:
    - ?search=term
    - ?year=2023
    - ?min_rating=7
    - ?favourited=true
    - ?in_watchlist=true
    """

    serializer_class = FilmSerializer

    def get_queryset(self):
        request = self.request
        user = request.user
        params = request.query_params

        # prefetch M2M so nested genres/keywords/people are efficient
        qs = Film.objects.all().prefetch_related("genres", "keywords", "people")

        # basic filters
        search = params.get("search")
        if search:
            qs = qs.filter(title__icontains=search)

        year = params.get("year")
        if year:
            qs = qs.filter(year=year)

        # review stats
        qs = qs.annotate(
            average_rating=Avg("reviews__rating"),
            review_count=Count("reviews", distinct=True),
        )

        # user-specific flags
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

        # filters using annotations
        min_rating = params.get("min_rating")
        if min_rating:
            try:
                min_rating = float(min_rating)
                qs = qs.filter(average_rating__gte=min_rating)
            except ValueError:
                pass

        favourited = params.get("favourited")
        if favourited and favourited.lower() == "true" and user.is_authenticated:
            qs = qs.filter(is_favourited=True)

        in_watchlist = params.get("in_watchlist")
        if in_watchlist and in_watchlist.lower() == "true" and user.is_authenticated:
            qs = qs.filter(in_watchlist=True)

        return qs


class BlendView(APIView):
    """
    GET /api/blend/?film_a=<id>&film_b=<id>

    Returns top 5 films that "blend" the two picks.
    Only for authenticated users.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        film_a_id = request.query_params.get("film_a")
        film_b_id = request.query_params.get("film_b")

        if not film_a_id or not film_b_id:
            return Response(
                {"detail": "film_a and film_b query parameters are required."},
                status=400,
            )

        if film_a_id == film_b_id:
            return Response(
                {"detail": "Please choose two different films."},
                status=400,
            )

        try:
            # prefetch related M2M so get_ids is efficient
            film_a = (
                Film.objects
                .prefetch_related("genres", "keywords", "people")
                .get(pk=film_a_id)
            )
            film_b = (
                Film.objects
                .prefetch_related("genres", "keywords", "people")
                .get(pk=film_b_id)
            )
        except Film.DoesNotExist:
            return Response(
                {"detail": "One or both films were not found."},
                status=404,
            )

        # helper to pull related ids; assumes Film.genres / Film.keywords / Film.people M2M
        def get_ids(film, attr_name):
            related = getattr(film, attr_name, None)
            if related is None:
                return set()
            return set(related.values_list("id", flat=True))

        genres_a = get_ids(film_a, "genres")
        genres_b = get_ids(film_b, "genres")

        keywords_a = get_ids(film_a, "keywords")
        keywords_b = get_ids(film_b, "keywords")

        people_a = get_ids(film_a, "people")
        people_b = get_ids(film_b, "people")

        combined_genre_ids = genres_a | genres_b
        combined_keyword_ids = keywords_a | keywords_b
        combined_person_ids = people_a | people_b

        # base candidates: share at least one genre/keyword/person with A or B
        candidates = Film.objects.exclude(id__in=[film_a.id, film_b.id])

        filter_q = Q()
        if combined_genre_ids:
            filter_q |= Q(genres__id__in=combined_genre_ids)
        if combined_keyword_ids:
            filter_q |= Q(keywords__id__in=combined_keyword_ids)
        if combined_person_ids:
            filter_q |= Q(people__id__in=combined_person_ids)

        if filter_q:
            candidates = candidates.filter(filter_q).distinct()
        else:
            candidates = Film.objects.none()

        # score each candidate in Python
        scores = {}

        # weights – genres strongest, then keywords, then people
        W_GENRE = 2.0
        W_KEYWORD = 1.5
        W_PERSON = 1.0

        for film in candidates.prefetch_related("genres", "keywords", "people"):
            cg = set(get_ids(film, "genres"))
            ck = set(get_ids(film, "keywords"))
            cp = set(get_ids(film, "people"))

            score = (
                W_GENRE * (len(cg & genres_a) + len(cg & genres_b))
                + W_KEYWORD * (len(ck & keywords_a) + len(ck & keywords_b))
                + W_PERSON * (len(cp & people_a) + len(cp & people_b))
            )

            if score > 0:
                scores[film.id] = score

        if not scores:
            return Response({"results": []})

        # normalise to a 0–100 "fit_score"
        max_score = max(scores.values()) or 1.0

        ranked_ids = sorted(
            scores.keys(),
            key=lambda fid: scores[fid],
            reverse=True,
        )[:5]

        fit_scores = {
            fid: int(round(scores[fid] / max_score * 100))
            for fid in ranked_ids
        }

        # reuse annotations from FilmViewSet for these films
        user = request.user
        qs = Film.objects.filter(id__in=ranked_ids).prefetch_related(
            "genres", "keywords", "people"
        )

        qs = qs.annotate(
            average_rating=Avg("reviews__rating"),
            review_count=Count("reviews", distinct=True),
        )

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

        # preserve ranking order
        film_by_id = {f.id: f for f in qs}
        ordered_films = [film_by_id[fid] for fid in ranked_ids if fid in film_by_id]

        data = FilmSerializer(
            ordered_films,
            many=True,
            context={"request": request},
        ).data

        # attach fit_score
        for item in data:
            item["fit_score"] = fit_scores.get(item["id"], 0)

        return Response({"results": data})
