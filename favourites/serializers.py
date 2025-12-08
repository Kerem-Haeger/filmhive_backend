from rest_framework import serializers
from .models import Favourite


class FavouriteSerializer(serializers.ModelSerializer):
    user = serializers.ReadOnlyField(source="user.id")

    class Meta:
        model = Favourite
        fields = [
            "id",
            "film",
            "user",
            "created_at",
        ]
        read_only_fields = ["user", "created_at"]

    def validate(self, attrs):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        film = attrs.get("film")

        if request and request.method == "POST":
            if user and user.is_authenticated and film:
                if Favourite.objects.filter(user=user, film=film).exists():
                    raise serializers.ValidationError(
                        "This film is already in your favourites."
                    )
        return attrs
