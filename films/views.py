from rest_framework import viewsets, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.core.cache import cache

from django.db.models import (
    Avg,
    Count,
    Exists,
    OuterRef,
    BooleanField,
    Value,
    Q,
    Case,
    When,
    IntegerField,
    F,
)

from django.contrib.auth import get_user_model

from .models import Film
from .serializers import (
    FilmSerializer,
    ForYouFilmSerializer,
    CompromiseRequestSerializer,
    FilmCardLiteSerializer,
    CompromiseResultSerializer,
)
from .services.compromise import get_compromise_films
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
        
        # Check cache first (15 minute TTL)
        cache_key = f'for_you_recommendations_{user.id}'
        cached_result = cache.get(cache_key)
        if cached_result:
            return Response(cached_result)
        
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
        
        # Build director affinity map (average rating per director)
        director_affinity = {}
        user_reviews_for_affinity = Review.objects.filter(user=user).prefetch_related('film__people')
        for review in user_reviews_for_affinity:
            for person in review.film.people.filter(film_people__role='director'):
                if person.id not in director_affinity:
                    director_affinity[person.id] = {'total': 0, 'count': 0, 'name': person.name}
                director_affinity[person.id]['total'] += review.rating
                director_affinity[person.id]['count'] += 1
        
        # Calculate average affinity per director
        for director_id in director_affinity:
            total = director_affinity[director_id]['total']
            count = director_affinity[director_id]['count']
            director_affinity[director_id]['avg'] = total / count if count > 0 else 5.0
        
        # Build keyword affinity map (average rating per keyword)
        keyword_affinity = {}
        user_reviews_keywords = Review.objects.filter(user=user).prefetch_related('film__keywords')
        for review in user_reviews_keywords:
            for keyword in review.film.keywords.all():
                if keyword.id not in keyword_affinity:
                    keyword_affinity[keyword.id] = {'total': 0, 'count': 0, 'name': keyword.name}
                keyword_affinity[keyword.id]['total'] += review.rating
                keyword_affinity[keyword.id]['count'] += 1
        
        # Calculate average affinity per keyword
        for keyword_id in keyword_affinity:
            total = keyword_affinity[keyword_id]['total']
            count = keyword_affinity[keyword_id]['count']
            keyword_affinity[keyword_id]['avg'] = total / count if count > 0 else 5.0
        
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
        
        # Pre-filter candidates to drastically reduce the scoring pool
        candidates = Film.objects.all()
        
        # Build filter: films that match user's interests
        filter_q = Q()
        
        # 1. Must share at least one genre with user's preferences or liked films
        relevant_genre_ids = preferred_genre_ids | user_liked_genres
        if relevant_genre_ids:
            filter_q |= Q(genres__id__in=relevant_genre_ids)
        
        # 2. OR share directors with liked films
        if user_liked_directors:
            filter_q |= Q(people__id__in=user_liked_directors)
        
        # 3. OR share keywords with liked films (weaker signal, but still relevant)
        if user_liked_keywords:
            filter_q |= Q(keywords__id__in=user_liked_keywords)
        
        # 4. OR on user's watchlist (already showing interest)
        if watchlist_film_ids:
            filter_q |= Q(id__in=watchlist_film_ids)
        
        # If user has NO preferences at all, fall back to high-quality films
        if not filter_q:
            filter_q = Q(vote_count__gte=100)
        
        # Apply the filter
        candidates = candidates.filter(filter_q).distinct()
        
        # Exclude already-favourited films upfront (we won't recommend what they already love)
        if favourited_film_ids:
            candidates = candidates.exclude(id__in=favourited_film_ids)
        
        # Calculate genre overlap scores in database
        genre_overlap_score = Count(
            Case(
                When(genres__id__in=relevant_genre_ids, then=1),
                output_field=IntegerField()
            )
        ) if relevant_genre_ids else Value(0)
        
        # Calculate director overlap scores in database
        director_overlap_score = Count(
            Case(
                When(people__id__in=user_liked_directors, then=1),
                output_field=IntegerField()
            )
        ) if user_liked_directors else Value(0)
        
        # Calculate keyword overlap scores in database
        keyword_overlap_score = Count(
            Case(
                When(keywords__id__in=user_liked_keywords, then=1),
                output_field=IntegerField()
            )
        ) if user_liked_keywords else Value(0)
        
        # Annotate candidates with scores
        candidates = candidates.annotate(
            genre_match_count=genre_overlap_score,
            director_match_count=director_overlap_score,
            keyword_match_count=keyword_overlap_score,
            average_rating=Avg('reviews__rating'),
            review_count=Count('reviews', distinct=True),
            is_favourited=Exists(
                Favourite.objects.filter(user=user, film=OuterRef('pk'))
            ),
            in_watchlist=Exists(
                Watchlist.objects.filter(user=user, film=OuterRef('pk'))
            ),
        )
        
        # Filter to films with at least some signal (genre or director match)
        candidates = candidates.filter(
            Q(genre_match_count__gt=0) | Q(director_match_count__gt=0) | Q(in_watchlist=True)
        )
        
        # Exclude already-reviewed films
        if reviewed_film_ids:
            candidates = candidates.exclude(id__in=reviewed_film_ids)
        
        # Calculate a composite score - BRUTAL MODE
        # Only films hitting MULTIPLE strong signals reach high scores
        # Base: Genre (8 pts) + Director (5 pts) - very low!
        # Quality: Requires 1500+ votes AND 8.5+ score for decent points
        
        # Vote count bonus: Requires very high vote counts
        vote_count_bonus = Case(
            When(vote_count__gte=3000, then=Value(15)),
            When(vote_count__gte=2000, then=Value(12)),
            When(vote_count__gte=1500, then=Value(9)),
            When(vote_count__gte=1000, then=Value(6)),
            When(vote_count__gte=500, then=Value(3)),
            default=Value(0),
            output_field=IntegerField()
        )
        
        # Critic score bonus: Requires excellent ratings
        critic_score_bonus = Case(
            When(critic_score__gte=9.0, then=Value(10)),
            When(critic_score__gte=8.7, then=Value(8)),
            When(critic_score__gte=8.5, then=Value(6)),
            When(critic_score__gte=8.0, then=Value(3)),
            default=Value(0),
            output_field=IntegerField()
        )
        
        # Year proximity bonus: Only very close matches
        year_bonus = Case(
            When(year__isnull=True, then=Value(0)),
            default=Case(
                When(year__gte=avg_year - 3, year__lte=avg_year + 3, then=Value(5)) if avg_year else Value(0),
                When(year__gte=avg_year - 7, year__lte=avg_year + 7, then=Value(2)) if avg_year else Value(0),
                default=Value(0),
                output_field=IntegerField()
            ),
            output_field=IntegerField()
        ) if avg_year else Value(0)
        
        candidates = candidates.annotate(
            db_score=(
                F('genre_match_count') * 2 + 
                F('director_match_count') * 5 + 
                F('keyword_match_count') * 2 +
                vote_count_bonus +
                critic_score_bonus +
                year_bonus
            )
        )
        
        # Add a ceiling based on criteria: sweet spot 80-90%, 100% only for perfection
        max_score_ceiling = Case(
            When(
                genre_match_count__gte=3,
                director_match_count__gte=1,
                keyword_match_count__gte=2,
                vote_count__gte=2000,
                critic_score__gte=8.5,
                then=Value(100)  # Perfect match: 3+ genres + director + 2+ keywords + 2000+ votes + 8.5+ score
            ),
            When(
                genre_match_count__gte=3,
                director_match_count__gte=1,
                keyword_match_count__gte=1,
                then=Value(95)  # 3+ genres + director + keyword
            ),
            When(
                genre_match_count__gte=2,
                director_match_count__gte=1,
                keyword_match_count__gte=1,
                then=Value(85)  # 2+ genres + director + keyword
            ),
            When(
                genre_match_count__gte=3,
                director_match_count__gte=1,
                then=Value(75)  # 3+ genres + director
            ),
            When(
                genre_match_count__gte=2,
                director_match_count__gte=1,
                then=Value(70)  # 2+ genres + director
            ),
            When(
                genre_match_count__gte=3,
                keyword_match_count__gte=2,
                then=Value(68)  # 3+ genres + 2+ keywords
            ),
            When(
                genre_match_count__gte=3,
                keyword_match_count__gte=1,
                then=Value(65)  # 3+ genres + keyword
            ),
            When(
                genre_match_count__gte=2,
                keyword_match_count__gte=1,
                then=Value(62)  # 2+ genres + keyword
            ),
            When(
                genre_match_count__gte=2,
                then=Value(60)  # 2+ genres only
            ),
            default=Value(55)  # Single genre or director
        )
        
        candidates = candidates.annotate(
            max_score_ceiling=max_score_ceiling
        )
        
        # Order by composite score
        candidates = candidates.order_by('-db_score', '-vote_count')
        
        # Limit to top 100 candidates (still plenty for UX)
        candidates = candidates[:100]
        
        # Prefetch only what we need for serialization
        candidates = candidates.prefetch_related('genres', 'keywords')
        
        # Simplified scoring: use the DB score and build minimal reasons
        scored_films = []
        
        for film in candidates:
            film_id = str(film.id)
            
            # Use the DB-calculated score
            score = getattr(film, 'db_score', 0)
            
            # Apply genre affinity weighting
            # Recalculate the genre portion of the score based on user's history
            if film.genre_match_count > 0 and relevant_genre_ids and genre_affinity:
                original_genre_portion = film.genre_match_count * 3
                weighted_genre_portion = 0
                
                # For each genre in the film, apply affinity multiplier if we have history
                for genre in film.genres.all():
                    if genre.id in relevant_genre_ids:
                        base_score = 3
                        
                        # Look up user's affinity for this specific genre
                        if genre.id in genre_affinity:
                            avg_rating = genre_affinity[genre.id]['avg']
                            
                            # Apply smoother multiplier based on user's rating history
                            if avg_rating >= 8.0:
                                multiplier = 1.25  # User loves this genre
                            elif avg_rating >= 7.0:
                                multiplier = 1.1  # User likes it
                            elif avg_rating >= 6.0:
                                multiplier = 1.0  # Neutral
                            elif avg_rating >= 5.0:
                                multiplier = 0.95  # User meh about it
                            else:
                                multiplier = 0.85  # User dislikes it
                            
                            weighted_genre_portion += base_score * multiplier
                        else:
                            weighted_genre_portion += base_score
                
                # Replace the genre portion with weighted version
                score = score - original_genre_portion + weighted_genre_portion
            
            # Apply director affinity weighting
            if film.director_match_count > 0 and user_liked_directors and director_affinity:
                original_director_portion = film.director_match_count * 5
                weighted_director_portion = 0
                
                # For each director in the film, apply affinity multiplier
                for person in film.people.filter(film_people__role='director'):
                    if person.id in user_liked_directors:
                        base_score = 5
                        
                        # Look up user's affinity for this director
                        if person.id in director_affinity:
                            avg_rating = director_affinity[person.id]['avg']
                            
                            # Apply smoother multiplier
                            if avg_rating >= 8.0:
                                multiplier = 1.25
                            elif avg_rating >= 7.0:
                                multiplier = 1.1
                            elif avg_rating >= 6.0:
                                multiplier = 1.0
                            elif avg_rating >= 5.0:
                                multiplier = 0.95
                            else:
                                multiplier = 0.85
                            
                            weighted_director_portion += base_score * multiplier
                        else:
                            weighted_director_portion += base_score
                
                # Replace the director portion with weighted version
                score = score - original_director_portion + weighted_director_portion
            
            # Apply keyword affinity weighting
            if film.keyword_match_count > 0 and user_liked_keywords and keyword_affinity:
                original_keyword_portion = film.keyword_match_count * 2
                weighted_keyword_portion = 0
                
                # For each keyword in the film, apply affinity multiplier
                for keyword in film.keywords.all():
                    if keyword.id in user_liked_keywords:
                        base_score = 2
                        
                        # Look up user's affinity for this keyword
                        if keyword.id in keyword_affinity:
                            avg_rating = keyword_affinity[keyword.id]['avg']
                            
                            # Apply smoother multiplier
                            if avg_rating >= 8.0:
                                multiplier = 1.25
                            elif avg_rating >= 7.0:
                                multiplier = 1.1
                            elif avg_rating >= 6.0:
                                multiplier = 1.0
                            elif avg_rating >= 5.0:
                                multiplier = 0.95
                            else:
                                multiplier = 0.85
                            
                            weighted_keyword_portion += base_score * multiplier
                        else:
                            weighted_keyword_portion += base_score
                
                # Replace the keyword portion with weighted version
                score = score - original_keyword_portion + weighted_keyword_portion
            
            # Build simple reasons based on what matched
            reasons = []
            if film.genre_match_count > 0 and relevant_genre_ids:
                # Get matching genre names
                matching_genres = [g.name for g in film.genres.all() if g.id in relevant_genre_ids][:2]
                if matching_genres:
                    if len(matching_genres) == 1:
                        reasons.append(f"Matches your {matching_genres[0]} preference")
                    else:
                        reasons.append(f"Matches your {', '.join(matching_genres)} preferences")
            
            if film.keyword_match_count > 0 and len(reasons) < 2:
                reasons.append("Matches your themes")
            
            if film.director_match_count > 0 and len(reasons) < 2:
                reasons.append("Director you like")
            
            if film.in_watchlist and len(reasons) < 2:
                reasons.append("On your watchlist")
            
            # Use raw score, but ceiling acts as a FLOOR (minimum guarantee)
            # If film matches criteria, it gets boosted to at least the ceiling value
            score_ceiling = getattr(film, 'max_score_ceiling', 55)
            match_score = max(score_ceiling, min(100, int(score)))
            
            # Store film with score and reasons
            scored_films.append({
                'film': film,
                'match_score': match_score,
                'reasons': reasons[:2],
            })
        
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
        
        # Cache the result for 15 minutes
        cache.set(cache_key, serializer.data, 60 * 15)
        
        return Response(serializer.data)


class CompromiseView(APIView):
    """
    POST /api/compromise/

    Blend Mode: Find films that bridge two selected films.
    
    Input:
        - film_a_id (UUID): First reference film
        - film_b_id (UUID): Second reference film
        - alpha (float, 0-1, default 0.5): Weight for film_a's similarity
        - limit (int, default 20, max 50): Max results to return
    
    Returns:
        - meta: Request echo + pagination info
        - results: List of {film, score, match, reasons}
    
    Auth required: IsAuthenticated
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        """Handle POST request for compromise/blend."""
        # Validate input
        serializer = CompromiseRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Extract validated data
        film_a_id = serializer.validated_data["film_a_id"]
        film_b_id = serializer.validated_data["film_b_id"]
        alpha = serializer.validated_data["alpha"]
        limit = serializer.validated_data["limit"]

        # Fetch films from database
        try:
            film_a = Film.objects.get(id=film_a_id)
            film_b = Film.objects.get(id=film_b_id)
        except Film.DoesNotExist:
            return Response(
                {"detail": "One or both films not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Get compromise results using service
        scored_results = get_compromise_films(
            film_a=film_a,
            film_b=film_b,
            alpha=alpha,
            limit=limit,
        )

        # Build response
        meta = {
            "film_a_id": str(film_a_id),
            "film_b_id": str(film_b_id),
            "alpha": alpha,
            "limit": limit,
            "returned": len(scored_results),
        }

        # Serialize results
        results_data = []
        for result in scored_results:
            film_data = FilmCardLiteSerializer(result["film"]).data
            results_data.append({
                "film": film_data,
                "score": result["score"],
                "match": result["match"],
                "reasons": result["reasons"],
            })

        response_data = {
            "meta": meta,
            "results": results_data,
        }

        return Response(response_data, status=status.HTTP_200_OK)
