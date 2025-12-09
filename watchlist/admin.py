from django.contrib import admin
from .models import Watchlist


@admin.register(Watchlist)
class WatchlistAdmin(admin.ModelAdmin):
    list_display = ("user", "name", "film", "position", "created_at")
    search_fields = ("user__username", "film__title", "name")
    list_filter = ("name", "is_private")
