from django.core.management.base import BaseCommand
from django.utils import timezone

from films.tmdb import (
    fetch_popular_movies,
    fetch_movie_details,
    fetch_movie_keywords,
    fetch_movie_credits,
)

from films.models import Film, Genre, Keyword, Person, FilmPerson


class Command(BaseCommand):
    help = "Seed the database with films from TMDB (popular movies)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--pages",
            type=int,
            default=2,
            help="How many pages of popular movies to fetch (20 per page).",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=50,
            help="Maximum number of films to store.",
        )

    def handle(self, *args, **options):
        pages = options["pages"]
        limit = options["limit"]

        created_count = 0
        updated_count = 0

        for page in range(1, pages + 1):
            if created_count + updated_count >= limit:
                break

            self.stdout.write(f"Fetching popular movies page {page}...")
            data = fetch_popular_movies(page=page)
            results = data.get("results", [])

            for movie in results:
                if created_count + updated_count >= limit:
                    break

                tmdb_id = movie["id"]
                title = movie.get("title") or movie.get("name") or "Untitled"
                release_date = movie.get("release_date") or ""
                year = None
                if release_date:
                    try:
                        year = int(release_date.split("-")[0])
                    except (ValueError, IndexError):
                        year = None

                poster_path = movie.get("poster_path")
                critic_score = movie.get("vote_average") or 0.0
                popularity = movie.get("popularity") or 0.0

                # Fetch full details (runtime, genres, etc.)
                details = fetch_movie_details(tmdb_id)
                runtime = details.get("runtime")

                film_defaults = {
                    "title": title,
                    "year": year,
                    "poster_path": poster_path,
                    "runtime": runtime,
                    "critic_score": critic_score,
                    "popularity": popularity,
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
                        defaults={
                            "id": g["id"],     # your ERD uses int PK, not auto
                            "name": g["name"],
                        },
                    )
                    genre_instances.append(genre)

                if hasattr(film, "genres"):
                    film.genres.set(genre_instances)

                # ---------- Keywords ----------
                keywords_payload = fetch_movie_keywords(tmdb_id)
                tmdb_keywords = keywords_payload.get("keywords", [])
                keyword_instances = []

                for kw in tmdb_keywords[:10]:  # keep it small
                    keyword, _ = Keyword.objects.get_or_create(
                        tmdb_id=kw["id"],
                        defaults={
                            "id": kw["id"],   # int PK from ERD
                            "name": kw["name"],
                        },
                    )
                    keyword_instances.append(keyword)

                if hasattr(film, "keywords"):
                    film.keywords.set(keyword_instances)

                # ---------- People (directors + top 5 cast) ----------
                credits = fetch_movie_credits(tmdb_id)
                people_for_film = []

                # Directors from crew
                for crew_member in credits.get("crew", []):
                    if crew_member.get("job") == "Director":
                        person, _ = Person.objects.get_or_create(
                            tmdb_id=crew_member["id"],
                            defaults={
                                "id": crew_member["id"],   # int PK
                                "name": crew_member["name"],
                            },
                        )
                        people_for_film.append((person, "director", 0))

                # Top 5 cast
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

                # Create/update FilmPerson join rows
                for person, role, billing_order in people_for_film:
                    FilmPerson.objects.update_or_create(
                        film=film,
                        person=person,
                        role=role,
                        defaults={"billing_order": billing_order},
                    )

        self.stdout.write(
            self.style.SUCCESS(
                f"Done. Created {created_count} films, updated {updated_count} films."
            )
        )
