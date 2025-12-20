from django.core.management.base import BaseCommand
from django.utils import timezone

from films.tmdb import (
    fetch_discover_movies,
    fetch_movie_details,
    fetch_movie_keywords,
    fetch_movie_credits,
)

from films.models import Film, Genre, Keyword, Person, FilmPerson


class Command(BaseCommand):
    help = "Seed the database with films from TMDB using a balanced mix " \
            "(decades, genres, sorts)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--target",
            type=int,
            default=1500,
            help="Total number of films to have in the DB after seeding.",
        )
        parser.add_argument(
            "--pages-per-bucket",
            type=int,
            default=5,
            help="How many pages to fetch per bucket (20 films per page).",
        )
        parser.add_argument(
            "--min-vote-count",
            type=int,
            default=50,
            help=(
                    "Filter out films with fewer votes than this "
                    "(helps quality/mix)."
                ),
        )

    def handle(self, *args, **options):
        target = options["target"]
        pages_per_bucket = options["pages_per_bucket"]
        min_vote_count = options["min_vote_count"]

        existing_count = Film.objects.exclude(tmdb_id__isnull=True).count()
        if existing_count >= target:
            self.stdout.write(
                self.style.SUCCESS(
                        f"DB already has {existing_count} films "
                        f"(target {target}). Nothing to do."
                )
            )
            return

        self.stdout.write(
            f"DB has {existing_count} films. Target is {target}. Seeding..."
        )

        created_count = 0
        updated_count = 0
        skipped_existing = 0

        # A balanced set of "buckets" to avoid only-recent / only-popular bias
        buckets = [
            # Time periods
            {
                "label": "70s-80s popular",
                "params": {
                    "primary_release_date.gte": "1970-01-01",
                    "primary_release_date.lte": "1989-12-31",
                    "sort_by": "popularity.desc",
                },
            },
            {
                "label": "90s most voted",
                "params": {
                    "primary_release_date.gte": "1990-01-01",
                    "primary_release_date.lte": "1999-12-31",
                    "sort_by": "vote_count.desc",
                },
            },
            {
                "label": "00s popular",
                "params": {
                    "primary_release_date.gte": "2000-01-01",
                    "primary_release_date.lte": "2009-12-31",
                    "sort_by": "popularity.desc",
                },
            },
            {
                "label": "10s top rated",
                "params": {
                    "primary_release_date.gte": "2010-01-01",
                    "primary_release_date.lte": "2019-12-31",
                    "sort_by": "vote_average.desc",
                },
            },
            {
                "label": "20s popular",
                "params": {
                    "primary_release_date.gte": "2020-01-01",
                    "primary_release_date.lte": "2029-12-31",
                    "sort_by": "popularity.desc",
                },
            },
            # Genre variety (TMDB genre IDs)
            {
                "label": "Comedy",
                "params": {"with_genres": "35", "sort_by": "vote_count.desc"},
            },
            {
                "label": "Drama",
                "params": {"with_genres": "18", "sort_by": "vote_count.desc"},
            },
            {
                "label": "Horror",
                "params": {"with_genres": "27", "sort_by": "popularity.desc"},
            },
            {
                "label": "Romance",
                "params": {
                    "with_genres": "10749",
                    "sort_by": "popularity.desc",
                },
            },
            {
                "label": "Animation",
                "params": {"with_genres": "16", "sort_by": "vote_count.desc"},
            },
            {
                "label": "Documentary",
                "params": {"with_genres": "99", "sort_by": "vote_count.desc"},
            },
            {
                "label": "Sci-Fi",
                "params": {"with_genres": "878", "sort_by": "popularity.desc"},
            },
            {
                "label": "Thriller",
                "params": {"with_genres": "53", "sort_by": "popularity.desc"},
            },
        ]

        # Apply a quality filter everywhere
        for b in buckets:
            b["params"]["vote_count.gte"] = min_vote_count

        # Helper: one movie -> your existing save logic
        def upsert_movie(tmdb_id: int, teaser: dict):
            nonlocal created_count, updated_count

            title = teaser.get("title") or teaser.get("name") or "Untitled"
            release_date = teaser.get("release_date") or ""
            year = None
            if release_date:
                try:
                    year = int(release_date.split("-")[0])
                except (ValueError, IndexError):
                    year = None

            poster_path = teaser.get("poster_path") or ""
            critic_score = teaser.get("vote_average") or 0.0
            popularity = teaser.get("popularity") or 0.0
            vote_count = teaser.get("vote_count") or 0

            details = fetch_movie_details(tmdb_id)
            runtime = details.get("runtime")
            overview = details.get("overview")

            # If year missing in teaser, try from details
            if not year:
                rd = details.get("release_date") or ""
                if rd:
                    try:
                        year = int(rd.split("-")[0])
                    except (ValueError, IndexError):
                        year = None

            # Your model requires year (PositiveIntegerField)
            if not year:
                return False  # skip films without a year

            film_defaults = {
                "title": title,
                "year": year,
                "overview": overview,
                "poster_path": poster_path,
                "runtime": runtime,
                "critic_score": critic_score,
                "popularity": popularity,
                "vote_count": vote_count,
                "last_synced_at": timezone.now(),
            }

            film, created = Film.objects.update_or_create(
                tmdb_id=tmdb_id, defaults=film_defaults
            )

            if created:
                created_count += 1
                action = "Created"
            else:
                updated_count += 1
                action = "Updated"

            self.stdout.write(f"{action} film: {film.title} ({tmdb_id})")

            # ---------- Genres ----------
            tmdb_genres = details.get("genres", [])
            genre_instances = []
            for g in tmdb_genres:
                genre, _ = Genre.objects.get_or_create(
                    tmdb_id=g["id"],
                    defaults={"id": g["id"], "name": g["name"]},
                )
                genre_instances.append(genre)
            if hasattr(film, "genres"):
                film.genres.set(genre_instances)

            # ---------- Keywords ----------
            keywords_payload = fetch_movie_keywords(tmdb_id)
            tmdb_keywords = keywords_payload.get("keywords", [])
            keyword_instances = []
            for kw in tmdb_keywords[:10]:
                keyword, _ = Keyword.objects.get_or_create(
                    tmdb_id=kw["id"],
                    defaults={"id": kw["id"], "name": kw["name"]},
                )
                keyword_instances.append(keyword)
            if hasattr(film, "keywords"):
                film.keywords.set(keyword_instances)

            # ---------- People (directors + top 5 cast) ----------
            credits = fetch_movie_credits(tmdb_id)
            people_for_film = []

            for crew_member in credits.get("crew", []):
                if crew_member.get("job") == "Director":
                    person, _ = Person.objects.get_or_create(
                        tmdb_id=crew_member["id"],
                        defaults={
                            "id": crew_member["id"],
                            "name": crew_member["name"],
                        },
                    )
                    people_for_film.append((person, "director", 0))

            for cast_member in credits.get("cast", [])[:5]:
                person, _ = Person.objects.get_or_create(
                    tmdb_id=cast_member["id"],
                    defaults={
                        "id": cast_member["id"],
                        "name": cast_member["name"],
                    },
                )
                order = cast_member.get("order") or 0
                people_for_film.append((person, "cast", order))

            for person, role, billing_order in people_for_film:
                FilmPerson.objects.update_or_create(
                    film=film,
                    person=person,
                    role=role,
                    defaults={"billing_order": billing_order},
                )

            return True

        # Seed loop
        for bucket in buckets:
            current_total = Film.objects.exclude(tmdb_id__isnull=True).count()
            if current_total >= target:
                break

            self.stdout.write(f"\n=== Bucket: {bucket['label']} ===")

            for page in range(1, pages_per_bucket + 1):
                current_total = Film.objects.exclude(
                    tmdb_id__isnull=True
                ).count()
                if current_total >= target:
                    break

                self.stdout.write(
                    f"Fetching discover page {page} ({bucket['label']})..."
                )
                data = fetch_discover_movies(page=page, **bucket["params"])
                results = data.get("results", [])

                if not results:
                    break

                for teaser in results:
                    current_total = Film.objects.exclude(
                        tmdb_id__isnull=True
                    ).count()
                    if current_total >= target:
                        break

                    tmdb_id = teaser.get("id")
                    if not tmdb_id:
                        continue

                    # Check if already in DB
                    already_exists = Film.objects.filter(
                        tmdb_id=tmdb_id
                    ).exists()
                    if already_exists:
                        skipped_existing += 1
                        # Still update to refresh vote_count and other fields
                        upsert_movie(tmdb_id, teaser)
                    else:
                        upsert_movie(tmdb_id, teaser)

        final_total = Film.objects.exclude(tmdb_id__isnull=True).count()
        self.stdout.write(
            self.style.SUCCESS(
                    f"Done. Created {created_count}, updated {updated_count}, "
                    f"skipped existing {skipped_existing}. "
                    f"DB total now: {final_total} (target {target})."
            )
        )
