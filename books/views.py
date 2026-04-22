from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponseRedirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Case, When, IntegerField, Value, Count, F, Sum, Avg, ExpressionWrapper, DecimalField, Subquery, OuterRef
from django.db import transaction
from django.views.generic import ListView
from django.views.generic.edit import CreateView
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse, reverse_lazy
import json
import datetime
import random
import requests
from django.conf import settings
from django.core.mail import send_mail
from django.core.validators import validate_email
from django.core.exceptions import ValidationError

from .models import Product, Rating, Order, OrderItem, Wishlist, ShippingAddress, UserBehavior
from .recommendation_engine import get_recommendations_for_user, get_similar_books
from recommendations.services import get_user_recommendations
from .user_interaction import (
    track_product_view, track_search, track_cart_addition, 
    track_wishlist_addition, track_purchase
)
from .forms import DonateBookForm, SwapBookForm


def _get_or_create_active_order(username: str) -> "Order":
    """Return the latest incomplete order for *username*, creating one if needed.

    Replaces all get_or_create(user=..., complete=False) calls which raise
    MultipleObjectsReturned when a user ends up with more than one open order.
    """
    order = Order.objects.filter(user=username, complete=False).last()
    if order is None:
        order = Order.objects.create(user=username, complete=False)
    return order


def _approved_swap_books_queryset():
    """Return approved swap listings with seller preloaded.

    Uses ``select_related('seller')`` to avoid N+1 queries when templates
    display seller information.
    """

    return Product.objects.select_related("seller").filter(
        listing_type="swap",
        listing_status="approved",
    ).order_by("-pub_date")


def _get_diverse_books(limit=10):
    """
    Return up to `limit` books with genre diversity.

    Strategy:
      1. Pick the single most-recent approved book from every distinct genre.
      2. Shuffle so the order feels fresh on every page load.
      3. If >= limit, return the first `limit` entries.
      4. If < limit, fill remaining slots with the newest approved books
         not already selected.
    Uses select_related('seller') throughout to avoid N+1 queries.
    """
    base_qs = (
        Product.objects.select_related("seller")
        .filter(listing_type="sell", listing_status="approved")
    )
    genres = base_qs.values_list("genre", flat=True).distinct()

    diverse_books = []
    seen_ids = set()

    for genre in genres:
        book = base_qs.filter(genre=genre).order_by("-pub_date", "-id").first()
        if book and book.id not in seen_ids:
            diverse_books.append(book)
            seen_ids.add(book.id)

    # Randomise so homepage looks different on every load
    random.shuffle(diverse_books)

    if len(diverse_books) >= limit:
        return diverse_books[:limit]

    # Fill remaining slots with newest books not already chosen
    needed = limit - len(diverse_books)
    fillers = list(base_qs.exclude(id__in=seen_ids).order_by("-id")[:needed])
    diverse_books.extend(fillers)
    return diverse_books


class DiscountOffersView(ListView):
    """List view for dynamically discounted offers.

    Shows books that have relatively high stock and low view counts,
    ordered by stock descending. Pricing is handled via the
    ``discounted_price`` property on ``Product``.
    """

    model = Product
    template_name = "discount_offers.html"
    context_object_name = "discount_books"

    def get_queryset(self):
        # High stock (quantity) and low interest (views)
        return (
            Product.objects.filter(quantity__gte=5, views__lte=50)
            .order_by("-quantity")
        )

    def get_context_data(self, **kwargs):  # type: ignore[override]
        context = super().get_context_data(**kwargs)

        cart_items = 0
        if self.request.user.is_authenticated:
            order = _get_or_create_active_order(self.request.user.username)
            cart_items = order.get_cart_items

        context["cartItems"] = cart_items
        return context


class AddSwapBookView(LoginRequiredMixin, CreateView):
    """Allow authenticated users to add a book to their swap list.

    Creates a Product with listing_type='swap' and listing_status='pending'.
    """

    model = Product
    form_class = SwapBookForm
    template_name = "books/add_swap_book.html"
    login_url = reverse_lazy("login")

    def form_valid(self, form):
        """Populate seller and listing metadata before saving.

        Also ensures required fields like genre have a safe default.
        """

        form.instance.seller = self.request.user
        form.instance.listing_type = "swap"
        form.instance.listing_status = "pending"
        form.instance.price = 0
        if not form.instance.contact_email and self.request.user.email:
            form.instance.contact_email = self.request.user.email

        # Ensure genre is not empty for swap-only listings.
        if not form.instance.genre:
            form.instance.genre = "Swap Listing"

        messages.success(
            self.request,
            "Your book was submitted for swapping and is pending review.",
        )
        return super().form_valid(form)

    def get_success_url(self):  # type: ignore[override]
        return reverse_lazy("swap_matches")


class BrowseSwapBooksView(ListView):
    """Browse all approved swap listings."""

    model = Product
    template_name = "books/browse_swaps.html"
    context_object_name = "books"
    paginate_by = 12

    def get_queryset(self):  # type: ignore[override]
        return _approved_swap_books_queryset()


class AddDonationBookView(LoginRequiredMixin, CreateView):
    """Allow authenticated users to submit a book donation.

    Creates a Product with listing_type='donate' and listing_status='pending'.
    """

    model = Product
    form_class = DonateBookForm
    template_name = "books/add_donation.html"
    login_url = reverse_lazy("login")

    def form_valid(self, form):
        form.instance.seller = self.request.user
        form.instance.listing_type = "donate"
        form.instance.listing_status = "pending"
        form.instance.price = 0
        if not form.instance.contact_email and self.request.user.email:
            form.instance.contact_email = self.request.user.email

        # Genre is required on Product but not part of the donation UX.
        if not form.instance.genre:
            form.instance.genre = "Donation"

        messages.success(
            self.request,
            "✅ Your book has been submitted! It is pending admin approval and will appear in the donations page once approved.",
        )
        return super().form_valid(form)

    def get_success_url(self):  # type: ignore[override]
        return reverse_lazy("browse_donations")


class BrowseDonationsView(ListView):
    """Public page listing approved donation books."""

    model = Product
    template_name = "books/browse_donations.html"
    context_object_name = "books"
    paginate_by = 12

    def get_queryset(self):  # type: ignore[override]
        return (
            Product.objects.select_related("seller")
            .filter(listing_type="donate", listing_status="approved")
            .order_by("-pub_date", "-id")
        )

    def get_context_data(self, **kwargs):  # type: ignore[override]
        context = super().get_context_data(**kwargs)
        from django.conf import settings as django_settings
        context["admin_email"] = getattr(django_settings, "EMAIL_HOST_USER", "samikisdope07@gmail.com")
        return context

# -------------------------
# BASIC PAGES
# -------------------------

def index_page(request):
    """
    Home page with AI-powered personalized recommendations
    """
    cartItems = 0
    recommended_books = []
    all_books = _get_diverse_books(limit=10)
    featured_books = (
        Product.objects.filter(listing_type="sell", listing_status="approved")
        .annotate(
            purchase_count=Count(
                "orderitem",
                filter=Q(orderitem__order__complete=True),
                distinct=True,
            ),
            wishlist_count=Count("wishlist", distinct=True),
            popularity_score=(
                Count("orderitem", filter=Q(orderitem__order__complete=True), distinct=True)
                + Count("wishlist", distinct=True)
                + Count("ratings", distinct=True)
            ),
        )
        .order_by("-popularity_score", "-views", "-average_rating")[:10]
    )
    nepali_books = (
        Product.objects.select_related("seller")
        .filter(
            Q(genre__icontains="nepali")
            | Q(genre__icontains="nepal")
            | Q(genre__icontains="नेपाल")
            | Q(genre__icontains="नेपाली"),
            listing_status="approved",
            listing_type="sell",
        )
        .annotate(
            purchase_count=Count(
                "orderitem",
                filter=Q(orderitem__order__complete=True),
                distinct=True,
            ),
            wishlist_count=Count("wishlist", distinct=True),
            rating_count_ann=Count("ratings", distinct=True),
            nepali_score=(
                Count("orderitem", filter=Q(orderitem__order__complete=True), distinct=True) * 5
                + Count("wishlist", distinct=True) * 3
                + Count("ratings", distinct=True) * 2
            ),
        )
        .order_by("-nepali_score", "-views", "-average_rating", "-pub_date")[:10]
    )
    
    if request.user.is_authenticated:
        order = _get_or_create_active_order(request.user.username)
        cartItems = order.get_cart_items
        
        # Get AI recommendations
        recommended_books = get_recommendations_for_user(request.user, num_recommendations=8)
    else:
        # For anonymous users, show popular books
        recommended_books = Product.objects.annotate(
            order_count=Count('orderitem', filter=Q(orderitem__order__complete=True))
        ).order_by('-order_count')[:8]
        if not recommended_books.exists():
            recommended_books = Product.objects.all()[:8]

    swap_books = _approved_swap_books_queryset()[:8]
    
    return render(request, 'index.html', {
        'cartItems': cartItems,
        'recommended_books': recommended_books,
        'all_books': all_books,
        'featured_books': featured_books,
        'nepali_books': nepali_books,
        'swap_books': swap_books,
    })


def about(request):
    total_books = Product.objects.count()
    return render(request, 'about.html', {"total_books": total_books})


@login_required
def profile(request):
    from authentication.models import UserProfile

    order = _get_or_create_active_order(request.user.username)
    items         = order.orderitem_set.all()
    cartItems     = order.get_cart_items
    placed_orders = Order.objects.filter(
        user=request.user.username, complete=True
    ).order_by('-date_ordered')
    wishlist_count = Wishlist.objects.filter(user=request.user.username).count()
    total_spent   = sum(o.get_cart_total for o in placed_orders)
    total_orders_count = placed_orders.count()
    recent_orders = placed_orders[:5]

    user_profile, _ = UserProfile.objects.get_or_create(user=request.user)

    if request.method == 'POST' and request.FILES.get('avatar'):
        user_profile.avatar = request.FILES['avatar']
        user_profile.save()
        messages.success(request, 'Profile picture updated!')
        return redirect('profile')

    return render(request, 'profile.html', {
        'items':               items,
        'cartItems':           cartItems,
        'total_orders_count':  total_orders_count,
        'wishlist_count':      wishlist_count,
        'total_spent':         total_spent,
        'recent_orders':       recent_orders,
        'user_profile':        user_profile,
    })


# -------------------------
# STORE / PRODUCTS
# -------------------------

def store(request):
    # Show one card per book title — cheapest in-stock approved listing per title.
    # When that seller's stock hits 0, the next cheapest automatically surfaces.
    _best_id_sub = (
        Product.objects
        .filter(
            Book_name=OuterRef('Book_name'),
            listing_type='sell',
            listing_status='approved',
            quantity__gt=0,
        )
        .order_by('price', 'pub_date')
        .values('id')[:1]
    )
    products = (
        Product.objects
        .select_related('seller')
        .filter(listing_type='sell', listing_status='approved', quantity__gt=0)
        .annotate(best_id=Subquery(_best_id_sub))
        .filter(id=F('best_id'))
    )
    cartItems = 0

    if request.user.is_authenticated:
        order = _get_or_create_active_order(request.user.username)
        cartItems = order.get_cart_items

    # Recently viewed: pull the user's latest view events, deduplicate by product,
    # keep only approved sell listings, cap at 8.
    recently_viewed = []
    if request.user.is_authenticated:
        seen_ids = set()
        for row in (
            UserBehavior.objects
            .filter(
                user=request.user.username,
                interaction_type='view',
                product__isnull=False,
                product__listing_type='sell',
                product__listing_status='approved',
            )
            .select_related('product')
            .order_by('-timestamp')[:50]          # bounded scan on indexed columns
        ):
            if row.product_id not in seen_ids:
                seen_ids.add(row.product_id)
                recently_viewed.append(row.product)
            if len(recently_viewed) >= 8:
                break

    return render(request, 'store.html', {
        'products': products,
        'cartItems': cartItems,
        'recommended_books': recently_viewed,
    })


def nepali_books_page(request):
    """Dedicated page showing all Nepali genre books sorted by popularity."""
    cartItems = 0
    if request.user.is_authenticated:
        order = _get_or_create_active_order(request.user.username)
        cartItems = order.get_cart_items

    sort = request.GET.get("sort", "popular")

    base_qs = (
        Product.objects.select_related("seller")
        .filter(
            Q(genre__icontains="nepali")
            | Q(genre__icontains="nepal")
            | Q(genre__icontains="\u0928\u0947\u092a\u093e\u0932")
            | Q(genre__icontains="\u0928\u0947\u092a\u093e\u0932\u0940"),
            listing_status="approved",
            listing_type="sell",
        )
        .annotate(
            purchase_count=Count(
                "orderitem",
                filter=Q(orderitem__order__complete=True),
                distinct=True,
            ),
            wishlist_count=Count("wishlist", distinct=True),
            nepali_score=(
                Count("orderitem", filter=Q(orderitem__order__complete=True), distinct=True) * 5
                + Count("wishlist", distinct=True) * 3
                + Count("ratings", distinct=True) * 2
            ),
        )
    )

    sort_map = {
        "popular":    "-nepali_score",
        "newest":     "-pub_date",
        "price_low":  "price",
        "price_high": "-price",
        "rating":     "-average_rating",
    }
    order_field = sort_map.get(sort, "-nepali_score")
    secondary = "-views" if sort == "popular" else "-nepali_score"
    books = base_qs.order_by(order_field, secondary)

    return render(request, "nepali_books.html", {
        "books": books,
        "cartItems": cartItems,
        "current_sort": sort,
        "total_count": base_qs.count(),
    })


def prod_detail(request, id):
    """
    Product detail page with similar book recommendations
    """
    product = Product.objects.filter(id=id).first()
    if not product:
        messages.error(request, 'That book is not available right now.')
        return redirect('store')
    cartItems = 0
    similar_books = []
    user_rating = None

    if request.user.is_authenticated:
        order = _get_or_create_active_order(request.user.username)
        cartItems = order.get_cart_items

        existing = Rating.objects.filter(user=request.user, book=product).values_list(
            "score", flat=True
        ).first()
        user_rating = int(existing) if existing is not None else None
        
        # Track product view for recommendations
        session_id = request.session.session_key
        track_product_view(request.user, product, session_id)
    
    # Get similar books using AI
    similar_books = get_similar_books(product, limit=6)

    # Other sellers offering the same book title (cheapest first, excluding current)
    other_sellers = (
        Product.objects
        .select_related('seller')
        .filter(
            Book_name__iexact=product.Book_name,
            listing_type='sell',
            listing_status='approved',
            quantity__gt=0,
        )
        .exclude(id=product.id)
        .order_by('price')
    )

    return render(request, 'productdetails.html', {
        'data': product,
        'cartItems': cartItems,
        'similar_books': similar_books,
        'user_rating': user_rating,
        'other_sellers': other_sellers,
    })


class RateBookView(LoginRequiredMixin, View):
    """Create or update the current user's rating for a book (1-5).

    Uses update-or-create; cached aggregates are refreshed by the Rating model.
    """

    def post(self, request, book_id):
        book = get_object_or_404(Product, id=book_id)
        raw_score = request.POST.get("score")

        try:
            score = int(raw_score)
        except (TypeError, ValueError):
            messages.error(request, "Please select a rating from 1 to 5.")
            return redirect("product", id=book.id)

        if score < 1 or score > 5:
            messages.error(request, "Please select a rating from 1 to 5.")
            return redirect("product", id=book.id)

        already_rated = Rating.objects.filter(user=request.user, book=book).exists()
        if already_rated:
            messages.error(request, "Your review was already recorded once.")
            return redirect("product", id=book.id)

        Rating.objects.create(user=request.user, book=book, score=score)
        messages.success(request, "Thanks! Your rating has been saved.")
        return redirect("product", id=book.id)


# -------------------------
# CART
# -------------------------

def cart(request):
    items = []
    order = None
    cartItems = 0

    if request.user.is_authenticated:
        order = _get_or_create_active_order(request.user.username)
        items = order.orderitem_set.all()
        cartItems = order.get_cart_items

    wishlist_products = []
    if request.user.is_authenticated:
        wishlist_ids = Wishlist.objects.filter(
            user=request.user.username
        ).values_list('product_id', flat=True)
        wishlist_products = list(Product.objects.filter(id__in=wishlist_ids))

    return render(request, 'cart.html', {
        'items': items,
        'order': order,
        'cartItems': cartItems,
        'wishlist_products': wishlist_products,
    })


def checkout(request):
    items = []
    order = None
    cartItems = 0
    buy_now_product_id = request.GET.get('buy_now')
    is_buy_now = False
    buy_now_total = None

    if request.user.is_authenticated:
        order = _get_or_create_active_order(request.user.username)
        cartItems = order.get_cart_items

        if buy_now_product_id:
            single_item = order.orderitem_set.filter(
                Book_name_id=buy_now_product_id
            ).first()
            if single_item:
                items = [single_item]
                is_buy_now = True
                buy_now_total = single_item.Book_name.discounted_price * single_item.quantity
            else:
                items = order.orderitem_set.all()
        else:
            items = order.orderitem_set.all()

    return render(request, 'checkout.html', {
        'items': items,
        'order': order,
        'cartItems': cartItems,
        'is_buy_now': is_buy_now,
        'buy_now_total': buy_now_total,
        'buy_now_product_id': buy_now_product_id,
    })


@login_required
def updateItem(request):
    data = json.loads(request.body)
    productId = data['productId']
    action = data['action']

    original_product = get_object_or_404(Product, id=productId)
    order = _get_or_create_active_order(request.user.username)
    session_id = request.session.session_key

    if action == 'add':
        if original_product.listing_type == 'sell':
            # Route to cheapest in-stock seller for this title.
            # select_for_update prevents two concurrent buyers from both
            # grabbing the last copy (race condition protection).
            with transaction.atomic():
                best = (
                    Product.objects
                    .select_for_update()
                    .filter(
                        Book_name__iexact=original_product.Book_name,
                        listing_type='sell',
                        listing_status='approved',
                        quantity__gt=0,
                    )
                    .order_by('price', 'pub_date')
                    .first()
                )
                if not best:
                    return JsonResponse({'error': 'out_of_stock'}, status=400)

                orderItem, _ = OrderItem.objects.get_or_create(order=order, Book_name=best)
                orderItem.quantity += 1
                best.quantity -= 1
                orderItem.save()
                best.save()

            track_cart_addition(request.user, best, session_id)

        else:
            # Swap / donate listings: no auto-routing, original behaviour
            orderItem, _ = OrderItem.objects.get_or_create(order=order, Book_name=original_product)
            if original_product.quantity <= 0:
                return JsonResponse({'error': 'out_of_stock'}, status=400)
            orderItem.quantity += 1
            original_product.quantity -= 1
            orderItem.save()
            original_product.save()
            track_cart_addition(request.user, original_product, session_id)

    elif action == 'remove':
        product = get_object_or_404(Product, id=productId)
        orderItem, _ = OrderItem.objects.get_or_create(order=order, Book_name=product)
        orderItem.quantity -= 1
        product.quantity += 1
        orderItem.save()
        product.save()
        if orderItem.quantity <= 0:
            orderItem.delete()

    return JsonResponse('Item updated', safe=False)


def remove_from_cart(request, id):
    if request.method == 'POST':
        OrderItem.objects.filter(Book_name_id=id).delete()
    return HttpResponseRedirect('/cart')


# -------------------------
# WISHLIST
# -------------------------

def wishlist(request):
    wishlist_items = []
    cartItems = 0
    items = []
    order = None

    if request.user.is_authenticated:
        order = _get_or_create_active_order(request.user.username)
        items = order.orderitem_set.all()
        cartItems = order.get_cart_items
        wishlist_items = Wishlist.objects.filter(user=request.user)

    return render(request, 'wishlist.html', {
        'wishlist': wishlist_items,
        'items': items,
        'order': order,
        'cartItems': cartItems
    })


def addtowishlist(request):
    if request.method == "POST" and request.user.is_authenticated:
        prod_id = int(request.POST.get('product_id'))
        product = get_object_or_404(Product, id=prod_id)

        if Wishlist.objects.filter(user=request.user, product=product).exists():
            return JsonResponse({'status': 'Already in wishlist'})

        Wishlist.objects.create(user=request.user, product=product)
        
        # Track wishlist addition for AI recommendations
        session_id = request.session.session_key
        track_wishlist_addition(request.user, product, session_id)
        
        return JsonResponse({'status': 'Added to wishlist'})

    return JsonResponse({'status': 'Login required'})


def remove_from_wishlist(request, id):
    if request.method == 'POST':
        Wishlist.objects.filter(user=request.user, product_id=id).delete()
    return HttpResponseRedirect('/wishlist')


# -------------------------
# SEARCH (NO ML)
# -------------------------

def search(request):
    """
    Smart search with genre-intent detection.

    Case A – Exact genre match  : query == a known genre (iexact)
                                  → strict genre filter, no title/author bleed.
    Case B – Partial genre match: query is a substring of one or more genres
                                  → genre-only OR-filter across those genres.
    Case C – Keyword             : no genre signal at all
                                  → title + author search, ranked by relevance.
    """
    query = request.GET.get('q', '').strip()
    books = Product.objects.none()
    cartItems = 0
    search_mode = 'keyword'

    if request.user.is_authenticated:
        order = _get_or_create_active_order(request.user.username)
        cartItems = order.get_cart_items

    if query:
        # -- collect all distinct genre values in one lightweight query ------
        all_genres = list(
            Product.objects
            .exclude(genre__isnull=True)
            .exclude(genre='')
            .values_list('genre', flat=True)
            .distinct()
        )
        q_lower = query.lower()

        # -- Case A: whole query is an exact genre name ----------------------
        exact_genre = next(
            (g for g in all_genres if g.strip().lower() == q_lower), None
        )

        if exact_genre:
            books = (
                Product.objects
                .select_related('seller')
                .filter(genre__iexact=exact_genre, listing_status='approved')
                .order_by('-pub_date')
            )
            search_mode = 'genre_exact'

        else:
            # -- Case B: query is contained in one or more genre names -------
            matching_genres = [
                g for g in all_genres if q_lower in g.strip().lower()
            ]

            if matching_genres:
                genre_q = Q()
                for g in matching_genres:
                    genre_q |= Q(genre__iexact=g)

                books = (
                    Product.objects
                    .select_related('seller')
                    .filter(genre_q, listing_status='approved')
                    .order_by('-pub_date')
                )
                search_mode = 'genre_partial'

            else:
                # -- Case C: no genre signal — pure title / author search ----
                books = (
                    Product.objects
                    .select_related('seller')
                    .filter(
                        Q(Book_name__icontains=query) | Q(Author__icontains=query),
                        listing_status='approved',
                    )
                    .annotate(
                        rank=Case(
                            When(Book_name__iexact=query,      then=Value(4)),
                            When(Book_name__istartswith=query, then=Value(3)),
                            When(Book_name__icontains=query,   then=Value(2)),
                            When(Author__icontains=query,      then=Value(1)),
                            default=Value(0),
                            output_field=IntegerField(),
                        )
                    )
                    .order_by('-rank', '-pub_date')
                )
                search_mode = 'keyword'

        if request.user.is_authenticated:
            session_id = request.session.session_key
            if not session_id:
                request.session.create()
                session_id = request.session.session_key
            track_search(request.user, query, session_id)
    else:
        books = Product.objects.filter(listing_status='approved').order_by('-pub_date')

    return render(request, 'searchbar.html', {
        'query':       query,
        'books':       books,
        'cartItems':   cartItems,
        'result_count': books.count(),
        'search_mode': search_mode,
    })


# -------------------------
# ORDERS
# -------------------------

@login_required
def orders(request):
    # Only show completed orders (complete=True) — these are real placed orders.
    # complete=False means an active cart, not a submitted order.
    orders = Order.objects.filter(
        user=request.user.username,
        complete=True,
    ).exclude(order_status='Order Canceled').order_by('-date_ordered')

    return render(request, 'orders.html', {
        'orders': orders,
        'allowed_cancel_statuses': ['Order Pending', 'Order Dispatched'],
    })


@login_required
def delete_order(request, order_id):
    order = get_object_or_404(
        Order,
        id=order_id,
        user=request.user.username
    )

    if request.method == 'POST':
        order.order_status = 'Order Canceled'
        order.complete = True
        order.save()

        OrderItem.objects.filter(order=order).delete()
        ShippingAddress.objects.filter(order=order).delete()

        messages.success(request, 'Order canceled successfully')
        return redirect('order')

    return render(request, 'order.html', {'order': order})


# -------------------------
# PAYMENT
# -------------------------

def send_order_confirmation_email(order, payment_method, recipient_email):
    """
    Send a plain-text order confirmation email to the customer.
    Wrapped in try/except — a mail failure never blocks order completion.
    """
    if not recipient_email:
        return

    items = order.orderitem_set.select_related('Book_name').all()
    item_lines = '\n'.join(
        f"  • {item.Book_name.Book_name}  x{item.quantity}  —  Rs. {item.Book_name.discounted_price * item.quantity}"
        for item in items if item.Book_name
    ) or '  (no items)'

    body = (
        f"Hi {order.user},\n\n"
        f"Your order has been confirmed! Here's a summary:\n\n"
        f"{'─' * 40}\n"
        f"Order ID   : #{order.user_order_number}\n"
        f"Payment    : {payment_method}\n"
        f"{'─' * 40}\n\n"
        f"Books Ordered:\n{item_lines}\n\n"
        f"{'─' * 40}\n"
        f"Order Total: Rs. {order.get_cart_total}\n"
        f"{'─' * 40}\n\n"
        f"Your books will be delivered to your address shortly.\n\n"
        f"Thank you for choosing BookLoop!\n\n"
        f"— The BookLoop Team\n"
    )

    try:
        send_mail(
            subject="Order Confirmed – BookLoop 📚",
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient_email],
            fail_silently=False,
        )
        print(f"[EMAIL] Confirmation sent to {recipient_email} for order #{order.user_order_number}")
    except Exception as exc:
        print(f"[EMAIL] Failed to send confirmation (order #{order.user_order_number}): {exc}")


def _assign_order_number(order):
    """Assign the next sequential per-user order number if not already set."""
    if not order.user_order_number:
        last = (
            Order.objects
            .filter(user=order.user, complete=True, user_order_number__isnull=False)
            .exclude(id=order.id)
            .order_by('-user_order_number')
            .first()
        )
        order.user_order_number = (last.user_order_number + 1) if last else 1


def _notify_admin_new_order(order, payment_method):
    """Send a plain-text admin alert when an order is placed successfully."""
    try:
        admin_email = settings.ADMIN_EMAIL
        if not admin_email:
            return
        items = order.orderitem_set.select_related('Book_name').all()
        item_lines = '\n'.join(
            f"  • {item.Book_name.Book_name}  x{item.quantity}  —  Rs. {item.Book_name.discounted_price * item.quantity}"
            for item in items if item.Book_name
        ) or '  (no items)'
        send_mail(
            subject=f'[BookLoop] New order #{order.user_order_number} by {order.user}',
            message=(
                f'A new order has been placed on BookLoop.\n\n'
                f'Order #  : {order.user_order_number}\n'
                f'Customer : {order.user}\n'
                f'Payment  : {payment_method}\n'
                f'Total    : Rs. {order.get_cart_total}\n\n'
                f'Items:\n{item_lines}\n'
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[admin_email],
            fail_silently=True,
        )
    except Exception:
        pass


def ProcessOrder(request):
    transaction_id = datetime.datetime.now().timestamp()
    data = json.loads(request.body)

    # ── Server-side email validation ──────────────────────────────────────────
    shipping            = data.get('shipping', {})
    email_input         = (shipping.get('email') or '').strip()
    buy_now_product_id  = data.get('buy_now_product_id')

    if email_input:
        try:
            validate_email(email_input)
        except ValidationError:
            return JsonResponse({'error': 'Please enter a valid email address.'}, status=400)

    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Login required.'}, status=401)

    session_id = request.session.session_key

    if buy_now_product_id:
        # ── Buy-Now path: isolate ONLY this product into its own order ────────
        cart_order = _get_or_create_active_order(request.user.username)
        buy_now_item = cart_order.orderitem_set.filter(
            Book_name_id=buy_now_product_id
        ).first()
        if not buy_now_item:
            return JsonResponse({'error': 'Item not found in cart.'}, status=400)

        # Create a fresh, standalone order for the single product
        order = Order.objects.create(
            user=request.user.username,
            complete=True,
            transaction_id=transaction_id,
            order_status='Order Pending',
        )
        _assign_order_number(order)
        order.save()

        # Relocate the item from the cart to the buy-now order
        buy_now_item.order = order
        buy_now_item.save()

        # Track the purchase for AI recommendations
        if buy_now_item.Book_name:
            track_purchase(request.user, buy_now_item.Book_name, session_id)

    else:
        # ── Normal cart checkout: complete the entire cart order ──────────────
        order = _get_or_create_active_order(request.user.username)
        order.transaction_id = transaction_id
        order.complete        = True
        order.order_status    = 'Order Pending'
        _assign_order_number(order)
        order.save()

        for item in order.orderitem_set.all():
            if item.Book_name:
                track_purchase(request.user, item.Book_name, session_id)

    # ── Shipping address ──────────────────────────────────────────────────────
    if not ShippingAddress.objects.filter(order=order).exists():
        if shipping.get('address'):
            ShippingAddress.objects.create(
                user=request.user.username,
                order=order,
                address=shipping.get('address', ''),
                city=shipping.get('city', 'Kathmandu'),
                ward_no=shipping.get('ward_no', 0),
                email=email_input,
                phone=shipping.get('phone', 0),
            )

    # ── Order confirmation email ──────────────────────────────────────────────
    send_order_confirmation_email(order, 'Cash on Delivery', email_input)
    _notify_admin_new_order(order, 'Cash on Delivery')

    return JsonResponse('Order processed', safe=False)



# ---------------------------------------------------------------------------
# Khalti Payment Integration (v2 ePay API)
# ---------------------------------------------------------------------------

_KHALTI_INITIATE_URL = "https://a.khalti.com/api/v2/epayment/initiate/"
_KHALTI_LOOKUP_URL   = "https://a.khalti.com/api/v2/epayment/lookup/"


def khalti_initiate_payment(request):
    """
    POST /khalti/initiate/

    Called by the checkout page when the user chooses Khalti.
    Saves shipping info, calls Khalti API server-side (secret key never
    sent to the browser), and returns the hosted payment URL.

    Returns JSON: {"payment_url": "https://pay.khalti.com/?pidx=..."}
    """
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    if not request.user.is_authenticated:
        return JsonResponse({"error": "Login required"}, status=401)

    try:
        data     = json.loads(request.body)
        shipping = data.get("shipping", {})
        total_rs = float(data.get("total", 0))
        buy_now_product_id = data.get("buy_now_product_id")
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"error": "Invalid request body"}, status=400)

    # Server-side email validation
    email_input = (shipping.get("email") or "").strip()
    if email_input:
        try:
            validate_email(email_input)
        except ValidationError:
            return JsonResponse({"error": "Please enter a valid email address."}, status=400)

    # Khalti requires amount in paisa (1 Rs = 100 paisa), minimum 10 Rs
    amount_paisa = int(total_rs * 100)
    if amount_paisa < 1000:
        return JsonResponse({"error": "Minimum order amount is Rs 10"}, status=400)

    if buy_now_product_id:
        # ── Buy-Now path: isolate ONLY this product into its own order ────────
        cart_order = _get_or_create_active_order(request.user.username)
        buy_now_item = cart_order.orderitem_set.filter(
            Book_name_id=buy_now_product_id
        ).first()
        if not buy_now_item:
            return JsonResponse({"error": "Item not found in cart."}, status=400)

        # Create a fresh pending order for the single product only
        order = Order.objects.create(
            user=request.user.username,
            complete=False,
            order_status='Order Pending',
            payment_method="Khalti",
        )
        buy_now_item.order = order
        buy_now_item.save()
    else:
        # ── Normal cart path: use the entire cart order ───────────────────────
        order = _get_or_create_active_order(request.user.username)
        order.payment_method = "Khalti"
        order.save(update_fields=["payment_method"])

    # Persist shipping before redirecting — verification won't have form data
    if not ShippingAddress.objects.filter(order=order).exists():
        if shipping.get("address"):
            ShippingAddress.objects.create(
                user=request.user.username,
                order=order,
                address=shipping.get("address", ""),
                city=shipping.get("city", "Kathmandu"),
                ward_no=int(shipping.get("ward_no") or 0),
                email=shipping.get("email", ""),
                phone=int(shipping.get("phone") or 0),
            )

    return_url  = request.build_absolute_uri("/khalti/verify/")
    website_url = request.build_absolute_uri("/")

    payload = {
        "return_url":           return_url,
        "website_url":          website_url,
        "amount":               amount_paisa,
        "purchase_order_id":    str(order.id),
        "purchase_order_name":  f"BookLoop Order #{order.id}",
        "customer_info": {
            "name":  request.user.get_full_name() or request.user.username,
            "email": shipping.get("email") or getattr(request.user, "email", ""),
            "phone": str(shipping.get("phone", "")),
        },
    }

    try:
        resp = requests.post(
            _KHALTI_INITIATE_URL,
            json=payload,
            headers={
                "Authorization": f"Key {settings.KHALTI_SECRET_KEY}",
                "Content-Type":  "application/json",
            },
            timeout=30,
        )
        resp.raise_for_status()
        khalti_data = resp.json()
    except requests.exceptions.HTTPError as exc:
        return JsonResponse(
            {"error": f"Khalti error: {exc.response.text[:200]}"},
            status=502,
        )
    except requests.exceptions.RequestException as exc:
        return JsonResponse({"error": f"Could not reach Khalti: {exc}"}, status=502)

    # Store pidx so we can look it up when Khalti redirects back
    order.transaction_id = khalti_data["pidx"]
    order.save(update_fields=["transaction_id"])

    return JsonResponse({"payment_url": khalti_data["payment_url"]})


def khalti_verify_payment(request):
    """
    GET /khalti/verify/

    Khalti redirects here after the user pays (or cancels).
    Query params: pidx, status, transaction_id, amount, mobile,
                  purchase_order_id, purchase_order_name

    Verifies with Khalti lookup API before marking the order complete.
    """
    pidx   = request.GET.get("pidx", "").strip()

    if not pidx:
        messages.error(request, "Payment verification failed — no token received.")
        return redirect("checkout")

    # Find the pending order by the pidx we stored during initiation
    try:
        order = Order.objects.get(transaction_id=pidx, complete=False)
    except Order.DoesNotExist:
        messages.error(request, "Order not found or already processed.")
        return redirect("order")

    # Verify with Khalti — never trust the client-side redirect alone
    try:
        resp = requests.post(
            _KHALTI_LOOKUP_URL,
            json={"pidx": pidx},
            headers={
                "Authorization": f"Key {settings.KHALTI_SECRET_KEY}",
                "Content-Type":  "application/json",
            },
            timeout=30,
        )
        resp.raise_for_status()
        khalti_data = resp.json()
    except requests.exceptions.RequestException:
        messages.error(request, "Could not verify payment with Khalti. Contact support.")
        return redirect("checkout")

    if khalti_data.get("status") != "Completed":
        messages.error(
            request,
            f"Payment {khalti_data.get('status', 'failed')}. Please try again.",
        )
        return redirect("checkout")

    # Payment confirmed — finalise the order
    order.complete      = True
    order.order_status  = "Order Pending"

    if not order.user_order_number:
        last = (
            Order.objects
            .filter(user=order.user, complete=True, user_order_number__isnull=False)
            .order_by("-user_order_number")
            .first()
        )
        order.user_order_number = (last.user_order_number + 1) if last else 1

    order.save()

    # Track purchases for AI recommendations
    session_id = request.session.session_key
    for item in order.orderitem_set.select_related("Book_name").all():
        if item.Book_name:
            track_purchase(request.user, item.Book_name, session_id)

    # Send order confirmation email using shipping address email
    shipping_addr = ShippingAddress.objects.filter(order=order).first()
    recipient     = shipping_addr.email if shipping_addr else ''
    send_order_confirmation_email(order, 'Khalti', recipient)
    _notify_admin_new_order(order, 'Khalti')

    from django.urls import reverse
    success_url = (
        reverse("order")
        + f"?khalti_success=1&order_no={order.user_order_number}&amount={khalti_data.get('total_amount', 0)}"
    )
    return redirect(success_url)
