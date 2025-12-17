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
from .serializers import FilmSerializer, ForYouFilmSerializer
from favourites.models import Favourite
from watchlist.models import Watchlist
from reviews.models import Review

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


class ForYouView(APIView):
    """
    GET /api/films/for-you/

    Returns personalized film recommendations based on user's preferences,
    favourites, reviews, and watchlist. Auth required.
    
    Response includes standard film fields + match_score (0-100) + reasons.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        
        # Get user's profile and preferred genres
        try:
            profile = user.profile
            preferred_genre_ids = set(profile.preferred_genres) if profile.preferred_genres else set()
        except:
            preferred_genre_ids = set()
        
        # If user hasn't set preferred genres, infer from their interactions
        if not preferred_genre_ids:
            # Get genres from favourited films
            fav_genre_ids = set(
                Favourite.objects.filter(user=user)
                .values_list('film__genres__id', flat=True)
            )
            # Get genres from highly-rated reviews (7+)
            reviewed_genre_ids = set(
                Review.objects.filter(user=user, rating__gte=7)
                .values_list('film__genres__id', flat=True)
            )
            preferred_genre_ids = fav_genre_ids | reviewed_genre_ids
            # Remove None values if any
            preferred_genre_ids.discard(None)
        
        # Build genre affinity map (average rating per genre)
        genre_affinity = {}
        user_reviews = Review.objects.filter(user=user).select_related('film').prefetch_related('film__genres')
        for review in user_reviews:
            for genre in review.film.genres.all():
                if genre.id not in genre_affinity:
                    genre_affinity[genre.id] = {'total': 0, 'count': 0, 'name': genre.name}
                genre_affinity[genre.id]['total'] += review.rating
                genre_affinity[genre.id]['count'] += 1
        
        # Calculate average affinity per genre
        for genre_id in genre_affinity:
            total = genre_affinity[genre_id]['total']
            count = genre_affinity[genre.id]['count']
            genre_affinity[genre_id]['avg'] = total / count if count > 0 else 5.0
        
        # Get user's interaction sets
        favourited_film_ids = set(
            Favourite.objects.filter(user=user).values_list('film_id', flat=True)
        )
        reviewed_film_ids = set(
            Review.objects.filter(user=user).values_list('film_id', flat=True)
        )
        highly_rated_film_ids = set(
            Review.objects.filter(user=user, rating__gte=7).values_list('film_id', flat=True)
        )
        watchlist_film_ids = set(
            Watchlist.objects.filter(user=user).values_list('film_id', flat=True)
        )
        
        # Get genres from user's favourite and highly-rated films for similarity matching
        user_liked_genres = set(
            Film.objects.filter(
                Q(id__in=favourited_film_ids) | Q(id__in=highly_rated_film_ids)
            ).values_list('genres__id', flat=True)
        )
        user_liked_genres.discard(None)
        
        # Get user's preferred directors (from favourited/highly-rated films)
        user_liked_directors = set(
            Film.objects.filter(
                Q(id__in=favourited_film_ids) | Q(id__in=highly_rated_film_ids)
            ).values_list('people__id', flat=True)
        )
        user_liked_directors.discard(None)
        
        # Get user's preferred keywords/themes
        user_liked_keywords = set(
            Film.objects.filter(
                Q(id__in=favourited_film_ids) | Q(id__in=highly_rated_film_ids)
            ).values_list('keywords__id', flat=True)
        )
        user_liked_keywords.discard(None)
        
        # Calculate user's preferred year range (from favourites/high ratings)
        liked_years = list(
            Film.objects.filter(
                Q(id__in=favourited_film_ids) | Q(id__in=highly_rated_film_ids)
            ).values_list('year', flat=True)
        )
        avg_year = sum(liked_years) / len(liked_years) if liked_years else None
        
        # Base candidate set: all films
        candidates = Film.objects.all().prefetch_related('genres', 'keywords', 'people')
        
        # Annotate with standard fields
        candidates = candidates.annotate(
            average_rating=Avg('reviews__rating'),
            review_count=Count('reviews', distinct=True),
            is_favourited=Exists(
                Favourite.objects.filter(user=user, film=OuterRef('pk'))
            ),
            in_watchlist=Exists(
                Watchlist.objects.filter(user=user, film=OuterRef('pk'))
            ),
        )
        
        # Score each film
        scored_films = []
        
        for film in candidates:
            film_id = str(film.id)
            film_genre_ids = set(film.genres.values_list('id', flat=True))
            film_director_ids = set(
                film.people.filter(film_people__role='director').values_list('id', flat=True)
            )
            film_keyword_ids = set(film.keywords.values_list('id', flat=True))
            
            # Skip if already interacted, unless it might score highly
            already_interacted = (
                film_id in favourited_film_ids or 
                film_id in reviewed_film_ids
            )
            
            # Calculate score components
            score = 0
            reasons = []
            
            # 1. Preferred genres overlap with progressive weighting + affinity
            if preferred_genre_ids and film_genre_ids:
                overlapping_genres = preferred_genre_ids & film_genre_ids
                genre_overlap_count = len(overlapping_genres)
                
                if genre_overlap_count > 0:
                    # Progressive weighting: 1=25, 2=40, 3+=60
                    if genre_overlap_count == 1:
                        base_genre_score = 25
                    elif genre_overlap_count == 2:
                        base_genre_score = 40
                    else:
                        base_genre_score = 60
                    
                    # Apply genre affinity multiplier if we have rating history
                    if genre_affinity:
                        # Calculate weighted affinity for overlapping genres
                        affinity_sum = sum(
                            genre_affinity.get(gid, {}).get('avg', 5.0) 
                            for gid in overlapping_genres
                        )
                        avg_affinity = affinity_sum / genre_overlap_count
                        # Scale affinity (5.0=neutral, 8+=boost, 4-=penalty)
                        affinity_multiplier = (avg_affinity / 5.0) * 0.5 + 0.5  # range: 0.5-1.5
                        base_genre_score = int(base_genre_score * affinity_multiplier)
                    
                    score += base_genre_score
                    
                    # Generate reason
                    matching_genres = film.genres.filter(id__in=preferred_genre_ids)
                    if matching_genres.exists():
                        genre_names = [g.name for g in matching_genres[:2]]
                        if len(genre_names) == 1:
                            reasons.append(f"Matches your {genre_names[0]} preference")
                        else:
                            reasons.append(f"Matches your {', '.join(genre_names)} preferences")
            
            # 2. Similar to favourites/highly-rated films (genre-level similarity)
            if user_liked_genres and film_genre_ids:
                similarity_overlap = len(user_liked_genres & film_genre_ids)
                if similarity_overlap > 0:
                    # Progressive: 1=15, 2=25, 3+=35
                    if similarity_overlap == 1:
                        similarity_score = 15
                    elif similarity_overlap == 2:
                        similarity_score = 25
                    else:
                        similarity_score = 35
                    
                    score += similarity_score
                    
                    if len(reasons) < 2:
                        reasons.append("Similar to your favourites")
            
            # 3. Director matching
            if user_liked_directors and film_director_ids:
                director_overlap = len(user_liked_directors & film_director_ids)
                if director_overlap > 0:
                    score += min(director_overlap * 20, 30)
                    if len(reasons) < 2:
                        director_names = [
                            d.name for d in film.people.filter(
                                id__in=user_liked_directors,
                                film_people__role='director'
                            )[:1]
                        ]
                        if director_names:
                            reasons.append(f"Director: {director_names[0]}")
            
            # 4. Keyword/theme matching
            if user_liked_keywords and film_keyword_ids:
                keyword_overlap = len(user_liked_keywords & film_keyword_ids)
                if keyword_overlap > 0:
                    # Keywords are weaker signal than genres
                    score += min(keyword_overlap * 5, 15)
            
            # 5. Year preference (within 10 years of user's preferred era)
            if avg_year and film.year:
                year_diff = abs(film.year - avg_year)
                if year_diff <= 10:
                    # Closer years get more points
                    year_score = int(10 - year_diff)
                    score += year_score
            
            # 6. Small boost if on watchlist (shows interest)
            if film_id in watchlist_film_ids:
                score += 10
                if len(reasons) < 2:
                    reasons.append("On your watchlist")
            
            # Skip already-interacted films unless they score highly
            if already_interacted and score < 70:
                continue
            
            # Skip films with zero score
            if score == 0:
                continue
            
            # Normalize to 0-100 scale (max theoretical: ~150 with all signals)
            match_score = min(int(score), 100)
            
            # Limit to max 2 reasons
            reasons = reasons[:2]
            
            # Store film with score and reasons
            scored_films.append({
                'film': film,
                'match_score': match_score,
                'reasons': reasons,
            })
        
        # Sort by match_score descending
        scored_films.sort(key=lambda x: x['match_score'], reverse=True)
        
        # Serialize films with match_score and reasons
        results = []
        for item in scored_films:
            film = item['film']
            # Set temporary attributes for serializer
            film.match_score = item['match_score']
            film.reasons = item['reasons']
            results.append(film)
        
        # Use ForYouFilmSerializer
        serializer = ForYouFilmSerializer(
            results,
            many=True,
            context={'request': request}
        )
        
        return Response(serializer.data)
