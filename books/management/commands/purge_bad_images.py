from __future__ import annotations

from io import BytesIO
from typing import Any

import requests
from django.core.management.base import BaseCommand
from django.db.models import QuerySet
from PIL import Image

from books.models import Product


class Command(BaseCommand):
    """Purge blurry / repeated placeholder covers.

    This command is designed to fix existing bad data *already stored* in
    Cloudinary by clearing `Product.image` for:

    - Images that are too small (low resolution) and will look blurry.
    - Images that are duplicated across many books (typical of API placeholders).

    After running this, you can run `python manage.py backfill_book_covers`
    to re-fetch better Open Library large covers (`-L.jpg`) for cleared items.
    """

    help = "Purge low-res or duplicated placeholder book covers."  # noqa: A003

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--genre",
            default="Nepali",
            help="Only scan products whose genre contains this value (default: Nepali). Use 'all' to scan everything.",
        )
        parser.add_argument(
            "--min-dim",
            type=int,
            default=220,
            help="Minimum allowed image dimension (min(width,height)). Smaller images are purged.",
        )
        parser.add_argument(
            "--min-duplicates",
            type=int,
            default=4,
            help="If the exact same image appears at least this many times, treat it as a placeholder and purge it.",
        )
        parser.add_argument(
            "--phash",
            action="store_true",
            help="Use a perceptual hash to detect duplicates (recommended; robust to recompression).",
        )
        parser.add_argument(
            "--max-items",
            type=int,
            default=0,
            help="Optional cap on how many products to scan (0 means no limit).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would be purged without changing the database.",
        )
        parser.add_argument(
            "--purge-nepali-not-curated",
            action="store_true",
            help=(
                "If set, also purge images for Nepali-genre products whose titles are not in the curated Nepali seeder list."
            ),
        )

    def handle(self, *args: Any, **options: Any) -> None:
        genre = (options.get("genre") or "Nepali").strip()
        min_dim = int(options.get("min_dim") or 220)
        min_duplicates = int(options.get("min_duplicates") or 4)
        max_items = int(options.get("max_items") or 0)
        dry_run = bool(options.get("dry_run"))
        use_phash = bool(options.get("phash"))
        purge_nepali_not_curated = bool(options.get("purge_nepali_not_curated"))

        qs = self._base_queryset(genre)
        total = qs.count()
        if total == 0:
            self.stdout.write(self.style.WARNING("No products with images matched the filter."))
            return

        if max_items > 0:
            qs = qs.order_by("id")[:max_items]
            total = qs.count()

        self.stdout.write(
            self.style.NOTICE(
                f"Scanning {total} products (genre={genre!r}, min_dim={min_dim}, min_duplicates={min_duplicates})..."
            )
        )

        session = requests.Session()

        # First pass: compute hashes + sizes
        hash_to_ids: dict[str, list[int]] = {}
        low_res_ids: set[int] = set()
        nepali_not_curated_ids: set[int] = set()
        fetch_failed = 0

        curated_nepali_titles = {
            # Keep in sync with books/management/commands/seed_nepali_books.py
            "palpasa cafe",
            "karnali blues",
            "seto dharti",
            "shirishko phool (the blue mimosa)",
            "muna madan",
            "china harayeko manchhe",
            "summer love",
            "saaya",
            "radha",
            "basain",
            "pagal basti",
            "jhola",
            "antarmann ko yatra",
            "firfire",
            "sumnima",
            "doshi chasma",
            "ek chihan",
            "jiwan kada ki phool",
            "ghumne mech mathi andho manche",
            "madhavi",
        }

        for product in qs.iterator():
            if purge_nepali_not_curated and (product.genre or "").lower().find("nepali") != -1:
                title_key = (product.Book_name or "").strip().lower()
                if title_key and title_key not in curated_nepali_titles:
                    nepali_not_curated_ids.add(product.id)

            url = self._safe_image_url(product)
            if not url:
                continue

            try:
                image_bytes = self._download_image_bytes(session, url)
                if not image_bytes:
                    fetch_failed += 1
                    continue

                if use_phash:
                    digest = self._average_hash(image_bytes)
                else:
                    digest = self._byte_hash(image_bytes)
                hash_to_ids.setdefault(digest, []).append(product.id)

                width, height = self._image_size(image_bytes)
                if min(width, height) < min_dim:
                    low_res_ids.add(product.id)
            except Exception:
                fetch_failed += 1
                continue

        duplicate_ids: set[int] = set()
        for digest, ids in hash_to_ids.items():
            if len(ids) >= min_duplicates:
                duplicate_ids.update(ids)

        ids_to_purge = set(low_res_ids) | set(duplicate_ids) | set(nepali_not_curated_ids)

        self.stdout.write(self.style.NOTICE(f"Fetch failures (skipped): {fetch_failed}"))
        self.stdout.write(self.style.NOTICE(f"Low-res images to purge: {len(low_res_ids)}"))
        self.stdout.write(self.style.NOTICE(f"Duplicated placeholder images to purge: {len(duplicate_ids)}"))
        if purge_nepali_not_curated:
            self.stdout.write(
                self.style.NOTICE(
                    f"Nepali not-curated images to purge: {len(nepali_not_curated_ids)}"
                )
            )
        self.stdout.write(self.style.NOTICE(f"Total unique products to purge: {len(ids_to_purge)}"))

        if not ids_to_purge:
            self.stdout.write(self.style.SUCCESS("Nothing to purge."))
            return

        if dry_run:
            self.stdout.write(self.style.WARNING("Dry run: no changes applied."))
            return

        updated = Product.objects.filter(id__in=list(ids_to_purge)).update(image=None)
        self.stdout.write(self.style.SUCCESS(f"Purged image for {updated} products."))
        self.stdout.write(
            self.style.NOTICE(
                "Next: run `./.venv/bin/python manage.py backfill_book_covers` to re-fetch better covers for cleared items."
            )
        )

    def _base_queryset(self, genre: str) -> QuerySet[Product]:
        qs = Product.objects.exclude(image__isnull=True).exclude(image="")
        if genre.lower() != "all":
            qs = qs.filter(genre__icontains=genre)
        return qs

    def _safe_image_url(self, product: Product) -> str | None:
        try:
            return (product.image.url or "").strip() or None
        except Exception:
            return None

    def _download_image_bytes(self, session: requests.Session, url: str) -> bytes | None:
        resp = session.get(url, timeout=5)
        resp.raise_for_status()

        content_type = (resp.headers.get("Content-Type") or "").lower()
        if content_type and not content_type.startswith("image/"):
            return None

        return resp.content

    def _image_size(self, image_bytes: bytes) -> tuple[int, int]:
        with Image.open(BytesIO(image_bytes)) as img:
            return img.size

    def _byte_hash(self, image_bytes: bytes) -> str:
        """Fast non-cryptographic hash for grouping identical-bytes images."""

        # Python's hash() is salted per-process; use a stable representation.
        # Using the first/last chunks keeps this relatively fast while stable.
        head = image_bytes[:4096]
        tail = image_bytes[-4096:] if len(image_bytes) > 4096 else b""
        return (head + tail).hex()

    def _average_hash(self, image_bytes: bytes) -> str:
        """Compute a simple 64-bit average hash (aHash) for perceptual dedupe."""

        with Image.open(BytesIO(image_bytes)) as img:
            img = img.convert("L").resize((8, 8), Image.Resampling.LANCZOS)
            pixels = list(img.getdata())
        avg = sum(pixels) / len(pixels)
        bits = "".join("1" if px >= avg else "0" for px in pixels)
        return hex(int(bits, 2))[2:].zfill(16)
