from __future__ import annotations

from django.contrib import admin
from django.db.models import QuerySet
from django.http import HttpRequest

from .models import DonationRequest, SwapRequest


@admin.register(SwapRequest)
class SwapRequestAdmin(admin.ModelAdmin):
    """Admin view for monitoring student-to-student swap requests."""

    list_display = ("requester", "receiver", "offered_book", "requested_book", "status", "created_at")
    list_filter = ("status", "created_at")
    search_fields = (
        "requester__username",
        "receiver__username",
        "offered_book__Book_name",
        "requested_book__Book_name",
    )
    date_hierarchy = "created_at"
    autocomplete_fields = ("requester", "receiver", "offered_book", "requested_book")
    list_select_related = ("requester", "receiver", "offered_book", "requested_book")

    def get_queryset(self, request: HttpRequest) -> QuerySet[SwapRequest]:
        return (
            super()
            .get_queryset(request)
            .select_related("requester", "receiver", "offered_book", "requested_book")
        )


@admin.register(DonationRequest)
class DonationRequestAdmin(admin.ModelAdmin):
    """Admin view for monitoring donation requests."""

    list_display = ("requester", "book", "status", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("requester__username", "book__Book_name")
    date_hierarchy = "created_at"
    autocomplete_fields = ("requester", "book")
    list_select_related = ("requester", "book")

    def get_queryset(self, request: HttpRequest) -> QuerySet[DonationRequest]:
        return super().get_queryset(request).select_related("requester", "book")
