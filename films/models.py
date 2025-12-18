import uuid
from django.db import models


class Genre(models.Model):
    # ERD: id int [pk], name, tmdb_id unique
    id = models.IntegerField(primary_key=True)
    name = models.CharField(max_length=100)
    tmdb_id = models.IntegerField(unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Keyword(models.Model):
    # ERD: id int [pk], name, tmdb_id unique
    id = models.IntegerField(primary_key=True)
    name = models.CharField(max_length=100)
    tmdb_id = models.IntegerField(unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Person(models.Model):
    # ERD: id int [pk], name, tmdb_id unique
    id = models.IntegerField(primary_key=True)
    name = models.CharField(max_length=200)
    tmdb_id = models.IntegerField(unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Film(models.Model):
    # ERD: id uuid [pk], tmdb_id unique, title, year, poster_path, runtime,
    # critic_score, popularity, last_synced_at, created_at, updated_at
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tmdb_id = models.IntegerField(unique=True, null=True, blank=True)
    title = models.CharField(max_length=255)
    overview = models.TextField(null=True, blank=True)
    year = models.PositiveIntegerField()
    poster_path = models.CharField(max_length=500, blank=True)
    runtime = models.PositiveIntegerField(null=True, blank=True)
    critic_score = models.FloatField(null=True, blank=True)
    popularity = models.FloatField(null=True, blank=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)

    # convenience M2M fields that map to your join tables in the ERD
    genres = models.ManyToManyField(
        Genre,
        through="FilmGenre",
        related_name="films",
        blank=True,
    )
    keywords = models.ManyToManyField(
        Keyword,
        through="FilmKeyword",
        related_name="films",
        blank=True,
    )
    people = models.ManyToManyField(
        Person,
        through="FilmPerson",
        related_name="films",
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Add vote_count for filtering high-quality films
    vote_count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-year", "title"]
        indexes = [
            models.Index(fields=["year"]),
            models.Index(fields=["vote_count"]),
            models.Index(fields=["popularity"]),
        ]

    def __str__(self):
        return f"{self.title} ({self.year})"


class FilmGenre(models.Model):
    # ERD: id uuid [pk], film_id, genre_id, created_at, unique
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    film = models.ForeignKey(
        Film, on_delete=models.CASCADE, related_name="film_genres"
    )
    genre = models.ForeignKey(
        Genre, on_delete=models.CASCADE, related_name="film_genres"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("film", "genre")
        indexes = [
            models.Index(fields=["genre"]),
            models.Index(fields=["film"]),
        ]

    def __str__(self):
        return f"{self.film} – {self.genre}"


class FilmKeyword(models.Model):
    # ERD: id uuid [pk], film_id, keyword_id, created_at, unique
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    film = models.ForeignKey(
        Film, on_delete=models.CASCADE, related_name="film_keywords"
    )
    keyword = models.ForeignKey(
        Keyword, on_delete=models.CASCADE, related_name="film_keywords"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("film", "keyword")
        indexes = [
            models.Index(fields=["keyword"]),
            models.Index(fields=["film"]),
        ]

    def __str__(self):
        return f"{self.film} – {self.keyword}"


class FilmPerson(models.Model):
    # ERD: id uuid [pk], film_id, person_id, role, billing_order,
    # unique (film_id, person_id, role)
    ROLE_CHOICES = [
        ("director", "Director"),
        ("cast", "Cast"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    film = models.ForeignKey(
        Film, on_delete=models.CASCADE, related_name="film_people"
    )
    person = models.ForeignKey(
        Person, on_delete=models.CASCADE, related_name="film_people"
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    billing_order = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        unique_together = ("film", "person", "role")
        ordering = ["film", "role", "billing_order"]
        indexes = [
            models.Index(fields=["person", "role"]),
            models.Index(fields=["film"]),
        ]

    def __str__(self):
        return f"{self.person} ({self.role}) – {self.film}"
