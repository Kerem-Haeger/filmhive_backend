from rest_framework import serializers
from .models import Film, Genre, Keyword, Person


class GenreSerializer(serializers.ModelSerializer):
    class Meta:
        model = Genre
        fields = ["id", "name"]


class KeywordSerializer(serializers.ModelSerializer):
    class Meta:
        model = Keyword
        fields = ["id", "name"]


class PersonSerializer(serializers.ModelSerializer):
    class Meta:
        model = Person
        fields = ["id", "name"]


class FilmSerializer(serializers.ModelSerializer):
    # These use the ManyToMany relationships on Film (genres, keywords, people)
    genres = GenreSerializer(many=True, read_only=True)
    keywords = KeywordSerializer(many=True, read_only=True)
    people = PersonSerializer(many=True, read_only=True)

    class Meta:
        model = Film
        fields = [
            "id",
            "tmdb_id",
            "title",
            "year",
            "poster_path",
            "runtime",
            "critic_score",
            "popularity",
            "last_synced_at",
            "genres",
            "keywords",
            "people",
        ]
