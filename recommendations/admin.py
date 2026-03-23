from django.contrib import admin

from .models import UserInteraction


@admin.register(UserInteraction)
class UserInteractionAdmin(admin.ModelAdmin):
    list_display = ("user", "book", "action", "weight", "created_at")
    list_filter = ("action", "created_at")
    search_fields = ("user__username", "book__Book_name")
