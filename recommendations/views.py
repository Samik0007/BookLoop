"""
Recommendation views.

Endpoints:
  GET /recommendations/              → full AI recommendations page (ai_recommendations)
  GET /recommendations/api/homepage/ → AJAX JSON endpoint (homepage_recommendations_api)
"""
from __future__ import annotations

import logging

from django.http import JsonResponse
from django.shortcuts import render

from books.models import Order, OrderItem, Product, Wishlist

from .ai_engine import get_recommendations

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_FALLBACK_LIMIT = 8


def _get_fallback_books() -> list[dict]:
    """Return the 6 most recently added approved sell books as dicts."""
    qs = (
        Product.objects.filter(listing_status="approved", listing_type="sell")
        .order_by("-id")[:_FALLBACK_LIMIT]
    )
    books = [_product_to_dict(p) for p in qs]
    print(f"[RECS] Fallback: fetched {len(books)} trending books from DB.")
    return books


def _product_to_dict(p: Product) -> dict:
    """Serialise a Product instance to a plain dict for JSON output."""
    try:
        image_url = p.image.url if p.image else ""
    except Exception:
        image_url = ""

    try:
        discounted = str(p.discounted_price)
    except Exception:
        discounted = str(p.price)

    return {
        "id": p.id,
        "title": p.Book_name,
        "author": p.Author,
        "genre": p.genre or "General",
        "price": float(p.price),
        "discounted_price": discounted,
        "image_url": image_url,
        "product_url": f"/product/{p.id}/",
    }


def _catalog_dict(p: Product) -> dict:
    """Lightweight dict sent to Groq (no image/URL overhead)."""
    return {
        "id": p.id,
        "title": p.Book_name,
        "author": p.Author,
        "genre": p.genre or "General",
        "price": float(p.price),
    }


# ---------------------------------------------------------------------------
# AJAX endpoint consumed by the homepage JS
# ---------------------------------------------------------------------------

def homepage_recommendations_api(request):
    """
    GET /recommendations/api/homepage/

    Returns JSON:
    {
        "recommendations": [ {id, title, author, genre, price, discounted_price,
                               reason, image_url, product_url}, ... ],
        "source_count": {"purchased": N, "cart": N, "wishlist": N}
    }

    Returns {"recommendations": [], "source_count": {...}} for anonymous users
    so the front-end can hide the section without JS errors.
    """
    # ---- Unauthenticated: return fallback trending books, not an empty list --
    if not request.user.is_authenticated:
        fallback = _get_fallback_books()
        print("[RECS] Unauthenticated user — returning fallback trending books.")
        return JsonResponse({
            "status": "unauthenticated",
            "recommendations": fallback,
            "source_count": {"purchased": 0, "cart": 0, "wishlist": 0},
        })

    username = request.user.username

    # ---- 1. Gather user signal books ----------------------------------------

    # Purchases: completed orders
    purchased_qs = (
        OrderItem.objects.select_related("Book_name")
        .filter(order__user=username, order__complete=True)
        .values_list("Book_name_id", flat=True)
        .distinct()
    )
    purchased_ids: set[int] = set(purchased_qs)

    # Cart: latest incomplete order
    cart_ids: set[int] = set()
    try:
        active_order = Order.objects.filter(user=username, complete=False).last()
        if active_order:
            cart_ids = set(
                OrderItem.objects.filter(order=active_order)
                .values_list("Book_name_id", flat=True)
                .distinct()
            )
    except Exception:
        pass

    # Wishlist
    wishlist_ids: set[int] = set(
        Wishlist.objects.filter(user=username)
        .values_list("product_id", flat=True)
        .distinct()
    )

    all_signal_ids = purchased_ids | cart_ids | wishlist_ids

    # Fetch full Product objects for the signal books in one query
    signal_products: dict[int, Product] = {
        p.id: p
        for p in Product.objects.filter(id__in=all_signal_ids)
    }

    purchased_books = [_catalog_dict(signal_products[i]) for i in purchased_ids if i in signal_products]
    cart_books = [_catalog_dict(signal_products[i]) for i in cart_ids if i in signal_products]
    wishlist_books = [_catalog_dict(signal_products[i]) for i in wishlist_ids if i in signal_products]

    source_count = {
        "purchased": len(purchased_books),
        "cart": len(cart_books),
        "wishlist": len(wishlist_books),
    }

    # ---- 2. Build catalog (exclude already-signalled books) ------------------
    catalog_qs = (
        Product.objects.filter(listing_status="approved", listing_type="sell")
        .exclude(id__in=all_signal_ids)
        .order_by("-id")[:80]
    )
    catalog = [_catalog_dict(p) for p in catalog_qs]

    # ---- 3. Force-Start / cold-start signal ----------------------------------
    # When a user has zero history Groq still needs *something* to act on.
    # Seed wishlist_books with the 2 most-recently added approved books so the
    # prompt always has concrete titles to reason about.
    cold_start_hint = ""
    if not all_signal_ids:
        seed_qs = (
            Product.objects.filter(listing_status="approved", listing_type="sell")
            .order_by("-id")[:2]
        )
        seed_books = [_catalog_dict(p) for p in seed_qs]
        wishlist_books = seed_books          # inject as wishlist signal
        seed_titles = [b["title"] for b in seed_books]
        print(f"DEBUG: Force-Start activated — seeding wishlist with: {seed_titles}")

        # Also derive top genres from the catalog for variety
        genre_counts: dict[str, int] = {}
        for b in catalog:
            g = b.get("genre") or "General"
            genre_counts[g] = genre_counts.get(g, 0) + 1
        top_genres = sorted(genre_counts, key=lambda g: genre_counts[g], reverse=True)[:4]
        cold_start_hint = (
            "Popular genres in this marketplace: " + ", ".join(top_genres)
            if top_genres
            else "Popular genres in Nepal: Fiction, Academic, Self-Help, Science"
        )

    # ---- 4. Call Groq ----------------------------------------------------------
    print(
        f"DEBUG: Purchased: {len(purchased_books)}, "
        f"Cart: {len(cart_books)}, "
        f"Wishlist: {len(wishlist_books)}"
    )

    try:
        ai_suggestions = get_recommendations(
            purchased_books, cart_books, wishlist_books, catalog,
            cold_start_hint=cold_start_hint,
        )
        print(f"DEBUG: catalog_size={len(catalog)}, ai_suggestions={len(ai_suggestions)}")
    except Exception as exc:  # noqa: BLE001
        print(f"DEBUG: AI call raised an unexpected exception: {type(exc).__name__}: {exc}")
        ai_suggestions = []

    # ---- 4a. AI returned nothing — use DB fallback ----------------------------
    if not ai_suggestions:
        print("[RECS] Groq returned no suggestions — using DB fallback.")
        fallback = _get_fallback_books()
        return JsonResponse({
            "status": "trending",
            "recommendations": fallback,
            "source_count": source_count,
        })

    # ---- 4b. Re-fetch matched Product objects from DB (fresh data) ------------
    suggested_ids = [item["id"] for item in ai_suggestions]
    reason_map = {item["id"]: item.get("reason", "") for item in ai_suggestions}

    products_by_id: dict[int, Product] = {
        p.id: p
        for p in Product.objects.filter(id__in=suggested_ids, listing_status="approved")
    }

    recommendations: list[dict] = []
    for item_id in suggested_ids:          # preserve Groq ordering
        product = products_by_id.get(item_id)
        if product is None:
            print(f"[RECS] WARNING: Groq suggested ID {item_id} not found in DB — skipping.")
            continue
        data = _product_to_dict(product)
        data["reason"] = reason_map.get(item_id, "")
        recommendations.append(data)

    # If DB re-fetch wiped everything (Groq hallucinated IDs), fall back
    if not recommendations:
        print("[RECS] All Groq IDs were invalid — using DB fallback.")
        fallback = _get_fallback_books()
        return JsonResponse({
            "status": "trending",
            "recommendations": fallback,
            "source_count": source_count,
        })

    print(f"[RECS] AI success — returning {len(recommendations)} AI recommendations.")
    return JsonResponse({
        "status": "ai_success",
        "recommendations": recommendations,
        "source_count": source_count,
    })


# ---------------------------------------------------------------------------
# Full-page AI recommendations view (standalone page)
# ---------------------------------------------------------------------------

def ai_recommendations(request):
    """Full dedicated recommendations page (optional, standalone)."""
    context: dict = {"recommendations": [], "logged_in": request.user.is_authenticated}
    return render(request, "recommendations/ai_recommendations.html", context)
