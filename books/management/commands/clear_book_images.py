from __future__ import annotations

from django.core.management.base import BaseCommand

from books.models import Product


class Command(BaseCommand):
    """Clear all Product.image values without triggering auto-fetch logic.

    This is intended as a one-time or occasional cleanup to remove
    mismatched or dummy images before relying on Cloudinary-backed
    auto-fetched covers.
    """

    help = "Clear image field for all Product (Book) records."

    def handle(self, *args, **options) -> None:
        # Count how many products currently have an image set
        affected = Product.objects.exclude(image__isnull=True).exclude(image="").count()

        # Bulk update avoids calling Product.save() and therefore
        # does NOT trigger the Open Library auto-fetch logic.
        Product.objects.update(image=None)

        self.stdout.write(self.style.SUCCESS(f"Cleared images for {affected} books."))
