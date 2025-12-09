from django.contrib import admin
from .models import Favourite


@admin.register(Favourite)
class FavouriteAdmin(admin.ModelAdmin):
    list_display = ("user", "film", "created_at")
    search_fields = ("user__username", "film__title")
    list_filter = ("created_at",)
