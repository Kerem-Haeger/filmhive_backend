from rest_framework import serializers
from .models import Review, ReviewLike


class ReviewSerializer(serializers.ModelSerializer):
    # Expose basic user info as read-only
    user = serializers.ReadOnlyField(source="user.id")
    user_username = serializers.ReadOnlyField(source="user.username")

    class Meta:
        model = Review
        fields = [
            "id",
            "film",
            "user",
            "user_username",
            "rating",
            "body",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["user", "user_username", "created_at", "updated_at"]

    def validate_rating(self, value):
        if value < 1 or value > 10:
            raise serializers.ValidationError("Rating must be between 1 and 10.")
        return value

    def validate(self, attrs):
        """
        Enforce: one review per user per film.
        """
        request = self.context.get("request")
        user = getattr(request, "user", None)

        # Film can come from incoming data or existing instance
        film = attrs.get("film") or getattr(self.instance, "film", None)

        if request and request.method in ("POST", "PUT", "PATCH"):
            if user and user.is_authenticated and film:
                qs = Review.objects.filter(user=user, film=film)
                # Exclude current instance on update
                if self.instance is not None:
                    qs = qs.exclude(pk=self.instance.pk)
                if qs.exists():
                    raise serializers.ValidationError(
                        "You have already reviewed this film."
                    )
        return attrs


class ReviewLikeSerializer(serializers.ModelSerializer):
    user = serializers.ReadOnlyField(source="user.id")
    user_username = serializers.ReadOnlyField(source="user.username")

    class Meta:
        model = ReviewLike
        fields = [
            "id",
            "review",
            "user",
            "user_username",
            "created_at",
        ]
        read_only_fields = ["user", "user_username", "created_at"]

    def validate(self, attrs):
        """
        Enforce: one like per user per review.
        """
        request = self.context.get("request")
        user = getattr(request, "user", None)
        review = attrs.get("review")

        if request and request.method == "POST":
            if user and user.is_authenticated and review:
                from .models import ReviewLike  # avoid circular import paranoia
                if ReviewLike.objects.filter(user=user, review=review).exists():
                    raise serializers.ValidationError(
                        "You have already liked this review."
                    )
        return attrs
