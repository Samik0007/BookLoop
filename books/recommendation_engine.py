"""
AI-Powered Book Recommendation Engine
Implements hybrid recommendation system combining:
1. Collaborative Filtering (user-user similarity)
2. Content-Based Filtering (genre-based)
3. Popularity-Based Recommendations
"""

from django.db.models import Count, Q
from collections import defaultdict, Counter
from datetime import timedelta
from django.utils import timezone


class RecommendationEngine:
    """
    Advanced recommendation system for personalized book suggestions
    """
    
    def __init__(self, user, num_recommendations=8):
        self.user = user
        self.num_recommendations = num_recommendations
        
    def get_recommendations(self):
        """
        Generate personalized recommendations using hybrid approach
        Returns: QuerySet of recommended products
        """
        from .models import Product
        
        # Get user's interaction history
        user_purchases = self._get_user_purchases()
        user_wishlist = self._get_user_wishlist()
        user_genres = self._extract_user_genre_preferences()
        
        # Calculate recommendation scores using multiple algorithms
        recommendations = defaultdict(float)
        
        # 1. Content-Based: Genre similarity (40% weight)
        genre_recs = self._content_based_recommendations(user_genres)
        for product_id, score in genre_recs.items():
            recommendations[product_id] += score * 0.4
        
        # 2. Collaborative Filtering: Similar users (35% weight)
        collab_recs = self._collaborative_filtering(user_purchases)
        for product_id, score in collab_recs.items():
            recommendations[product_id] += score * 0.35
        
        # 3. Trending/Popular books in user's genres (25% weight)
        trending_recs = self._trending_in_preferred_genres(user_genres)
        for product_id, score in trending_recs.items():
            recommendations[product_id] += score * 0.25
        
        # Exclude books user already purchased or has in wishlist
        exclude_ids = set(user_purchases + user_wishlist)
        recommendations = {k: v for k, v in recommendations.items() 
                          if k not in exclude_ids}
        
        # Sort by score and get top recommendations
        sorted_recommendations = sorted(
            recommendations.items(), 
            key=lambda x: x[1], 
            reverse=True
        )[:self.num_recommendations]
        
        recommended_ids = [pid for pid, _ in sorted_recommendations]
        
        # Fallback: if not enough recommendations, add popular books
        if len(recommended_ids) < self.num_recommendations:
            fallback = self._get_popular_books(
                exclude=exclude_ids | set(recommended_ids),
                limit=self.num_recommendations - len(recommended_ids)
            )
            recommended_ids.extend(fallback)
        
        # Return products maintaining recommendation order
        if not recommended_ids:
            return Product.objects.all()[:self.num_recommendations]
            
        preserved_order = f"CASE {' '.join(f'WHEN id={pid} THEN {i}' for i, pid in enumerate(recommended_ids))} END"
        return Product.objects.filter(id__in=recommended_ids).extra(
            select={'ordering': preserved_order},
            order_by=['ordering']
        )
    
    def _get_user_purchases(self):
        """Get list of product IDs user has purchased"""
        from .models import OrderItem
        
        completed_orders = OrderItem.objects.filter(
            order__user=self.user.username,
            order__complete=True
        ).values_list('Book_name_id', flat=True)
        
        return list(completed_orders)
    
    def _get_user_wishlist(self):
        """Get list of product IDs in user's wishlist"""
        from .models import Wishlist
        
        wishlist_items = Wishlist.objects.filter(
            user=self.user
        ).values_list('product_id', flat=True)
        
        return list(wishlist_items)
    
    def _extract_user_genre_preferences(self):
        """
        Analyze user's purchase and wishlist history to determine genre preferences
        Returns: dict of {genre: preference_score}
        """
        from .models import OrderItem, Wishlist
        
        genre_scores = Counter()
        
        # Weight purchases higher than wishlist items
        purchases = OrderItem.objects.filter(
            order__user=self.user.username,
            order__complete=True
        ).select_related('Book_name')
        
        for item in purchases:
            if item.Book_name and item.Book_name.genre:
                genres = [g.strip() for g in item.Book_name.genre.replace('/', ',').split(',')]
                for genre in genres:
                    genre_scores[genre.lower()] += 2.0
        
        # Add wishlist items with lower weight
        wishlist = Wishlist.objects.filter(user=self.user).select_related('product')
        for item in wishlist:
            if item.product and item.product.genre:
                genres = [g.strip() for g in item.product.genre.replace('/', ',').split(',')]
                for genre in genres:
                    genre_scores[genre.lower()] += 1.0
        
        return dict(genre_scores)
    
    def _content_based_recommendations(self, user_genres):
        """
        Recommend books based on genre similarity
        Returns: dict of {product_id: score}
        """
        from .models import Product
        
        if not user_genres:
            return {}
        
        recommendations = {}
        all_products = Product.objects.all()
        
        for product in all_products:
            if not product.genre:
                continue
            
            product_genres = [g.strip().lower() for g in 
                            product.genre.replace('/', ',').split(',')]
            
            score = 0
            for pgenre in product_genres:
                if pgenre in user_genres:
                    score += user_genres[pgenre]
            
            if score > 0:
                recommendations[product.id] = score / len(product_genres)
        
        return recommendations
    
    def _collaborative_filtering(self, user_purchases):
        """
        Find similar users and recommend what they bought
        Returns: dict of {product_id: score}
        """
        from .models import OrderItem
        
        if not user_purchases:
            return {}
        
        # Find users who bought similar books
        similar_users = OrderItem.objects.filter(
            Book_name_id__in=user_purchases,
            order__complete=True
        ).exclude(
            order__user=self.user.username
        ).values_list('order__user', flat=True).distinct()
        
        recommendations = Counter()
        
        for similar_user in similar_users:
            their_purchases = list(OrderItem.objects.filter(
                order__user=similar_user,
                order__complete=True
            ).values_list('Book_name_id', flat=True))
            
            # Calculate Jaccard similarity
            common_items = set(user_purchases) & set(their_purchases)
            total_items = set(user_purchases) | set(their_purchases)
            
            if total_items:
                similarity = len(common_items) / len(total_items)
                
                for pid in their_purchases:
                    if pid not in user_purchases:
                        recommendations[pid] += similarity
        
        return dict(recommendations)
    
    def _trending_in_preferred_genres(self, user_genres):
        """
        Get currently trending/popular books in user's preferred genres
        Returns: dict of {product_id: score}
        """
        from .models import OrderItem
        
        if not user_genres:
            return {}
        
        # Build genre filter using Book_name FK
        genre_q = Q()
        for genre in user_genres.keys():
            genre_q |= Q(Book_name__genre__icontains=genre)
        
        recent_date = timezone.now() - timedelta(days=60)
        
        trending = OrderItem.objects.filter(
            order__complete=True,
            order__date_ordered__gte=recent_date
        ).filter(genre_q).values('Book_name_id').annotate(
            order_count=Count('id')
        ).order_by('-order_count')[:20]
        
        recommendations = {}
        if not trending:
            return recommendations
            
        max_count = trending[0]['order_count']
        
        for item in trending:
            recommendations[item['Book_name_id']] = item['order_count'] / max_count
        
        return recommendations
    
    def _get_popular_books(self, exclude=None, limit=8):
        """
        Fallback: Get most popular books overall
        Returns: list of product IDs
        """
        from .models import OrderItem
        
        exclude = exclude or set()
        
        popular = OrderItem.objects.filter(
            order__complete=True
        ).exclude(
            Book_name_id__in=exclude
        ).values('Book_name_id').annotate(
            order_count=Count('id')
        ).order_by('-order_count')[:limit]
        
        return [item['Book_name_id'] for item in popular]


def get_recommendations_for_user(user, num_recommendations=8):
    """
    Convenience function to get recommendations for a user
    """
    from .models import Product
    
    if not user.is_authenticated:
        return Product.objects.all()[:num_recommendations]
    
    try:
        engine = RecommendationEngine(user, num_recommendations)
        recs = engine.get_recommendations()
        if not recs.exists():
            return Product.objects.all()[:num_recommendations]
        return recs
    except Exception:
        # Graceful fallback on any error
        return Product.objects.all()[:num_recommendations]


def get_similar_books(product, limit=6):
    """
    Get books similar to a given product (for product detail page)
    """
    from .models import Product
    
    if not product.genre:
        return Product.objects.exclude(id=product.id)[:limit]
    
    # Extract genres
    product_genres = [g.strip().lower() for g in 
                     product.genre.replace('/', ',').split(',')]
    
    if not product_genres:
        return Product.objects.exclude(id=product.id)[:limit]
    
    # Find books with overlapping genres
    genre_q = Q(genre__icontains=product_genres[0])
    for genre in product_genres[1:]:
        genre_q |= Q(genre__icontains=genre)
    
    similar_books = Product.objects.exclude(id=product.id).filter(genre_q).distinct()
    
    # Prioritize same author
    same_author = list(similar_books.filter(Author=product.Author).values_list('id', flat=True)[:limit // 2])
    other_similar = list(similar_books.exclude(id__in=same_author).values_list('id', flat=True)[:limit])
    
    # Combine
    result_ids = same_author + [pid for pid in other_similar if pid not in same_author]
    result_ids = result_ids[:limit]
    
    if not result_ids:
        return Product.objects.exclude(id=product.id)[:limit]
    
    preserved_order = f"CASE {' '.join(f'WHEN id={pid} THEN {i}' for i, pid in enumerate(result_ids))} END"
    return Product.objects.filter(id__in=result_ids).extra(
        select={'ordering': preserved_order},
        order_by=['ordering']
    )
