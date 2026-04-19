"""
AI recommendation engine using Groq's LLaMA3 API.

Accepts lists of user-context books (purchased, cart, wishlist) plus a
catalog slice, calls Groq, and returns up to 8 recommended book dicts.

All network/parse failures degrade gracefully to an empty list — the
calling view decides what to show instead.
"""
from __future__ import annotations

import json
import logging
import os
import re

import requests

logger = logging.getLogger(__name__)

_GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
_MODEL = "llama-3.1-8b-instant"
_TIMEOUT = 25          # seconds — Groq server timeout; browser fetch has no limit
_MAX_TOKENS = 1200     # 8 recs × ~130 tokens; enough for specific reasons
_TEMPERATURE = 0.5     # mid-range: varied reasons without hallucination


def _build_prompt(
    purchased: list[dict],
    cart: list[dict],
    wishlist: list[dict],
    catalog: list[dict],
    cold_start_hint: str = "",
) -> str:
    """Return the full system+user prompt string."""

    catalog_lines = "\n".join(
        f"  [ID:{b['id']}] {b.get('title', 'Unknown')} by {b.get('author', 'Unknown')} "
        f"[{b.get('genre', 'General')}] Rs.{b.get('price', 0)}"
        for b in catalog
    )

    exclude_ids = {b["id"] for b in purchased + cart + wishlist if b.get("id")}
    exclude_note = (
        f"Do NOT recommend books with these IDs (already in user history): {sorted(exclude_ids)}"
        if exclude_ids
        else "No books to exclude."
    )

    # Derive ordered preferred genres (purchased weighted 3×, cart 2×, wishlist 1×)
    _genre_weight: dict[str, int] = {}
    for _b, _w in [(b, 3) for b in purchased] + \
                   [(b, 2) for b in cart] + \
                   [(b, 1) for b in wishlist]:
        _g = _b.get("genre") or "General"
        _genre_weight[_g] = _genre_weight.get(_g, 0) + _w
    preferred_genres_str = (
        ", ".join(sorted(_genre_weight, key=lambda g: -_genre_weight[g])[:8])
        if _genre_weight else "new user — recommend popular titles across genres"
    )

    # Compact history — title only to save tokens, but keep enough for Groq to write
    # specific reasons that reference the user's actual titles.
    def _fmt_titled(books: list[dict]) -> str:
        if not books:
            return "(none)"
        # Deduplicate by title so repeated purchases don't bloat the prompt
        seen: set[str] = set()
        parts: list[str] = []
        for b in books:
            t = b.get("title", "?")
            if t not in seen:
                seen.add(t)
                parts.append(f'"{t}" [{b.get("genre","?")}]')
        return ", ".join(parts)

    history_section = (
        f"Purchased: {_fmt_titled(purchased)}\n"
        f"Cart: {_fmt_titled(cart)}\n"
        f"Wishlist: {_fmt_titled(wishlist)}\n"
        f"Top preferred genres: {preferred_genres_str}"
    )
    if cold_start_hint:
        history_section += f"\nNote: {cold_start_hint}"

    return (
        "You are a personalised book recommendation engine for a second-hand marketplace in Nepal.\n"
        "Study the user's reading history below, then pick 8 books from the CATALOG.\n\n"
        "USER HISTORY:\n"
        f"{history_section}\n\n"
        "CATALOG:\n"
        f"{catalog_lines}\n\n"
        "RULES:\n"
        f"1. {exclude_note}\n"
        "2. Return exactly 8 recommendations (fewer only if <8 valid catalog options).\n"
        "3. At least 5 of 8 must come from the user's top preferred genres.\n"
        "4. Max 2 books from the same genre — keep picks varied.\n"
        "5. reason field: write one SHORT, SPECIFIC sentence (10–15 words) that:\n"
        "   - Names a book the user actually read/bought that this recommendation relates to.\n"
        "   - Explains concretely why THIS book will appeal to them.\n"
        "   - GOOD: \"Like P.S. I Love You, this is an emotional romance with unforgettable characters.\"\n"
        "   - BAD: \"User purchased a romance book so we recommend this.\" (too generic)\n"
        "   - Each reason must be UNIQUE — no copy-pasting the same sentence.\n"
        "6. Only use IDs from the catalog. Never invent IDs or titles.\n"
        "7. Output raw JSON only — no markdown, no explanation.\n"
        '   Format: [{"id":int,"title":str,"author":str,"genre":str,"reason":str},...]\n'
        "   Start with [ and end with ].\n\n"
        "JSON:"
    )


def _call_groq(prompt: str) -> str:
    """POST to Groq and return the raw text content string."""
    api_key = os.environ.get("GROQ_API_KEY", "").strip()
    if not api_key:
        print("[GROQ] ERROR: GROQ_API_KEY is not set in environment.")
        raise ValueError("GROQ_API_KEY is not set in environment.")

    print("[GROQ] Sending request to Groq...")

    resp = requests.post(
        _GROQ_URL,
        json={
            "model": _MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": _TEMPERATURE,
            "max_tokens": _MAX_TOKENS,
        },
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        timeout=_TIMEOUT,
    )
    resp.raise_for_status()

    data = resp.json()
    content = data["choices"][0]["message"]["content"]
    print(f"[GROQ] Raw response received ({len(content)} chars):\n{content[:500]}")
    return content


def _extract_json_array(text: str) -> str:
    """
    Aggressively extract a JSON array from raw Groq output.

    Strategy (in order):
    1. re.search with DOTALL to grab the outermost [...] — handles any prefix/suffix text.
    2. Strip markdown fences then bracket-count scan as fallback.
    """
    # --- Strategy 1: regex with DOTALL (handles fences, prefixes, suffixes) ---
    match = re.search(r'(\[.*\])', text, re.DOTALL)
    if match:
        candidate = match.group(1).strip()
        # Quick sanity: it should at least start with [ and end with ]
        if candidate.startswith("[") and candidate.endswith("]"):
            print(f"[GROQ] JSON extracted via regex ({len(candidate)} chars).")
            return candidate

    # --- Strategy 2: strip fences + bracket-counting scan ---
    fenced = re.sub(r"```(?:json)?\s*", "", text)
    fenced = re.sub(r"```", "", fenced).strip()

    start = fenced.find("[")
    if start == -1:
        print("[GROQ] WARNING: No JSON array bracket found in response.")
        return fenced  # let json.loads raise a clear error

    depth = 0
    end = -1
    for idx in range(start, len(fenced)):
        if fenced[idx] == "[":
            depth += 1
        elif fenced[idx] == "]":
            depth -= 1
            if depth == 0:
                end = idx
                break

    if end == -1:
        print("[GROQ] WARNING: Unterminated JSON array in response.")
        return fenced

    print(f"[GROQ] JSON extracted via bracket scan ({end - start + 1} chars).")
    return fenced[start: end + 1]


def _parse_response(raw: str) -> list[dict]:
    """Extract and parse the JSON array from Groq output."""
    json_str = _extract_json_array(raw)
    print(f"[GROQ] Extracted JSON string (first 400 chars): {json_str[:400]}")

    parsed = json.loads(json_str)

    if not isinstance(parsed, list):
        print(f"[GROQ] WARNING: Parsed JSON is not a list, got {type(parsed)}")
        return []

    results: list[dict] = []
    for item in parsed:
        if not isinstance(item, dict):
            continue
        # Validate required keys — reason is optional, others are mandatory
        if not all(k in item for k in ("id", "title", "author", "genre")):
            print(f"[GROQ] WARNING: Skipping incomplete item (missing keys): {item}")
            continue
        try:
            item["id"] = int(item["id"])
        except (ValueError, TypeError):
            print(f"[GROQ] WARNING: Invalid ID in item: {item}")
            continue
        item.setdefault("reason", "")
        results.append(item)

    print(f"[GROQ] Parsed {len(results)} valid recommendations from Groq.")
    return results


def get_recommendations(
    purchased_books: list[dict],
    cart_books: list[dict],
    wishlist_books: list[dict],
    catalog: list[dict],
    cold_start_hint: str = "",
) -> list[dict]:
    """
    Call Groq AI and return up to 8 recommended book dicts.

    Each book dict in the input lists and catalog should have:
        id (int), title (str), author (str), genre (str), price (int/float)

    Returns a list of dicts, each with:
        id, title, author, genre, reason

    Returns [] on any failure (timeout, HTTP error, parse error, missing API key).
    """
    if not catalog:
        print("[GROQ] No catalog books available — skipping Groq call.")
        return []

    print(
        f"[GROQ] Calling get_recommendations: "
        f"purchased={len(purchased_books)}, cart={len(cart_books)}, "
        f"wishlist={len(wishlist_books)}, catalog={len(catalog)}, "
        f"cold_start={bool(cold_start_hint)}"
    )

    prompt = _build_prompt(purchased_books, cart_books, wishlist_books, catalog, cold_start_hint)

    try:
        raw = _call_groq(prompt)
    except requests.exceptions.HTTPError as exc:
        print(f"[GROQ] HTTP {exc.response.status_code} error. Body: {exc.response.text[:500]}")
        return []
    except requests.exceptions.Timeout:
        print(f"[GROQ] Request timed out after {_TIMEOUT} seconds.")
        return []
    except requests.exceptions.ConnectionError as exc:
        print(f"[GROQ] Network/connection error: {exc}")
        return []
    except requests.exceptions.RequestException as exc:
        print(f"[GROQ] Request error: {type(exc).__name__}: {exc}")
        return []
    except (KeyError, IndexError) as exc:
        print(f"[GROQ] Unexpected response structure: {exc}")
        return []
    except json.JSONDecodeError as exc:
        print(f"[GROQ] Failed to parse Groq HTTP response body as JSON: {exc}")
        return []
    except ValueError as exc:
        print(f"[GROQ] Config error: {exc}")
        return []
    except Exception as exc:  # noqa: BLE001
        print(f"[GROQ] Unexpected error: {type(exc).__name__}: {exc}")
        return []

    if not raw or not raw.strip():
        print("[GROQ] Empty content returned by Groq.")
        return []

    try:
        results = _parse_response(raw)
        print(f"[GROQ] Final result: {len(results)} recommendations returned.")
        return results
    except (json.JSONDecodeError, ValueError) as exc:
        print(f"[GROQ] JSON parse failure: {exc} | raw excerpt: {raw[:300]!r}")
        return []
