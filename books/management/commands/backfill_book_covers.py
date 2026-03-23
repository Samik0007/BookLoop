from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand

from books.models import Product


class Command(BaseCommand):
    """Backfill Cloudinary book covers for existing Products.

    For every Product without an image, this command calls ``save()``
    so that the model's auto-fetch logic (Open Library + Cloudinary)
    can try to populate ``image``. Products that already have an
    image are skipped.
    """

    help = "Auto-fetch and upload covers for existing books without images."

    def handle(self, *args: Any, **options: Any) -> None:
        qs = Product.objects.filter(image__isnull=True)
        total = qs.count()

        if total == 0:
            self.stdout.write(self.style.WARNING("No products without images found."))
            return

        self.stdout.write(f"Processing {total} products without images...")

        updated = 0
        for product in qs.iterator():
            # Calling save() without update_fields triggers the auto-fetch
            # logic in Product.save(), which is already wrapped in
            # try/except and will never raise on network issues.
            product.save()
            if product.image:
                updated += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Finished backfill: {updated} of {total} products received covers."
            )
        )
