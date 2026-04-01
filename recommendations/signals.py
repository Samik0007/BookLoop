from __future__ import annotations

from typing import Optional

from django.contrib.auth.models import AbstractBaseUser

from .models import UserInteraction


# Default weights for each implicit action
ACTION_WEIGHTS = {
    UserInteraction.ACTION_PURCHASE: 5,
    UserInteraction.ACTION_CART: 3,
    UserInteraction.ACTION_WISHLIST: 2,
    UserInteraction.ACTION_VIEW: 1,
}


def log_user_interaction(
    *,
    user: AbstractBaseUser | None,
    book,
    action: str,
    weight: Optional[int] = None,
) -> None:
    """Create or update a UserInteraction record.

    This is intended to be called from views or existing tracking utilities
    (e.g., books.user_interaction) whenever the user performs an action.
    """

    if user is None or not getattr(user, "is_authenticated", False):
        return

    if book is None:
        return

    # Validate action and derive default weight
    if action not in ACTION_WEIGHTS:
        return

    resolved_weight = weight if weight is not None else ACTION_WEIGHTS[action]

    # Either create a new record or update the existing one for this (user, book, action)
    interaction, _created = UserInteraction.objects.get_or_create(
        user=user,
        book=book,
        action=action,
        defaults={"weight": resolved_weight},
    )

    if not _created and interaction.weight != resolved_weight:
        interaction.weight = resolved_weight
        interaction.save(update_fields=["weight"])
