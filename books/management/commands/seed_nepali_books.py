from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import re

import requests
from cloudinary.uploader import upload as cloudinary_upload
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from books.models import Product


@dataclass(frozen=True)
class NepaliSeedBook:
    title: str
    author: str
    genre: str
    price: int
    description: str


class Command(BaseCommand):
    """Seed 20 famous Nepali books with reliable, high-quality covers.

    Why this command exists:
    - Public APIs are inconsistent for Nepali literature metadata.
    - We hardcode high-confidence *metadata* (title/author/description/price).
    - For covers, we *reliably* fetch the best available Open Library cover
      (large: `-L.jpg`) at seed time and upload it to Cloudinary.

    Safe behavior:
    - If cover fetching/upload fails, the book is still created (without image).
    - Running the command multiple times is idempotent via update_or_create.
    """

    help = "Seeds the database with a curated set of famous Nepali books."  # noqa: A003

    def handle(self, *args: Any, **options: Any) -> None:
        curated = self._curated_books()
        created = 0
        updated = 0
        covers_uploaded = 0
        covers_failed = 0

        self.stdout.write(self.style.NOTICE(f"Seeding {len(curated)} curated Nepali books..."))

        session = requests.Session()

        with transaction.atomic():
            for book in curated:
                defaults = {
                    "genre": book.genre[:300],
                    "description": book.description[:1000],
                    "price": book.price,
                    "pub_date": timezone.now().date(),
                    "quantity": 20,
                    "listing_type": "sell",
                    "listing_status": "approved",
                }

                product, was_created = Product.objects.update_or_create(
                    Book_name=book.title[:50],
                    Author=book.author[:50],
                    defaults=defaults,
                )

                if was_created:
                    created += 1
                else:
                    updated += 1

                # Cover pipeline (high-quality):
                # 1) Search Open Library for a cover ID.
                # 2) Build a LARGE cover URL (`-L.jpg`).
                # 3) Validate the URL is reachable.
                # 4) Upload to Cloudinary and store the returned public_id.
                try:
                    cover_url = self._best_openlibrary_cover_url(
                        session=session,
                        title=book.title,
                        author=book.author,
                    )
                    if not cover_url:
                        continue

                    try:
                        resp = session.get(cover_url, timeout=10)
                        resp.raise_for_status()
                    except Exception:
                        continue

                    upload_result = cloudinary_upload(
                        cover_url,
                        folder="bookloop_covers",
                    )
                    public_id = upload_result.get("public_id") if isinstance(upload_result, dict) else None
                    if public_id:
                        Product.objects.filter(pk=product.pk).update(image=public_id)
                        covers_uploaded += 1
                except Exception:
                    covers_failed += 1
                    continue

        self.stdout.write(self.style.SUCCESS("Nepali seeding complete."))
        self.stdout.write(self.style.SUCCESS(f"Created: {created}, Updated: {updated}"))
        self.stdout.write(self.style.SUCCESS(f"Covers uploaded: {covers_uploaded}"))
        if covers_failed:
            self.stdout.write(self.style.WARNING(f"Cover uploads failed (non-fatal): {covers_failed}"))

    def _curated_books(self) -> list[NepaliSeedBook]:
        return [
            NepaliSeedBook(
                title="Palpasa Cafe",
                author="Narayan Wagle",
                genre="Nepali",
                price=450,
                description=(
                    "A modern Nepali classic that follows an artist-turned-traveler as he navigates love, "
                    "friendship, and the emotional weight of Nepal's conflict years. Written with warmth and "
                    "quiet political undertones, it captures the pulse of a changing Kathmandu." 
                ),
            ),
            NepaliSeedBook(
                title="Karnali Blues",
                author="Buddhi Sagar",
                genre="Nepali",
                price=550,
                description=(
                    "A tender, humorous coming-of-age novel centered on a son's memory of his father and "
                    "their life shaped by hardship and hope. It paints rural Nepal with intimate detail, "
                    "balancing nostalgia, grief, and resilience." 
                ),
            ),
            NepaliSeedBook(
                title="Seto Dharti",
                author="Amar Neupane",
                genre="Nepali",
                price=600,
                description=(
                    "A powerful story of a young girl's life constrained by social customs, told through "
                    "a voice that is both painful and honest. The novel explores widowhood, tradition, and "
                    "the quiet endurance of women across decades." 
                ),
            ),
            NepaliSeedBook(
                title="Shirishko Phool (The Blue Mimosa)",
                author="Parijat",
                genre="Nepali",
                price=500,
                description=(
                    "A landmark Nepali novel that interrogates love, desire, and self-destruction through "
                    "a sharp psychological lens. With striking prose and moral ambiguity, it remains one of "
                    "the most influential works in Nepali literature." 
                ),
            ),
            NepaliSeedBook(
                title="Muna Madan",
                author="Laxmi Prasad Devkota",
                genre="Nepali",
                price=250,
                description=(
                    "An epic narrative poem that tells the heartbreaking story of love and separation as a "
                    "young man leaves home in search of work. Revered for its simplicity and emotional depth, "
                    "it is often considered a foundational text of modern Nepali literature." 
                ),
            ),
            NepaliSeedBook(
                title="China Harayeko Manchhe",
                author="Hari Bansha Acharya",
                genre="Nepali",
                price=400,
                description=(
                    "A witty and reflective travel memoir that blends humor with poignant observations on "
                    "society, identity, and human dignity. The narrative reads like a conversation—light on the "
                    "surface but deeply empathetic underneath." 
                ),
            ),
            NepaliSeedBook(
                title="Summer Love",
                author="Subin Bhattarai",
                genre="Nepali",
                price=450,
                description=(
                    "A popular contemporary romance that captures the excitement, confusion, and consequences "
                    "of first love. Fast-paced and relatable, it reflects modern Nepali youth culture and the "
                    "tension between emotion and responsibility." 
                ),
            ),
            NepaliSeedBook(
                title="Saaya",
                author="Subin Bhattarai",
                genre="Nepali",
                price=450,
                description=(
                    "A heartfelt novel about companionship, loss, and the complicated bonds that survive time. "
                    "It explores how love can be both healing and painful, told in an accessible modern voice." 
                ),
            ),
            NepaliSeedBook(
                title="Radha",
                author="Krishna Dharabasi",
                genre="Nepali",
                price=650,
                description=(
                    "A literary retelling that reimagines Radha's inner world with philosophical depth and "
                    "emotional complexity. It blends myth and modern sensibility to explore devotion, desire, "
                    "and selfhood." 
                ),
            ),
            NepaliSeedBook(
                title="Basain",
                author="Lil Bahadur Chettri",
                genre="Nepali",
                price=350,
                description=(
                    "A socially grounded novel about displacement, poverty, and the forces that push families "
                    "to leave their ancestral homes. It is celebrated for its realism and compassion toward rural "
                    "life." 
                ),
            ),
            NepaliSeedBook(
                title="Pagal Basti",
                author="Sarubhakta",
                genre="Nepali",
                price=500,
                description=(
                    "A philosophical and romantic novel that questions what it means to live authentically. "
                    "Through intense relationships and introspection, it explores freedom, devotion, and the "
                    "price of ideals." 
                ),
            ),
            NepaliSeedBook(
                title="Jhola",
                author="Krishna Dharabasi",
                genre="Nepali",
                price=300,
                description=(
                    "A moving narrative centered on a woman's life under oppressive traditions, written with "
                    "economy and emotional force. The story exposes cruelty normalized by society and highlights "
                    "quiet courage." 
                ),
            ),
            NepaliSeedBook(
                title="Antarmann Ko Yatra",
                author="Jhamak Ghimire",
                genre="Nepali",
                price=450,
                description=(
                    "A deeply inspirational memoir chronicling the author's struggle for expression and dignity "
                    "in the face of severe physical challenges. It is a testament to resilience, intellect, and "
                    "the transformative power of writing." 
                ),
            ),
            NepaliSeedBook(
                title="Firfire",
                author="Buddhi Sagar",
                genre="Nepali",
                price=500,
                description=(
                    "A warm, character-driven story that captures everyday life, small ambitions, and the subtle "
                    "ways communities shape a person's future. It balances humor and tenderness while painting a "
                    "vivid Nepali social landscape." 
                ),
            ),
            NepaliSeedBook(
                title="Sumnima",
                author="Bishweshwar Prasad Koirala",
                genre="Nepali",
                price=450,
                description=(
                    "A thought-provoking novel that explores identity, culture, and desire through a story shaped "
                    "by contrasting worldviews. Known for its psychological depth, it remains a key work in Nepali "
                    "modern literature." 
                ),
            ),
            NepaliSeedBook(
                title="Doshi Chasma",
                author="Bishweshwar Prasad Koirala",
                genre="Nepali",
                price=400,
                description=(
                    "A concise, psychologically rich story focused on perception, insecurity, and the fragile lines "
                    "between reality and projection. It showcases BP Koirala's signature introspective style." 
                ),
            ),
            NepaliSeedBook(
                title="Ek Chihan",
                author="Hridaya Chandra Singh Pradhan",
                genre="Nepali",
                price=400,
                description=(
                    "A renowned Nepali classic that explores social change, dignity, and the pressures faced by ordinary "
                    "people under entrenched systems. Its realism and emotional weight make it a frequently cited milestone "
                    "in Nepali prose." 
                ),
            ),
            NepaliSeedBook(
                title="Jiwan Kada Ki Phool",
                author="Jhamak Ghimire",
                genre="Nepali",
                price=450,
                description=(
                    "A powerful autobiographical work that portrays life as both painful and beautiful, shaped by "
                    "barriers yet driven by spirit. It combines raw experience with a message of hope and dignity." 
                ),
            ),
            NepaliSeedBook(
                title="Ghumne Mech Mathi Andho Manche",
                author="Bhupi Sherchan",
                genre="Nepali",
                price=300,
                description=(
                    "A widely read poetry collection known for sharp social observation and unforgettable lines. "
                    "It captures political frustration, human vulnerability, and a distinctly Nepali modern sensibility "
                    "through accessible yet powerful verse." 
                ),
            ),
            NepaliSeedBook(
                title="Madhavi",
                author="Madan Mani Dixit",
                genre="Nepali",
                price=650,
                description=(
                    "A major Nepali novel that blends historical imagination with layered storytelling and moral questions. "
                    "Celebrated for its scope and literary craft, it offers a rich reading experience that rewards patience "
                    "and reflection." 
                ),
            ),
        ]

    def _best_openlibrary_cover_url(self, session: requests.Session, title: str, author: str) -> str | None:
        """Find the best available Open Library cover URL (large) for a book."""

        title_q = (title or "").strip()
        author_q = (author or "").strip()
        if not title_q:
            return None

        normalized_title = self._normalize_title(title_q)

        # We intentionally try multiple queries to maximize hit-rate.
        query_attempts: list[dict[str, str]] = []
        if author_q:
            query_attempts.append({"title": title_q, "author": author_q})
            if normalized_title != title_q:
                query_attempts.append({"title": normalized_title, "author": author_q})
        query_attempts.append({"title": title_q})
        if normalized_title != title_q:
            query_attempts.append({"title": normalized_title})

        for params in query_attempts:
            try:
                resp = session.get(
                    "https://openlibrary.org/search.json",
                    params=params,
                    timeout=10,
                )
                resp.raise_for_status()
                data = resp.json() or {}
            except Exception:
                continue

            docs = data.get("docs") or []
            for doc in docs:
                cover_i = doc.get("cover_i")
                if cover_i:
                    return f"https://covers.openlibrary.org/b/id/{cover_i}-L.jpg"

                cover_edition_key = doc.get("cover_edition_key")
                if cover_edition_key:
                    return f"https://covers.openlibrary.org/b/olid/{cover_edition_key}-L.jpg"

        return None

    def _normalize_title(self, title: str) -> str:
        """Normalize titles for better Open Library search matching."""

        cleaned = re.sub(r"\s*\([^)]*\)\s*", " ", title).strip()
        cleaned = re.sub(r"\s+", " ", cleaned)
        return cleaned
