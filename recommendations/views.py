"""
Recommendation views.

Endpoints:
  GET /recommendations/                → full AI recommendations page (ai_recommendations)
  GET /recommendations/api/trending/   → fast trending books (no AI, < 100 ms)
  GET /recommendations/api/homepage/   → full AI recommendations (may be slow)
"""
from __future__ import annotations

import logging

from django.core.cache import cache
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
    """Return genre-diverse trending books for the stage-1 cards.

    Uses the existing ``views`` field for popularity — no JOIN, no annotation,
    single fast query evaluated once in Python.
    """
    # One query, bounded to 80 rows, no heavy aggregation
    pool = list(
        Product.objects
        .filter(listing_status="approved", listing_type="sell")
        .order_by("-views", "-id")[:80]
    )

    seen_genres: set = set()
    diverse: list = []
    for p in pool:
        g = p.genre or "General"
        if g not in seen_genres:
            seen_genres.add(g)
            diverse.append(p)
        if len(diverse) >= _FALLBACK_LIMIT:
            break

    # Fill any remaining slots from the same pool (already in memory)
    if len(diverse) < _FALLBACK_LIMIT:
        seen_ids = {p.id for p in diverse}
        for p in pool:
            if p.id not in seen_ids:
                diverse.append(p)
            if len(diverse) >= _FALLBACK_LIMIT:
                break

    books = [_product_to_dict(p) for p in diverse]
    print(f"[RECS] Trending fallback: {len(books)} genre-diverse books.")
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
# Fast trending endpoint — no AI, just DB, responds in < 100 ms
# ---------------------------------------------------------------------------

def trending_books_api(request):
    """
    GET /recommendations/api/trending/

    Returns the most-recently-added approved sell books immediately.
    No Groq call — used as the stage-1 fast load on the homepage.
    """
    books = _get_fallback_books()
    return JsonResponse({
        "status": "trending",
        "recommendations": books,
        "source_count": {"purchased": 0, "cart": 0, "wishlist": 0},
    })


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
    cache_key = f'btmgya_recs_{username}'
    force_refresh = request.GET.get('refresh') == '1'

    # ── Server-side cache hit (4 h TTL) ──────────────────────────────────────
    # Skip cache only when the client explicitly signals a user action
    # (cart add / wishlist / purchase) via ?refresh=1.
    if not force_refresh:
        cached = cache.get(cache_key)
        if cached is not None:
            print(f"[RECS] Serving server-side cache for '{username}'.")
            return JsonResponse(cached)

    # ---- 1. Gather user signal books ----------------------------------------

    # Purchases: completed orders
    purchased_qs = (
        OrderItem.objects.select_related("Book_name")
        .filter(order__user=username, order__complete=True)
        .values_list("Book_name_id", flat=True)
        .distinct()
    )
    # Filter out None — happens when an ordered product was deleted (SET_NULL)
    purchased_ids: set[int] = {i for i in purchased_qs if i is not None}

    # Cart: latest incomplete order
    cart_ids: set[int] = set()
    try:
        active_order = Order.objects.filter(user=username, complete=False).last()
        if active_order:
            cart_ids = {
                i for i in OrderItem.objects.filter(order=active_order)
                .values_list("Book_name_id", flat=True)
                .distinct()
                if i is not None
            }
    except Exception:
        pass

    # Wishlist
    wishlist_ids: set[int] = {
        i for i in Wishlist.objects.filter(user=username)
        .values_list("product_id", flat=True)
        .distinct()
        if i is not None
    }

    all_signal_ids = purchased_ids | cart_ids | wishlist_ids

    # Fetch full Product objects for the signal books in one query
    signal_products: dict[int, Product] = {
        p.id: p
        for p in Product.objects.filter(id__in=all_signal_ids)
    }

    purchased_books  = [_catalog_dict(signal_products[i]) for i in purchased_ids  if i in signal_products]
    cart_books       = [_catalog_dict(signal_products[i]) for i in cart_ids        if i in signal_products]
    wishlist_books   = [_catalog_dict(signal_products[i]) for i in wishlist_ids    if i in signal_products]

    # Use the raw ID counts so source_count reflects ALL activity,
    # including books later archived (they still shaped the user's taste).
    source_count = {
        "purchased": len(purchased_ids),
        "cart":      len(cart_ids),
        "wishlist":  len(wishlist_ids),
    }

    # ---- 2. Build catalog -----------------------------------------------------
    # Hard cap: 10 preferred-genre books + 5 discovery books = 15 max.
    # Keeps the Groq prompt small enough to respond in 2-5 s on free tier.
    preferred_genres: set[str] = {
        b["genre"] for b in purchased_books + cart_books + wishlist_books
        if b.get("genre")
    }

    _pref_books: list = []
    _disc_seen: dict  = {}   # genre → first Product seen (discovery)

    for _p in (
        Product.objects
        .filter(listing_status="approved", listing_type="sell")
        .exclude(id__in=all_signal_ids)
        .order_by("-views", "-id")
    ):
        _g = _p.genre or "General"
        if _g in preferred_genres and len(_pref_books) < 10:
            _pref_books.append(_p)
        elif _g not in preferred_genres and _g not in _disc_seen and len(_disc_seen) < 5:
            _disc_seen[_g] = _p   # 1 discovery book per non-preferred genre, 5 max

        # Stop early once we have enough of each kind
        pref_done = len(_pref_books) >= 10 or not preferred_genres
        disc_done = len(_disc_seen) >= 5
        if pref_done and disc_done:
            break

    catalog_pool = (
        sorted(_pref_books, key=lambda p: p.genre or "")
        + sorted(_disc_seen.values(), key=lambda p: p.genre or "")
    )
    catalog = [_catalog_dict(p) for p in catalog_pool]
    print(
        f"[RECS] Catalog: {len(catalog)} books "
        f"({len(_pref_books)} from {len(preferred_genres)} preferred genres + "
        f"{len(_disc_seen)} discovery genres)."
    )

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
    response_data = {
        "status": "ai_success",
        "recommendations": recommendations,
        "source_count": source_count,
    }
    # Store in server-side cache for 4 hours so Groq is only called once
    # per user per 4 hours, regardless of browser state.
    cache.set(cache_key, response_data, 4 * 60 * 60)
    return JsonResponse(response_data)


# ---------------------------------------------------------------------------
# Full-page AI recommendations view (standalone page)
# ---------------------------------------------------------------------------

def ai_recommendations(request):
    """Full dedicated recommendations page (optional, standalone)."""
    context: dict = {"recommendations": [], "logged_in": request.user.is_authenticated}
    return render(request, "recommendations/ai_recommendations.html", context)
