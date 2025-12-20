from rest_framework import serializers
from .models import Watchlist


class WatchlistSerializer(serializers.ModelSerializer):
    user = serializers.ReadOnlyField(source="user.id")

    class Meta:
        model = Watchlist
        fields = [
            "id",
            "film",
            "user",
            "name",
            "is_private",
            "position",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["user", "created_at", "updated_at"]

    def validate(self, attrs):
        """
        Prevent adding the same film twice to the same list
        (name) for this user.
        """
        request = self.context.get("request")
        user = getattr(request, "user", None)

        film = attrs.get("film")
        # Allow client to omit name; use default from model
        name = attrs.get("name") or getattr(self.instance, "name", "Watchlist")

        if request and request.method == "POST":
            if user and user.is_authenticated and film:
                if Watchlist.objects.filter(
                    user=user, film=film, name=name
                ).exists():
                    raise serializers.ValidationError(
                        "This film is already in this watchlist."
                    )
        return attrs
