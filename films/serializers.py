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
            "overview",
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


class ForYouFilmSerializer(FilmSerializer):
    """Extends FilmSerializer with recommendation-specific fields."""
    match_score = serializers.IntegerField(read_only=True)
    reasons = serializers.ListField(
        child=serializers.CharField(),
        read_only=True,
    )

    class Meta(FilmSerializer.Meta):
        fields = FilmSerializer.Meta.fields + ["match_score", "reasons"]


class FilmCardLiteSerializer(serializers.ModelSerializer):
    """Lightweight film card for /compromise/ and similar endpoints."""
    class Meta:
        model = Film
        fields = ["id", "title", "year", "poster_path", "runtime", "critic_score", "popularity"]


class CompromiseRequestSerializer(serializers.Serializer):
    """Validates input for the /compromise/ endpoint."""
    film_a_id = serializers.UUIDField(required=True)
    film_b_id = serializers.UUIDField(required=True)
    alpha = serializers.FloatField(required=False, default=0.5)
    limit = serializers.IntegerField(required=False, default=20)

    def validate_alpha(self, value):
        """Ensure alpha is between 0 and 1."""
        if not (0 <= value <= 1):
            raise serializers.ValidationError(
                "alpha must be between 0 and 1 (inclusive)."
            )
        return value

    def validate_limit(self, value):
        """Ensure limit is within acceptable range."""
        if value <= 0:
            raise serializers.ValidationError("limit must be greater than 0.")
        if value > 50:
            raise serializers.ValidationError(
                "limit cannot exceed 50 (hard cap for performance)."
            )
        return value

    def validate(self, attrs):
        """Ensure film_a_id and film_b_id are different."""
        if attrs["film_a_id"] == attrs["film_b_id"]:
            raise serializers.ValidationError(
                "film_a_id and film_b_id must be different films."
            )
        return attrs


class CompromiseResultSerializer(serializers.Serializer):
    """Serializes a single result from the /compromise/ endpoint."""
    film = FilmCardLiteSerializer()
    score = serializers.FloatField()
    match = serializers.DictField(child=serializers.FloatField())
    reasons = serializers.ListField(child=serializers.CharField())


class CompromiseResponseSerializer(serializers.Serializer):
    """Serializes the full response from the /compromise/ endpoint."""
    meta = serializers.DictField()
    results = CompromiseResultSerializer(many=True)
