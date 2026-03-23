from __future__ import annotations

from typing import Any

from django.contrib import admin, messages
from django.contrib.admin.sites import NotRegistered
from django.core.exceptions import PermissionDenied
from django.db.models import QuerySet
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import path, reverse
from django.utils.html import format_html

from .models import (  # noqa: F401
    Order,
    OrderItem,
    Product,
    ShippingAddress,
    UserBehavior,
    UserGenrePreference,
    Wishlist,
)


admin.site.register(Order)
admin.site.register(OrderItem)
admin.site.register(ShippingAddress)
admin.site.register(Wishlist)


try:
    admin.site.unregister(Product)
except NotRegistered:
    pass


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    """Admin for verifying peer-to-peer listings (swap/donate) and store items."""

    list_display = (
        "title",
        "seller",
        "listing_type",
        "price",
        "stock",
        "status",
        "created_at",
        "verification_actions",
    )
    list_filter = ("listing_status", "listing_type", "condition")
    search_fields = ("Book_name", "Author", "genre", "seller__username", "contact_email")
    readonly_fields = ("views", "image_preview")
    actions = ("approve_books", "reject_books")
    list_select_related = ("seller",)

    def get_queryset(self, request: HttpRequest) -> QuerySet[Product]:
        return super().get_queryset(request).select_related("seller")

    @admin.display(description="Title", ordering="Book_name")
    def title(self, obj: Product) -> str:
        return obj.Book_name

    @admin.display(description="Stock", ordering="quantity")
    def stock(self, obj: Product) -> int:
        return obj.quantity

    @admin.display(description="Status", ordering="listing_status")
    def status(self, obj: Product) -> str:
        return obj.listing_status

    @admin.display(description="Created At", ordering="pub_date")
    def created_at(self, obj: Product):
        return obj.pub_date

    @admin.display(description="Image")
    def image_preview(self, obj: Product) -> str:
        if not obj.image:
            return "-"
        try:
            return format_html(
                '<img src="{}" alt="Cover" style="max-height: 180px; width: auto;" />',
                obj.image.url,
            )
        except Exception:
            return "-"

    def approve_books(self, request: HttpRequest, queryset: QuerySet[Product]) -> None:
        """Bulk-approve selected books."""

        updated = queryset.update(listing_status="approved")
        self.message_user(
            request,
            f"Approved {updated} book(s).",
            level=messages.SUCCESS,
        )

    approve_books.short_description = "Approve selected books"  # type: ignore[attr-defined]

    def reject_books(self, request: HttpRequest, queryset: QuerySet[Product]) -> None:
        """Bulk-reject selected books."""

        updated = queryset.update(listing_status="rejected")
        self.message_user(
            request,
            f"Rejected {updated} book(s).",
            level=messages.SUCCESS,
        )

    reject_books.short_description = "Reject selected books"  # type: ignore[attr-defined]

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "<path:object_id>/approve/",
                self.admin_site.admin_view(self.approve_one),
                name="books_product_approve",
            ),
            path(
                "<path:object_id>/reject/",
                self.admin_site.admin_view(self.reject_one),
                name="books_product_reject",
            ),
        ]
        return custom_urls + urls

    @admin.display(description="Verify")
    def verification_actions(self, obj: Product) -> str:
        approve_url = reverse("admin:books_product_approve", args=[obj.pk])
        reject_url = reverse("admin:books_product_reject", args=[obj.pk])
        return format_html(
            '<a class="button" href="{}">Approve</a>\n'
            '<a class="deletelink" href="{}">Reject</a>',
            approve_url,
            reject_url,
        )

    def approve_one(self, request: HttpRequest, object_id: str, *args: Any, **kwargs: Any) -> HttpResponse:
        product = get_object_or_404(Product, pk=object_id)
        if not self.has_change_permission(request, product):
            raise PermissionDenied
        Product.objects.filter(pk=product.pk).update(listing_status="approved")
        self.message_user(request, f"Approved '{product.Book_name}'.", level=messages.SUCCESS)
        return redirect("admin:books_product_changelist")

    def reject_one(self, request: HttpRequest, object_id: str, *args: Any, **kwargs: Any) -> HttpResponse:
        product = get_object_or_404(Product, pk=object_id)
        if not self.has_change_permission(request, product):
            raise PermissionDenied
        Product.objects.filter(pk=product.pk).update(listing_status="rejected")
        self.message_user(request, f"Rejected '{product.Book_name}'.", level=messages.SUCCESS)
        return redirect("admin:books_product_changelist")


# Custom admin for better visualization
@admin.register(UserBehavior)
class UserBehaviorAdmin(admin.ModelAdmin):
    list_display = ('user', 'product', 'interaction_type', 'timestamp')
    list_filter = ('interaction_type', 'timestamp')
    search_fields = ('user', 'search_query')
    date_hierarchy = 'timestamp'


@admin.register(UserGenrePreference)
class UserGenrePreferenceAdmin(admin.ModelAdmin):
    list_display = ('user', 'last_updated')
    search_fields = ('user',)
    readonly_fields = ('last_updated',)


