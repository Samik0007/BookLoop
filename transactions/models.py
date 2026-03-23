from django.conf import settings
from django.db import models

from books.models import Product


class SwapRequest(models.Model):
    """Represents a swap offer between two users for two books.

    requester offers ``offered_book`` to ``receiver`` in exchange for
    ``requested_book``.
    """

    STATUS_CHOICES = (
        ("pending", "Pending"),
        ("accepted", "Accepted"),
        ("rejected", "Rejected"),
        ("completed", "Completed"),
    )

    requester = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="swap_requests_made",
    )
    receiver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="swap_requests_received",
    )

    # The book the requester wants
    requested_book = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="swap_requests_for_this_book",
    )
    # The book the requester is offering in exchange
    offered_book = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="swap_offers_with_this_book",
    )

    status = models.CharField(
        max_length=15,
        choices=STATUS_CHOICES,
        default="pending",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:  # pragma: no cover - simple representation
        return f"{self.requester} offers {self.offered_book.Book_name} for {self.requested_book.Book_name}"


class DonationRequest(models.Model):
    """Represents a request to receive a donated book."""

    STATUS_CHOICES = (
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("received", "Received"),
    )

    requester = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="donations_requested",
    )
    book = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="donation_requests",
    )
    reason = models.TextField(
        help_text=(
            "Briefly explain why you need this book "
            "(e.g., financial need, course requirement)."
        )
    )

    status = models.CharField(
        max_length=15,
        choices=STATUS_CHOICES,
        default="pending",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:  # pragma: no cover - simple representation
        return f"{self.requester} requested {self.book.Book_name}"
