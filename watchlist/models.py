import uuid
from django.db import models
from django.contrib.auth import get_user_model
from films.models import Film

User = get_user_model()


class Watchlist(models.Model):
    """
    One row = one film in one of the user's lists.

    Later, we can expand this to have multiple lists per user, with
    names, privacy settings, and positions.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="watchlist_items",
    )
    film = models.ForeignKey(
        Film,
        on_delete=models.CASCADE,
        related_name="in_watchlists",
    )

    # ERD: name, is_private, position
    name = models.CharField(max_length=100, default="Watchlist")
    is_private = models.BooleanField(default=False)
    position = models.PositiveIntegerField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            # user can't add the same film twice to the same list name
            models.UniqueConstraint(
                fields=["user", "name", "film"],
                name="unique_watchlist_item_per_list",
            ),
        ]
        indexes = [
            # easy to query all lists for a user and list name
            models.Index(fields=["user", "name"]),
        ]
        ordering = ["user", "name", "position", "-created_at"]

    def __str__(self):
        return f"{self.user} – {self.name} – {self.film}"
