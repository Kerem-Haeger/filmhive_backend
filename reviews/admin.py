from django.contrib import admin
from .models import Review, ReviewLike, ReviewReport


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ("film", "user", "rating", "created_at")
    list_filter = ("rating", "film")
    search_fields = ("user__username", "film__title", "body")


@admin.register(ReviewLike)
class ReviewLikeAdmin(admin.ModelAdmin):
    list_display = ("review", "user", "created_at")
    search_fields = ("review__film__title", "user__username")


@admin.register(ReviewReport)
class ReviewReportAdmin(admin.ModelAdmin):
    list_display = ("review", "user", "created_at")
    search_fields = ("review__film__title", "user__username")
