"""
User Interaction Tracking for Better Recommendations
Tracks user behavior: views, searches, time spent, etc.
"""

from django.utils import timezone

from recommendations.models import UserInteraction
from recommendations.signals import log_user_interaction


def track_product_view(user, product, session_id=None):
    """
    Track when a user views a product detail page
    """
    from .models import UserBehavior, UserGenrePreference
    
    if user.is_authenticated:
        UserBehavior.objects.create(
            user=user.username,
            product=product,
            interaction_type='view',
            session_id=session_id
        )

        # Increment product view counter for analytics and discount logic
        try:
            product.views = (product.views or 0) + 1
            product.save(update_fields=["views"])
        except Exception:
            # Never let a tracking failure impact the user experience
            pass

        # Log implicit feedback for the recommendation engine
        log_user_interaction(user=user, book=product, action=UserInteraction.ACTION_VIEW)
        
        # Update genre preference
        if product.genre:
            genres = [g.strip() for g in product.genre.replace('/', ',').split(',')]
            for genre in genres:
                UserGenrePreference.update_for_user(user.username, genre, 0.5)


def track_search(user, query, session_id=None):
    """
    Track user search queries
    """
    from .models import UserBehavior
    
    if user.is_authenticated:
        UserBehavior.objects.create(
            user=user.username,
            interaction_type='search',
            search_query=query,
            session_id=session_id
        )


def track_cart_addition(user, product, session_id=None):
    """
    Track when user adds product to cart
    """
    from .models import UserBehavior, UserGenrePreference
    
    if user.is_authenticated:
        UserBehavior.objects.create(
            user=user.username,
            product=product,
            interaction_type='cart_add',
            session_id=session_id
        )

        # Log implicit feedback for the recommendation engine
        log_user_interaction(user=user, book=product, action=UserInteraction.ACTION_CART)
        
        # Higher weight for cart additions
        if product.genre:
            genres = [g.strip() for g in product.genre.replace('/', ',').split(',')]
            for genre in genres:
                UserGenrePreference.update_for_user(user.username, genre, 1.5)


def track_wishlist_addition(user, product, session_id=None):
    """
    Track when user adds product to wishlist
    """
    from .models import UserBehavior, UserGenrePreference
    
    if user.is_authenticated:
        UserBehavior.objects.create(
            user=user.username,
            product=product,
            interaction_type='wishlist_add',
            session_id=session_id
        )

        # Log implicit feedback for the recommendation engine
        log_user_interaction(user=user, book=product, action=UserInteraction.ACTION_WISHLIST)
        
        # Medium weight for wishlist
        if product.genre:
            genres = [g.strip() for g in product.genre.replace('/', ',').split(',')]
            for genre in genres:
                UserGenrePreference.update_for_user(user.username, genre, 1.0)


def track_purchase(user, product, session_id=None):
    """
    Track when user purchases a product
    """
    from .models import UserBehavior, UserGenrePreference
    
    if user.is_authenticated:
        UserBehavior.objects.create(
            user=user.username,
            product=product,
            interaction_type='purchase',
            session_id=session_id
        )

        # Log implicit feedback for the recommendation engine
        log_user_interaction(user=user, book=product, action=UserInteraction.ACTION_PURCHASE)
        
        # Highest weight for purchases
        if product.genre:
            genres = [g.strip() for g in product.genre.replace('/', ',').split(',')]
            for genre in genres:
                UserGenrePreference.update_for_user(user.username, genre, 3.0)
