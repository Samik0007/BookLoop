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
_TIMEOUT = 30          # seconds — increased for slow networks
_MAX_TOKENS = 2048     # 8 books with reasons needs ~1500 tokens; 2048 is safe
_TEMPERATURE = 0.3


def _build_prompt(
    purchased: list[dict],
    cart: list[dict],
    wishlist: list[dict],
    catalog: list[dict],
    cold_start_hint: str = "",
) -> str:
    """Return the full system+user prompt string."""

    def _fmt(books: list[dict]) -> str:
        if not books:
            return "  (none)"
        return "\n".join(
            f"  - {b.get('title', 'Unknown')} by {b.get('author', 'Unknown')} [{b.get('genre', 'General')}]"
            for b in books
        )

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

    # Cold-start: no user history — add a discovery hint so Groq has a signal
    history_section = (
        f"PURCHASED (strongest signal):\n{_fmt(purchased)}\n\n"
        f"IN CART (strong signal):\n{_fmt(cart)}\n\n"
        f"IN WISHLIST (moderate signal):\n{_fmt(wishlist)}"
    )
    if cold_start_hint:
        history_section += (
            f"\n\nCOLD-START HINT (user is new — no history yet):\n  {cold_start_hint}\n"
            "  Recommend a diverse and popular selection of 8 books from different genres."
        )

    return (
        "You are a book recommendation engine for a second-hand book marketplace in Nepal.\n"
        "A user's reading history and interests are provided below. Recommend exactly 8 books "
        "strictly from the AVAILABLE CATALOG list.\n\n"
        "--- USER HISTORY ---\n"
        f"{history_section}\n\n"
        "--- AVAILABLE CATALOG ---\n"
        f"{catalog_lines}\n\n"
        "--- RULES ---\n"
        f"1. {exclude_note}\n"
        "2. Recommend exactly 8 books from the catalog above.\n"
        "3. Prioritize books in similar genres to the user's history (or vary genres for new users).\n"
        "4. Return ONLY a raw JSON array — no markdown fences, no explanation, no intro text.\n"
        "5. Each object must have exactly these keys:\n"
        '   {"id": <int>, "title": <str>, "author": <str>, "genre": <str>, "reason": <one sentence str>}\n'
        "6. If fewer than 8 good matches exist, return as many as possible (minimum 1).\n"
        "7. Do not invent books or IDs — only use books from the catalog.\n"
        "8. Start your response with [ and end with ] — nothing else.\n\n"
        "Output (raw JSON array only):"
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
