"""
Compromise/Blend Mode service for finding films that blend two selected films.

Scoring is based on weighted Jaccard similarity of genres and keywords,
with a bonus for films overlapping with both input films.
"""

from typing import Dict, List, Tuple, Set
from django.db.models import QuerySet, Prefetch
from films.models import Film, Genre, Keyword


# Scoring weights and bonuses
GENRE_WEIGHT = 0.45
KEYWORD_WEIGHT = 0.55
BOTH_GENRES_BONUS = 0.05
BOTH_KEYWORDS_BONUS = 0.10


def _jaccard_similarity(set_a: Set, set_b: Set) -> float:
    """
    Compute Jaccard similarity between two sets.
    
    Args:
        set_a: First set
        set_b: Second set
    
    Returns:
        float between 0 and 1
    """
    if not set_a and not set_b:
        return 0.0
    
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    
    return intersection / union if union > 0 else 0.0


def _compute_similarity_score(
    candidate_genres: Set[int],
    candidate_keywords: Set[int],
    film_genres: Set[int],
    film_keywords: Set[int],
) -> Tuple[float, Dict[str, float]]:
    """
    Compute weighted similarity score between candidate and a reference film.
    
    Args:
        candidate_genres: Set of genre IDs for the candidate film
        candidate_keywords: Set of keyword IDs for the candidate film
        film_genres: Set of genre IDs for the reference film
        film_keywords: Set of keyword IDs for the reference film
    
    Returns:
        Tuple of (score, breakdown_dict)
    """
    genre_sim = _jaccard_similarity(candidate_genres, film_genres)
    keyword_sim = _jaccard_similarity(candidate_keywords, film_keywords)
    
    score = GENRE_WEIGHT * genre_sim + KEYWORD_WEIGHT * keyword_sim
    
    breakdown = {
        "genre_overlap": genre_sim,
        "keyword_overlap": keyword_sim,
    }
    
    return score, breakdown


def _build_explanation_strings(
    candidate: Film,
    shared_genres_a: Set[str],
    shared_genres_b: Set[str],
    shared_keywords_a: Set[str],
    shared_keywords_b: Set[str],
) -> List[str]:
    """
    Build human-readable explanation strings for why this film was recommended.
    
    Args:
        candidate: The candidate film object
        shared_genres_a: Genre names shared with film A
        shared_genres_b: Genre names shared with film B
        shared_keywords_a: Keyword names shared with film A
        shared_keywords_b: Keyword names shared with film B
    
    Returns:
        List of explanation strings
    """
    reasons = []
    
    # Genres shared with both
    both_genres = shared_genres_a & shared_genres_b
    if both_genres:
        reasons.append(f"Shared genres with both: {', '.join(sorted(both_genres))}")
    
    # Genres shared with only A
    only_a_genres = shared_genres_a - shared_genres_b
    if only_a_genres:
        reasons.append(f"Shared genres with A: {', '.join(sorted(only_a_genres))}")
    
    # Genres shared with only B
    only_b_genres = shared_genres_b - shared_genres_a
    if only_b_genres:
        reasons.append(f"Shared genres with B: {', '.join(sorted(only_b_genres))}")
    
    # Keywords shared with both
    both_keywords = shared_keywords_a & shared_keywords_b
    if both_keywords:
        reasons.append(f"Shared keywords with both: {', '.join(sorted(both_keywords))}")
    
    # Keywords shared with only A
    only_a_keywords = shared_keywords_a - shared_keywords_b
    if only_a_keywords:
        reasons.append(f"Shared keywords with A: {', '.join(sorted(only_a_keywords))}")
    
    # Keywords shared with only B
    only_b_keywords = shared_keywords_b - shared_keywords_a
    if only_b_keywords:
        reasons.append(f"Shared keywords with B: {', '.join(sorted(only_b_keywords))}")
    
    return reasons


def get_compromise_films(
    film_a: Film,
    film_b: Film,
    alpha: float = 0.5,
    limit: int = 20,
) -> List[Dict]:
    """
    Find films that "blend" two selected films using weighted Jaccard similarity.
    
    Args:
        film_a: First reference film
        film_b: Second reference film
        alpha: Weight for film_a's similarity (0-1). film_b gets (1-alpha). Default 0.5.
        limit: Max number of results to return. Default 20.
    
    Returns:
        List of dicts with structure:
        {
            "film": Film object (not serialized),
            "score": float (0-1),
            "match": dict with breakdown,
            "reasons": list of strings,
        }
    """
    
    # Prefetch all genres and keywords once
    film_a = Film.objects.filter(id=film_a.id).prefetch_related(
        "genres", "keywords"
    ).first()
    film_b = Film.objects.filter(id=film_b.id).prefetch_related(
        "genres", "keywords"
    ).first()
    
    if not film_a or not film_b:
        return []
    
    # Extract IDs as sets for faster lookup
    genres_a = set(film_a.genres.values_list("id", flat=True))
    keywords_a = set(film_a.keywords.values_list("id", flat=True))
    
    genres_b = set(film_b.genres.values_list("id", flat=True))
    keywords_b = set(film_b.keywords.values_list("id", flat=True))
    
    # Also keep name mappings for explanation strings
    genre_id_to_name_a = {g.id: g.name for g in film_a.genres.all()}
    genre_id_to_name_b = {g.id: g.name for g in film_b.genres.all()}
    keyword_id_to_name_a = {k.id: k.name for k in film_a.keywords.all()}
    keyword_id_to_name_b = {k.id: k.name for k in film_b.keywords.all()}
    
    # Build combined set of relevant IDs (union of both films)
    combined_genres = genres_a | genres_b
    combined_keywords = keywords_a | keywords_b
    
    # Fetch candidates: must share ≥1 genre OR keyword with either film
    candidates = Film.objects.exclude(
        id__in=[film_a.id, film_b.id]
    ).prefetch_related(
        "genres", "keywords"
    )
    
    # Filter to films sharing at least one genre or keyword
    if combined_genres or combined_keywords:
        from django.db.models import Q
        candidates = candidates.filter(
            Q(genres__id__in=combined_genres) | Q(keywords__id__in=combined_keywords)
        ).distinct()
    else:
        candidates = Film.objects.none()
    
    # Fetch all candidates with prefetched relations (evaluate the queryset once)
    candidates = list(candidates)
    
    # Score each candidate
    scored_results = []
    
    for candidate in candidates:
        # Use prefetched data (already loaded, no new queries)
        candidate_genres = set(g.id for g in candidate.genres.all())
        candidate_keywords = set(k.id for k in candidate.keywords.all())
        
        # Compute similarity to each film
        sim_a, breakdown_a = _compute_similarity_score(
            candidate_genres, candidate_keywords, genres_a, keywords_a
        )
        sim_b, breakdown_b = _compute_similarity_score(
            candidate_genres, candidate_keywords, genres_b, keywords_b
        )
        
        # Weighted pair score
        pair_score = alpha * sim_a + (1 - alpha) * sim_b
        
        # Bonuses for overlapping with both films
        bonus = 0.0
        if (candidate_genres & genres_a) and (candidate_genres & genres_b):
            bonus += BOTH_GENRES_BONUS
        if (candidate_keywords & keywords_a) and (candidate_keywords & keywords_b):
            bonus += BOTH_KEYWORDS_BONUS
        
        final_score = min(pair_score + bonus, 1.0)  # Cap at 1.0
        
        # Build match breakdown for response
        match_breakdown = {
            "genre_overlap_a": breakdown_a["genre_overlap"],
            "keyword_overlap_a": breakdown_a["keyword_overlap"],
            "genre_overlap_b": breakdown_b["genre_overlap"],
            "keyword_overlap_b": breakdown_b["keyword_overlap"],
            "bonus": bonus,
        }
        
        # Build explanation strings using prefetched data
        shared_genres_a = {g.name for g in candidate.genres.all() if g.id in genres_a}
        shared_genres_b = {g.name for g in candidate.genres.all() if g.id in genres_b}
        shared_keywords_a = {k.name for k in candidate.keywords.all() if k.id in keywords_a}
        shared_keywords_b = {k.name for k in candidate.keywords.all() if k.id in keywords_b}
        
        reasons = _build_explanation_strings(
            candidate,
            shared_genres_a,
            shared_genres_b,
            shared_keywords_a,
            shared_keywords_b,
        )
        
        scored_results.append({
            "film": candidate,
            "score": round(final_score, 3),
            "match": match_breakdown,
            "reasons": reasons,
        })
    
    # Sort by score descending and apply limit
    scored_results.sort(key=lambda x: x["score"], reverse=True)
    
    return scored_results[:limit]
