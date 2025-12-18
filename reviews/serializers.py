from rest_framework import serializers
from .models import Review, ReviewLike, ReviewReport


class ReviewSerializer(serializers.ModelSerializer):
    # Basic user info
    user = serializers.ReadOnlyField(source="user.id")
    user_username = serializers.ReadOnlyField(source="user.username")

    # Computed / frontend helper fields
    likes_count = serializers.IntegerField(read_only=True)
    liked_by_me = serializers.SerializerMethodField()
    my_like_id = serializers.SerializerMethodField()
    reported_by_me = serializers.SerializerMethodField()
    is_owner = serializers.SerializerMethodField()

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
            "likes_count",
            "liked_by_me",
            "my_like_id",
            "reported_by_me",
            "is_owner",
        ]
        read_only_fields = [
            "user",
            "user_username",
            "created_at",
            "updated_at",
            "likes_count",
            "liked_by_me",
            "my_like_id",
            "reported_by_me",
            "is_owner",
        ]

    # ---- Computed fields ----

    def get_is_owner(self, obj):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        return bool(user and user.is_authenticated and obj.user_id == user.id)

    def get_liked_by_me(self, obj):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return False
        return ReviewLike.objects.filter(user=user, review=obj).exists()

    def get_my_like_id(self, obj):
        """
        Needed so frontend can DELETE /api/review-likes/<id>/
        """
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return None

        like = (
            ReviewLike.objects.filter(user=user, review=obj).only("id").first()
        )
        return str(like.id) if like else None

    def get_reported_by_me(self, obj):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return False
        return ReviewReport.objects.filter(user=user, review=obj).exists()

    # ---- Validation ----

    def validate_rating(self, value):
        if value < 1 or value > 10:
            raise serializers.ValidationError(
                "Rating must be between 1 and 10."
            )
        return value

    def validate(self, attrs):
        """
        Enforce: one review per user per film.
        """
        request = self.context.get("request")
        user = getattr(request, "user", None)
        film = attrs.get("film") or getattr(self.instance, "film", None)

        if request and request.method in ("POST", "PUT", "PATCH"):
            if user and user.is_authenticated and film:
                qs = Review.objects.filter(user=user, film=film)
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
        request = self.context.get("request")
        user = getattr(request, "user", None)
        review = attrs.get("review")

        if request and request.method == "POST":
            if user and user.is_authenticated and review:
                if ReviewLike.objects.filter(
                    user=user, review=review
                ).exists():
                    raise serializers.ValidationError(
                        "You have already liked this review."
                    )
        return attrs


class ReviewReportSerializer(serializers.ModelSerializer):
    user = serializers.ReadOnlyField(source="user.id")
    user_username = serializers.ReadOnlyField(source="user.username")

    class Meta:
        model = ReviewReport
        fields = [
            "id",
            "review",
            "user",
            "user_username",
            "created_at",
        ]
        read_only_fields = ["user", "user_username", "created_at"]

    def validate(self, attrs):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        review = attrs.get("review")

        if request and request.method == "POST":
            if user and user.is_authenticated and review:
                if ReviewReport.objects.filter(
                    user=user, review=review
                ).exists():
                    raise serializers.ValidationError(
                        "You have already reported this review."
                    )
        return attrs
