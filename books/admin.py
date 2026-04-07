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
    PendingBook,
    Product,
    ShippingAddress,
    UserBehavior,
    UserGenrePreference,
    Wishlist,
)


admin.site.register(ShippingAddress)
admin.site.register(Wishlist)


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ('Book_name', 'quantity', 'get_total')
    can_delete = False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'order_status', 'cart_total', 'date_ordered', 'complete')
    list_filter  = ('order_status', 'complete', 'date_ordered')
    list_editable = ('order_status',)
    search_fields = ('user', 'transaction_id')
    ordering      = ('-date_ordered',)
    inlines       = [OrderItemInline]
    readonly_fields = ('date_ordered', 'transaction_id')

    @admin.display(description='Total')
    def cart_total(self, obj):
        return f'Rs. {obj.get_cart_total}'


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ('id', 'order', 'Book_name', 'quantity')
    list_select_related = ('order', 'Book_name')


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


# ── Pending-approval queue ────────────────────────────────────────────────────
@admin.register(PendingBook)
class PendingBookAdmin(admin.ModelAdmin):
    """Focused admin view: only sell-type books awaiting approval.

    Appears as '⏳ Pending Book Approvals' in the admin sidebar so it
    is impossible to miss. Each row has one-click Approve / Reject.
    """

    list_display = ('Book_name', 'Author', 'genre', 'price', 'seller_name', 'submitted_at', 'quick_actions')
    search_fields = ('Book_name', 'Author', 'seller__username')
    ordering = ('-pub_date',)
    list_select_related = ('seller',)
    # No add permission — books come in only via the bookshop form
    def has_add_permission(self, request):
        return False

    @admin.display(description='Seller', ordering='seller__username')
    def seller_name(self, obj):
        return obj.seller.username if obj.seller else '—'

    @admin.display(description='Submitted', ordering='pub_date')
    def submitted_at(self, obj):
        return obj.pub_date

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                '<path:object_id>/approve/',
                self.admin_site.admin_view(self._approve),
                name='books_pendingbook_approve',
            ),
            path(
                '<path:object_id>/reject/',
                self.admin_site.admin_view(self._reject),
                name='books_pendingbook_reject',
            ),
        ]
        return custom_urls + urls

    @admin.display(description='Actions')
    def quick_actions(self, obj):
        approve_url = reverse('admin:books_pendingbook_approve', args=[obj.pk])
        reject_url  = reverse('admin:books_pendingbook_reject',  args=[obj.pk])
        return format_html(
            '<a class="button" style="background:#28a745;color:#fff;padding:3px 10px;border-radius:4px;" href="{}">✓ Approve</a>&nbsp;'
            '<a class="deletelink" style="padding:3px 10px;border-radius:4px;" href="{}">✗ Reject</a>',
            approve_url, reject_url,
        )

    def _approve(self, request, object_id, *args, **kwargs):
        book = get_object_or_404(Product, pk=object_id)
        if not self.has_change_permission(request, book):
            raise PermissionDenied
        Product.objects.filter(pk=book.pk).update(listing_status='approved')
        self.message_user(request, f'✓ Approved "{book.Book_name}" — now live in the store.', messages.SUCCESS)
        return redirect('admin:books_pendingbook_changelist')

    def _reject(self, request, object_id, *args, **kwargs):
        book = get_object_or_404(Product, pk=object_id)
        if not self.has_change_permission(request, book):
            raise PermissionDenied
        Product.objects.filter(pk=book.pk).update(listing_status='rejected')
        self.message_user(request, f'✗ Rejected "{book.Book_name}".', messages.WARNING)
        return redirect('admin:books_pendingbook_changelist')


# ── Bookshop feature ────────────────────────────────────────────────────────
from authentication.models import UserProfile, BookshopProfile  # noqa: E402


@admin.register(BookshopProfile)
class BookshopProfileAdmin(admin.ModelAdmin):
    list_display = ('shop_name', 'user', 'location', 'is_verified', 'created_at')
    list_filter = ('is_verified',)
    search_fields = ('shop_name', 'user__username', 'location')
    actions = ('verify_shops',)
    readonly_fields = ('created_at',)

    def verify_shops(self, request, queryset):
        count = queryset.update(is_verified=True)
        self.message_user(request, f'Verified {count} bookshop(s).')
    verify_shops.short_description = 'Mark selected bookshops as verified'


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'created_at')
    list_filter = ('role',)
    search_fields = ('user__username',)
    readonly_fields = ('created_at',)


