from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils import timezone


class UserInteraction(models.Model):
    """Implicit feedback signal between a user and a book (Product).

    This model centralizes interactions like views, wishlist, cart, and purchases
    with an associated integer weight for recommendation purposes.
    """

    ACTION_VIEW = "view"
    ACTION_WISHLIST = "wishlist"
    ACTION_CART = "cart"
    ACTION_PURCHASE = "purchase"

    ACTION_CHOICES = (
        (ACTION_VIEW, "View"),
        (ACTION_WISHLIST, "Wishlist"),
        (ACTION_CART, "Cart"),
        (ACTION_PURCHASE, "Purchase"),
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="book_interactions",
    )
    # In this project, the logical "Book" is the Product model from books.models
    book = models.ForeignKey(
        "books.Product",
        on_delete=models.CASCADE,
        related_name="user_interactions",
    )
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    weight = models.IntegerField(default=1)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = ("user", "book", "action")
        ordering = ["-created_at"]

    def __str__(self) -> str:  # pragma: no cover - simple representation
        return f"{self.user_id}-{self.book_id}-{self.action}-{self.weight}"
