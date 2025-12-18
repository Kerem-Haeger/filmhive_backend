import uuid
from django.db import models
from django.contrib.auth import get_user_model
from films.models import Film

User = get_user_model()


class Favourite(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="favourites"
    )
    film = models.ForeignKey(
        Film, on_delete=models.CASCADE, related_name="favourited_by"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "film"],
                name="unique_favourite_per_user_and_film",
            )
        ]

    def __str__(self):
        return f"{self.user} → {self.film}"
