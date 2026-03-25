import random
from datetime import datetime
import re
from io import BytesIO

import requests
from django.core.management.base import BaseCommand
from django.utils import timezone
from PIL import Image

from books.models import Product
from cloudinary.uploader import upload as cloudinary_upload


class Command(BaseCommand):
    help = "Seeds the database with books from the Google Books API."

    def add_arguments(self, parser):
        parser.add_argument(
            "--per-genre",
            type=int,
            default=15,
            help="Maximum number of books to fetch per genre (default: 15)",
        )
        parser.add_argument(
            "--genres",
            nargs="+",
            help=(
                "Optional list of genres to fetch. "
                "If omitted, a sensible default set is used."
            ),
        )

    def handle(self, *args, **options):
        default_genres = [
            "Computer Science",
            "Business",
            "Psychology",
            "Fiction",
            "Science",
            "Mathematics",
            "Self-Help",
        ]

        genres = options.get("genres") or default_genres
        per_genre = options.get("per-genre") or 15

        session = requests.Session()
        total_created = 0
        total_skipped = 0

        for genre in genres:
            self.stdout.write(self.style.NOTICE(f"\n📖 Fetching books for genre: {genre}"))

            params = {
                "q": f"subject:{genre}",
                "maxResults": per_genre,
                "langRestrict": "en",
            }

            try:
                response = session.get(
                    "https://www.googleapis.com/books/v1/volumes",
                    params=params,
                    timeout=5,
                )
                response.raise_for_status()
            except Exception as exc:  # noqa: BLE001
                self.stderr.write(
                    self.style.ERROR(
                        f"  ✗ Failed to fetch from Google Books for '{genre}': {exc}"
                    )
                )
                continue

            data = response.json() or {}
            items = data.get("items", [])
            if not items:
                self.stdout.write(
                    self.style.WARNING(
                        f"  - No items returned by Google Books for genre '{genre}'"
                    )
                )
                continue

            for item in items:
                volume_info = item.get("volumeInfo") or {}

                title = (volume_info.get("title") or "").strip()
                if not title:
                    continue

                authors = volume_info.get("authors") or []
                author_str = ", ".join(authors).strip() or "Unknown"

                categories = volume_info.get("categories") or [genre]
                category_str = ", ".join(categories)

                description = (volume_info.get("description") or "").strip()
                if not description:
                    description = f"{title} by {author_str} ({genre})"
                description = description[:1000]

                published_raw = (volume_info.get("publishedDate") or "").strip()
                pub_date = timezone.now().date()
                if published_raw:
                    pub_date = self._safe_parse_date(published_raw, fallback=pub_date)

                # Avoid duplicates based on title + author (case-insensitive)
                if Product.objects.filter(
                    Book_name__iexact=title[:50],
                    Author__iexact=author_str[:50],
                ).exists():
                    total_skipped += 1
                    self.stdout.write(
                        self.style.WARNING(f"  - Skipped (already exists): {title}")
                    )
                    continue

                # Random but realistic pricing and stock in NPR
                price = random.randint(250, 1500)
                quantity = random.randint(5, 40)

                # Try to upload cover image to Cloudinary
                image_public_id = None
                image_links = volume_info.get("imageLinks") or {}
                image_url = self._pick_best_google_image_url(image_links)
                if image_url and not self._looks_like_placeholder_url(image_url):
                    try:
                        image_url = self._to_high_res_google_books_url(image_url)
                        image_bytes = self._download_image_bytes(session, image_url)
                        if image_bytes and self._image_is_usable(image_bytes, min_dim=220):
                            upload_result = cloudinary_upload(
                                BytesIO(image_bytes),
                                folder="bookloop_covers",
                            )
                            if isinstance(upload_result, dict):
                                image_public_id = upload_result.get("public_id")
                    except Exception:  # noqa: BLE001
                        # Fail silently; Product.save() can still auto-fetch
                        image_public_id = None

                product = Product(
                    Book_name=title[:50],
                    Author=author_str[:50],
                    genre=category_str[:300],
                    description=description,
                    price=price,
                    pub_date=pub_date,
                    quantity=quantity,
                )

                if image_public_id:
                    product.image = image_public_id

                product.save()
                total_created += 1
                self.stdout.write(
                    self.style.SUCCESS(f"  ✓ Created: {product.Book_name} ({genre})")
                )

        self.stdout.write(self.style.SUCCESS("\n📚 Seeding complete"))
        self.stdout.write(self.style.SUCCESS(f"   Created: {total_created} books"))
        self.stdout.write(self.style.WARNING(f"   Skipped: {total_skipped} books"))
        self.stdout.write(
            self.style.SUCCESS(
                f"   Total in database: {Product.objects.count()} books"
            )
        )

    def _safe_parse_date(self, raw: str, fallback):
        """Parse Google Books publishedDate into a Python date.

        Google Books may return dates as:
        - YYYY
        - YYYY-MM
        - YYYY-MM-DD
        This helper normalizes these into a ``date`` object, or returns
        ``fallback`` on failure.
        """

        try:
            if len(raw) == 4:
                return datetime.strptime(raw, "%Y").date()
            if len(raw) == 7:
                return datetime.strptime(raw, "%Y-%m").date()
            if len(raw) == 10:
                return datetime.strptime(raw, "%Y-%m-%d").date()
        except Exception:  # noqa: BLE001
            return fallback
        return fallback

    def _to_high_res_google_books_url(self, url: str) -> str:
        """Normalize a Google Books thumbnail URL to a higher-quality variant.

        Google often returns ``zoom=1`` thumbnails and may include
        ``edge=curl``. For crisper covers, we force ``zoom=0`` and remove
        edge curl.
        """

        if not url:
            return url

        # Prefer https
        url = url.replace("http://", "https://")

        # Force the highest zoom level Google Books exposes in this endpoint.
        if "zoom=" in url:
            url = re.sub(r"zoom=\d+", "zoom=0", url)
        else:
            joiner = "&" if "?" in url else "?"
            url = f"{url}{joiner}zoom=0"

        # Remove curl effect which can degrade perceived sharpness
        url = url.replace("&edge=curl", "").replace("edge=curl&", "")
        return url

    def _pick_best_google_image_url(self, image_links: dict) -> str | None:
        """Pick the highest-quality image URL Google Books provides."""

        if not isinstance(image_links, dict):
            return None

        for key in ("extraLarge", "large", "medium", "thumbnail", "smallThumbnail"):
            url = (image_links.get(key) or "").strip()
            if url:
                return url
        return None

    def _looks_like_placeholder_url(self, url: str) -> bool:
        """Heuristic filter for known placeholder/no-photo style URLs."""

        lowered = (url or "").lower()
        return any(token in lowered for token in ("nophoto", "no_photo", "placeholder", "noimage", "no_image", "default"))

    def _download_image_bytes(self, session: requests.Session, url: str) -> bytes | None:
        """Download image bytes once so we can validate resolution before uploading."""

        if not url:
            return None

        resp = session.get(url, timeout=5)
        resp.raise_for_status()
        content_type = (resp.headers.get("Content-Type") or "").lower()
        if content_type and not content_type.startswith("image/"):
            return None
        return resp.content

    def _image_is_usable(self, image_bytes: bytes, *, min_dim: int) -> bool:
        """Reject tiny thumbnails that will look blurry when scaled up."""

        if not image_bytes:
            return False

        try:
            with Image.open(BytesIO(image_bytes)) as img:
                width, height = img.size
        except Exception:  # noqa: BLE001
            return False

        return min(width, height) >= int(min_dim)
