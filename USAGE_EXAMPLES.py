"""
Example Usage of AI Recommendation System
Demonstrates how to use the recommendation engine programmatically
"""

# ==========================================
# Example 1: Get Recommendations for a User
# ==========================================

from books.recommendation_engine import get_recommendations_for_user
from django.contrib.auth.models import User

# In your view or script:
user = request.user  # Or: User.objects.get(username='john')
recommendations = get_recommendations_for_user(user, num_recommendations=10)

# Returns: QuerySet of Product objects
for book in recommendations:
    print(f"{book.Book_name} by {book.Author} - Rs. {book.price}")


# ==========================================
# Example 2: Get Similar Books
# ==========================================

from books.recommendation_engine import get_similar_books
from books.models import Product

# Get a book
product = Product.objects.get(id=5)

# Find similar books
similar = get_similar_books(product, limit=8)

for book in similar:
    print(f"Similar: {book.Book_name} - Genre: {book.genre}")


# ==========================================
# Example 3: Track User Interactions
# ==========================================

from books.user_interaction import (
    track_product_view,
    track_search,
    track_cart_addition,
    track_wishlist_addition,
    track_purchase
)

# In your views:
def product_detail_view(request, product_id):
    product = Product.objects.get(id=product_id)
    
    # Track the view
    if request.user.is_authenticated:
        session_id = request.session.session_key
        track_product_view(request.user, product, session_id)
    
    # ... rest of your view


# ==========================================
# Example 4: Update Genre Preferences Manually
# ==========================================

from books.user_interaction import UserGenrePreference

# Update preference for a user
UserGenrePreference.update_for_user(
    username='john',
    genre='Science Fiction',
    score_increment=2.0
)


# ==========================================
# Example 5: Get User's Genre Preferences
# ==========================================

from books.user_interaction import UserGenrePreference

preference = UserGenrePreference.objects.get(user='john')
print(preference.genre_scores)
# Output: {'fiction': 5.5, 'self-help': 3.0, 'science': 2.0}


# ==========================================
# Example 6: Custom Recommendation Logic
# ==========================================

from books.recommendation_engine import RecommendationEngine

# Create custom engine
engine = RecommendationEngine(user=request.user, num_recommendations=20)

# Use individual methods
user_purchases = engine._get_user_purchases()
user_genres = engine._extract_user_genre_preferences()
genre_recommendations = engine._content_based_recommendations(user_genres)

# Get full recommendations
recommendations = engine.get_recommendations()


# ==========================================
# Example 7: Filter Recommendations by Price
# ==========================================

def get_affordable_recommendations(user, max_price=500):
    """Get recommendations within budget"""
    from books.recommendation_engine import get_recommendations_for_user
    
    recommendations = get_recommendations_for_user(user, num_recommendations=20)
    affordable = recommendations.filter(price__lte=max_price)[:8]
    
    return affordable


# ==========================================
# Example 8: Get Genre-Specific Recommendations
# ==========================================

def get_genre_recommendations(user, genre, limit=10):
    """Get recommendations for a specific genre"""
    from books.recommendation_engine import get_recommendations_for_user
    
    all_recommendations = get_recommendations_for_user(user, num_recommendations=50)
    genre_specific = all_recommendations.filter(genre__icontains=genre)[:limit]
    
    return genre_specific


# ==========================================
# Example 9: Recommendation Analytics
# ==========================================

from books.user_interaction import UserBehavior
from django.db.models import Count

# Most viewed books by user
def get_user_most_viewed(username):
    most_viewed = UserBehavior.objects.filter(
        user=username,
        interaction_type='view'
    ).values('product__Book_name').annotate(
        view_count=Count('id')
    ).order_by('-view_count')[:10]
    
    return most_viewed


# Most searched terms
def get_popular_searches():
    popular = UserBehavior.objects.filter(
        interaction_type='search'
    ).values('search_query').annotate(
        search_count=Count('id')
    ).order_by('-search_count')[:20]
    
    return popular


# ==========================================
# Example 10: Batch Update Recommendations
# ==========================================

def update_recommendations_for_all_users():
    """Pre-calculate and cache recommendations for all users"""
    from django.contrib.auth.models import User
    from books.recommendation_engine import get_recommendations_for_user
    from django.core.cache import cache
    
    users = User.objects.all()
    
    for user in users:
        # Calculate recommendations
        recommendations = get_recommendations_for_user(user, num_recommendations=10)
        
        # Cache for 1 hour
        cache_key = f'recommendations_{user.username}'
        cache.set(cache_key, list(recommendations.values_list('id', flat=True)), 3600)
        
        print(f"Updated recommendations for {user.username}")


# ==========================================
# Example 11: REST API Endpoint (if using DRF)
# ==========================================

from rest_framework.decorators import api_view
from rest_framework.response import Response

@api_view(['GET'])
def api_get_recommendations(request):
    """
    GET /api/recommendations/
    Returns personalized recommendations
    """
    if not request.user.is_authenticated:
        return Response({'error': 'Authentication required'}, status=401)
    
    from books.recommendation_engine import get_recommendations_for_user
    
    recommendations = get_recommendations_for_user(request.user, num_recommendations=10)
    
    data = [{
        'id': book.id,
        'name': book.Book_name,
        'author': book.Author,
        'genre': book.genre,
        'price': book.price,
        'image_url': book.imageURL
    } for book in recommendations]
    
    return Response(data)


# ==========================================
# Example 12: Command Line Testing
# ==========================================

"""
Run in Django shell:

python manage.py shell

Then:

from django.contrib.auth.models import User
from books.recommendation_engine import get_recommendations_for_user
from books.models import Product

# Get a user
user = User.objects.first()

# Get recommendations
recs = get_recommendations_for_user(user, num_recommendations=5)

# Print results
for book in recs:
    print(f"{book.Book_name} - {book.genre}")
"""


# ==========================================
# Example 13: Integration with Views
# ==========================================

# In your books/views.py

def home_with_recommendations(request):
    """Home page with AI recommendations"""
    from books.recommendation_engine import get_recommendations_for_user
    from books.models import Product
    from django.db.models import Count, Q
    
    cartItems = 0
    recommended_books = []
    
    if request.user.is_authenticated:
        # Get cart items
        order, _ = Order.objects.get_or_create(
            user=request.user.username, complete=False
        )
        cartItems = order.get_cart_items
        
        # Get AI recommendations
        recommended_books = get_recommendations_for_user(request.user, num_recommendations=8)
    else:
        # For anonymous users, show popular books
        recommended_books = Product.objects.annotate(
            order_count=Count('orderitem', filter=Q(orderitem__order__complete=True))
        ).order_by('-order_count')[:8]
    
    context = {
        'cartItems': cartItems,
        'recommended_books': recommended_books,
        'page_title': 'Home - AI Recommendations'
    }
    
    return render(request, 'index.html', context)


# ==========================================
# TIPS FOR BEST RESULTS
# ==========================================

"""
1. TRACK EVERYTHING
   - Always track user interactions
   - More data = Better recommendations

2. GENRE QUALITY
   - Ensure books have proper genres set
   - Use consistent genre naming
   - Split multiple genres with commas

3. PERIODIC UPDATES
   - Run batch updates during off-peak hours
   - Clear old UserBehavior data (older than 6 months)

4. A/B TESTING
   - Test different weight combinations
   - Measure click-through rates
   - Adjust algorithm weights based on results

5. PERFORMANCE
   - Cache recommendations for frequently accessed users
   - Use select_related() and prefetch_related()
   - Add database indexes (already included)

6. USER FEEDBACK
   - Add "Not interested" button on recommendations
   - Let users adjust genre preferences
   - Track recommendation click rates
"""
