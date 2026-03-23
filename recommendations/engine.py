from __future__ import annotations

from typing import Dict, Iterable, List

import pandas as pd
from django.core.cache import cache
from sklearn.metrics.pairwise import cosine_similarity

from .models import UserInteraction


def _build_user_item_matrix() -> pd.DataFrame:
    """Return a user-item matrix DataFrame from UserInteraction records.

    Index: user_id, Columns: book_id, Values: aggregated weight.
    """

    interactions_qs = UserInteraction.objects.all().values("user_id", "book_id", "weight")
    if not interactions_qs.exists():
        return pd.DataFrame()

    df = pd.DataFrame.from_records(interactions_qs)
    if df.empty:
        return pd.DataFrame()

    # Aggregate by (user, book) in case of multiple interactions
    df_agg = df.groupby(["user_id", "book_id"], as_index=False)["weight"].sum()

    user_item = df_agg.pivot(index="user_id", columns="book_id", values="weight").fillna(0)
    return user_item


def _compute_item_similarity(user_item: pd.DataFrame) -> pd.DataFrame:
    """Compute item-item cosine similarity matrix.

    Returns a DataFrame where both index and columns are book_ids.
    """

    if user_item.empty:
        return pd.DataFrame()

    # Transpose so rows correspond to items
    item_matrix = user_item.T

    if item_matrix.shape[0] == 0 or item_matrix.shape[1] == 0:
        return pd.DataFrame()

    similarity = cosine_similarity(item_matrix)
    return pd.DataFrame(similarity, index=item_matrix.index, columns=item_matrix.index)


def _recommend_for_user(
    user_id: int,
    user_item: pd.DataFrame,
    item_similarity: pd.DataFrame,
    top_n: int = 10,
) -> List[int]:
    """Generate top-N recommended book_ids for a single user.

    The approach is standard item-item collaborative filtering:
    - For each item the user has interacted with, look up similar items.
    - Score candidate items by the similarity weighted by the user's interaction weight.
    - Exclude items the user already interacted with.
    """

    if user_id not in user_item.index:
        return []

    user_vector = user_item.loc[user_id]
    interacted_items: List[int] = [int(bid) for bid, w in user_vector[user_vector > 0].items()]

    if not interacted_items:
        return []

    scores: Dict[int, float] = {}

    for book_id, weight in user_vector[user_vector > 0].items():
        if book_id not in item_similarity.index:
            continue

        # Similarity scores for this item to all others
        sim_series = item_similarity.loc[book_id]

        for candidate_id, sim in sim_series.items():
            if sim <= 0:
                continue
            if candidate_id in interacted_items:
                continue

            scores[candidate_id] = scores.get(candidate_id, 0.0) + float(sim) * float(weight)

    # Sort by score descending and return top N IDs
    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)[:top_n]
    return [int(book_id) for book_id, _score in ranked]


def generate_recommendations(top_n: int = 10) -> None:
    """Compute and cache recommendations for all users.

    This function is designed to run offline via a Celery task. It
    populates the Django cache with keys of the form ``recs_user_{user_id}``.
    """

    user_item = _build_user_item_matrix()
    if user_item.empty:
        # Nothing to compute yet (cold start); simply return.
        return

    item_similarity = _compute_item_similarity(user_item)
    if item_similarity.empty:
        return

    for user_id in user_item.index:
        try:
            recs = _recommend_for_user(int(user_id), user_item, item_similarity, top_n=top_n)
        except Exception:
            # Be conservative: never let a single user break the full batch.
            continue

        cache_key = f"recs_user_{int(user_id)}"
        cache.set(cache_key, recs, timeout=60 * 60 * 24)  # 24 hours
