from __future__ import annotations

import time
from typing import Any

import requests
from cloudinary.uploader import upload as cloudinary_upload
from django.core.management.base import BaseCommand
from django.db.models import Q

from books.models import (
    Product,
    _looks_like_placeholder_url,
    _normalize_google_books_image_url,
    _pick_best_google_image_link,
)


class Command(BaseCommand):
    """Backfill Cloudinary book covers for existing Products.

    Optimized behaviour:
    - Reuses a single HTTP session for all external requests.
    - Tries Open Library first (large covers: `-L.jpg`).
    - Optionally falls back to Google Books, enforcing `zoom=0`.
    - Updates `Product.image` via queryset `update()` (no per-row `save()`).
    """

    help = "Auto-fetch and upload covers for existing books without images."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="Optional cap on how many products to process (0 means no limit).",
        )
        parser.add_argument(
            "--use-google-fallback",
            action="store_true",
            help="Also try Google Books if Open Library does not provide a cover.",
        )
        parser.add_argument(
            "--throttle-ms",
            type=int,
            default=0,
            help="Optional delay between items to reduce API pressure (milliseconds).",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        limit = int(options.get("limit") or 0)
        use_google_fallback = bool(options.get("use_google_fallback"))
        throttle_ms = int(options.get("throttle_ms") or 0)

        qs = Product.objects.filter(Q(image__isnull=True) | Q(image=""))
        if limit > 0:
            qs = qs.order_by("id")[:limit]
        total = qs.count()

        if total == 0:
            self.stdout.write(self.style.WARNING("No products without images found."))
            return

        self.stdout.write(f"Processing {total} products without images...")

        session = requests.Session()

        updated = 0
        processed = 0
        for product in qs.iterator():
            processed += 1

            public_id = None
            title = (product.Book_name or "").strip()
            author = (product.Author or "").strip()

            try:
                cover_url = self._best_openlibrary_cover_url(session=session, title=title, author=author)
                if cover_url and not _looks_like_placeholder_url(cover_url):
                    upload_result = cloudinary_upload(cover_url, folder="bookloop_covers")
                    if isinstance(upload_result, dict):
                        public_id = upload_result.get("public_id")
            except Exception:
                public_id = None

            if not public_id and use_google_fallback:
                try:
                    gb_url = self._best_google_books_cover_url(session=session, title=title, author=author)
                    if gb_url and not _looks_like_placeholder_url(gb_url):
                        upload_result = cloudinary_upload(gb_url, folder="bookloop_covers")
                        if isinstance(upload_result, dict):
                            public_id = upload_result.get("public_id")
                except Exception:
                    public_id = None

            if public_id:
                Product.objects.filter(pk=product.pk).update(image=public_id)
                updated += 1

            if throttle_ms > 0:
                time.sleep(throttle_ms / 1000)

            if processed % 25 == 0:
                self.stdout.write(f"Progress: {processed}/{total} scanned, {updated} updated")

        self.stdout.write(
            self.style.SUCCESS(
                f"Finished backfill: {updated} of {total} products received covers."
            )
        )

    def _best_openlibrary_cover_url(self, *, session: requests.Session, title: str, author: str) -> str | None:
        title_q = (title or "").strip()
        author_q = (author or "").strip()
        if not title_q:
            return None

        for title_variant in self._title_variants(title_q):
            query_attempts: list[dict[str, str]] = []
            if author_q:
                query_attempts.append({"title": title_variant, "author": author_q})
            query_attempts.append({"title": title_variant})

            for params in query_attempts:
                resp = session.get(
                    "https://openlibrary.org/search.json",
                    params=params,
                    timeout=5,
                )
                resp.raise_for_status()
                data = resp.json() or {}
                docs = data.get("docs") or []
                for doc in docs:
                    cover_i = doc.get("cover_i")
                    if cover_i:
                        return f"https://covers.openlibrary.org/b/id/{cover_i}-L.jpg"

                    cover_edition_key = doc.get("cover_edition_key")
                    if cover_edition_key:
                        return f"https://covers.openlibrary.org/b/olid/{cover_edition_key}-L.jpg"

        return None

    def _best_google_books_cover_url(self, *, session: requests.Session, title: str, author: str) -> str | None:
        title_q = (title or "").strip()
        author_q = (author or "").strip()
        if not title_q:
            return None

        for title_variant in self._title_variants(title_q):
            query_attempts: list[str] = []
            if author_q:
                query_attempts.append(f"intitle:{title_variant} inauthor:{author_q}")
            query_attempts.append(f"intitle:{title_variant}")
            if author_q:
                query_attempts.append(f"{title_variant} {author_q}")
            query_attempts.append(title_variant)

            for q in query_attempts:
                resp = session.get(
                    "https://www.googleapis.com/books/v1/volumes",
                    params={
                        "q": q,
                        "maxResults": 5,
                        "printType": "books",
                    },
                    timeout=5,
                )
                resp.raise_for_status()
                data = resp.json() or {}
                items = data.get("items") or []
                if not items:
                    continue

                for item in items:
                    volume_info = item.get("volumeInfo") or {}
                    image_links = volume_info.get("imageLinks") or {}
                    url = _pick_best_google_image_link(image_links)
                    normalized = _normalize_google_books_image_url(url or "")
                    if normalized:
                        return normalized

        return None

    def _title_variants(self, title: str) -> list[str]:
        base = (title or "").strip()
        if not base:
            return []

        variants: list[str] = []

        def add(v: str) -> None:
            v2 = " ".join((v or "").strip().split())
            if v2 and v2 not in variants:
                variants.append(v2)

        add(base)

        trimmed = base.rstrip("\u2026").rstrip(" ,.;:-")
        add(trimmed)

        tokens = trimmed.split()
        if len(tokens) >= 2 and len(tokens[-1]) <= 2:
            add(" ".join(tokens[:-1]))

        if len(tokens) > 10:
            add(" ".join(tokens[:8]))
            add(" ".join(tokens[:6]))

        return variants
