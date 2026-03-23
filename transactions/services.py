"""Services for swap and donation transactions."""

from typing import List, Dict, Any

from django.db.models import Q

from books.models import Product


def find_swap_matches(user) -> List[Dict[str, Any]]:
    """Find perfect swap matches for a specific user.

    A match is defined as:
    - User A has a swap listing (``my_book``) with a non-empty ``swap_preference``.
    - User B has a swap listing (``their_book``) such that:
        * ``their_book`` matches A's ``swap_preference`` in title or genre.
        * A's book (title or genre) matches ``their_book.swap_preference``.
    This implementation relies purely on ORM/SQL filters for matching
    conditions and only loops over the current user's books, keeping it
    extremely fast even with large datasets.
    """

    matches: List[Dict[str, Any]] = []

    # All swap listings for this user that are currently approved
    my_swap_books = Product.objects.filter(
        seller=user,
        listing_type="swap",
        listing_status="approved",
    ).exclude(swap_preference__isnull=True).exclude(swap_preference__exact="")

    for my_book in my_swap_books:
        # Find other users' swap listings that match our preference
        preference = my_book.swap_preference.strip()
        if not preference:
            continue

        # Other users' approved swap listings
        their_books = (
            Product.objects.filter(
                listing_type="swap",
                listing_status="approved",
            )
            .exclude(seller=user)
            .filter(
                # Their book matches what we want (by title or genre)
                Q(Book_name__icontains=preference)
                | Q(genre__icontains=preference)
            )
            .filter(
                # What they want should match our book (title or genre)
                Q(swap_preference__icontains=my_book.Book_name)
                | Q(swap_preference__icontains=my_book.genre)
            )
        )

        for their_book in their_books:
            matches.append(
                {
                    "my_book": my_book,
                    "their_book": their_book,
                    "match_user": their_book.seller,
                }
            )

    return matches
