from __future__ import annotations

from typing import Iterable, List

from django.core.cache import cache
from django.db.models import Case, IntegerField, QuerySet, When
from django.db.models import Count
from django.contrib.auth import get_user_model

from books.models import OrderItem, Product
from .models import UserInteraction

User = get_user_model()


def _order_by_id_list(qs: QuerySet[Product], id_list: List[int]) -> QuerySet[Product]:
    """Return ``qs`` ordered according to ``id_list`` preserving recommendation order."""

    if not id_list:
        return qs

    when_statements = [When(id=pk, then=pos) for pos, pk in enumerate(id_list)]
    return qs.order_by(Case(*when_statements, output_field=IntegerField()))


def _trending_books(limit: int = 10) -> QuerySet[Product]:
    """Fallback: trending books based on purchase counts or recent additions."""

    # Use completed orders to determine popularity
    popular_ids = (
        OrderItem.objects.filter(order__complete=True)
        .values("Book_name_id")
        .annotate(order_count=Count("id"))
        .order_by("-order_count")[: limit]
    )

    ids = [row["Book_name_id"] for row in popular_ids if row["Book_name_id"] is not None]
    if ids:
        return _order_by_id_list(Product.objects.filter(id__in=ids), ids)

    # Absolute cold-start: no orders at all; just show most recent products
    return Product.objects.order_by("-pub_date")[:limit]


def get_user_recommendations(user: User, limit: int = 10) -> QuerySet[Product]:
    """Return a queryset of recommended ``Product`` objects for a user.

    Logic:
    1. Try Redis/Django cache for precomputed recommendations (from Celery task).
    2. If missing, check if the user has any interactions.
       - If yes, we still fall back to trending, as heavy ML work is done offline.
    3. If the user has no interactions (true cold start), we also use trending.
    """

    if user is None or not getattr(user, "is_authenticated", False):
        return _trending_books(limit=limit)

    cache_key = f"recs_user_{user.id}"

    # Be robust if Redis or the cache backend is temporarily unavailable.
    # In that case we simply fall back to trending books instead of
    # raising a 500 error for the user.
    try:
        book_ids: List[int] = cache.get(cache_key) or []
    except Exception:
        # Cache failure (e.g., Redis down) – degrade gracefully.
        return _trending_books(limit=limit)

    if book_ids:
        qs = Product.objects.filter(id__in=book_ids)
        return _order_by_id_list(qs, book_ids)[:limit]

    # No cached recommendations: check for any historical interactions
    has_interactions = UserInteraction.objects.filter(user=user).exists()

    # For this scope, both cases share the same fallback behavior (trending books).
    # The distinction primarily matters for analytics; recommendation generation
    # itself happens offline in Celery.
    return _trending_books(limit=limit)
