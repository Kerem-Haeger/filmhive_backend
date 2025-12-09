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
    genres = GenreSerializer(many=True, read_only=True)
    keywords = KeywordSerializer(many=True, read_only=True)
    people = PersonSerializer(many=True, read_only=True)

    average_rating = serializers.FloatField(read_only=True)
    review_count = serializers.IntegerField(read_only=True)
    is_favourited = serializers.BooleanField(read_only=True)
    in_watchlist = serializers.BooleanField(read_only=True)

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
            "average_rating",
            "review_count",
            "is_favourited",
            "in_watchlist",
        ]
