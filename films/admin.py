from django.contrib import admin
from .models import (
    Film,
    Genre,
    Keyword,
    Person,
    FilmGenre,
    FilmKeyword,
    FilmPerson,
)


@admin.register(Film)
class FilmAdmin(admin.ModelAdmin):
    list_display = ("title", "year", "critic_score", "popularity")
    search_fields = ("title",)
    list_filter = ("year", "genres")


admin.site.register(Genre)
admin.site.register(Keyword)
admin.site.register(Person)
admin.site.register(FilmGenre)
admin.site.register(FilmKeyword)
admin.site.register(FilmPerson)
