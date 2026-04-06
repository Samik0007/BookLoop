from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponseRedirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Case, When, IntegerField, Value, Count, F, Sum, Avg, ExpressionWrapper, DecimalField
from django.views.generic import ListView
from django.views.generic.edit import CreateView
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse, reverse_lazy
import json
import datetime
import random

from .models import Product, Rating, Order, OrderItem, Wishlist, ShippingAddress
from .recommendation_engine import get_recommendations_for_user, get_similar_books
from recommendations.services import get_user_recommendations
from .user_interaction import (
    track_product_view, track_search, track_cart_addition, 
    track_wishlist_addition, track_purchase
)
from .forms import DonateBookForm, SwapBookForm


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
            order, _ = Order.objects.get_or_create(
                user=self.request.user.username,
                complete=False,
            )
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
            "Thank you! Your donation is pending admin approval.",
        )
        return super().form_valid(form)

    def get_success_url(self):  # type: ignore[override]
        return reverse_lazy("home")


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


def profile(request):
    cartItems = 0
    items = []
    orders = []
    wishlist_count = 0
    total_spent = 0
    recent_orders = []

    if request.user.is_authenticated:
        order, _ = Order.objects.get_or_create(
            user=request.user.username, complete=False
        )
        items = order.orderitem_set.all()
        cartItems = order.get_cart_items
        orders = Order.objects.filter(user=request.user.username).order_by('-date_ordered')
        wishlist_count = Wishlist.objects.filter(user=request.user.username).count()
        total_spent = sum([o.get_cart_total for o in orders.filter(complete=True)])
        recent_orders = orders[:5]

    return render(request, 'profile.html', {
        'items': items,
        'cartItems': cartItems,
        'orders': orders,
        'wishlist_count': wishlist_count,
        'total_spent': total_spent,
        'recent_orders': recent_orders
    })


# -------------------------
# STORE / PRODUCTS
# -------------------------

def store(request):
    products = Product.objects.filter(listing_type="sell", listing_status="approved")
    cartItems = 0

    if request.user.is_authenticated:
        order, _ = Order.objects.get_or_create(
            user=request.user.username, complete=False
        )
        cartItems = order.get_cart_items

    # Use the optimized hybrid recommendation engine (with Redis + Celery)
    recommended_books = get_user_recommendations(request.user, limit=8)

    return render(request, 'store.html', {
        'products': products,
        'cartItems': cartItems,
        'recommended_books': recommended_books,
    })


def nepali_books_page(request):
    """Dedicated page showing all Nepali genre books sorted by popularity."""
    cartItems = 0
    if request.user.is_authenticated:
        order, _ = Order.objects.get_or_create(
            user=request.user.username, complete=False
        )
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
        order, _ = Order.objects.get_or_create(
            user=request.user.username, complete=False
        )
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

    return render(request, 'productdetails.html', {
        'data': product,
        'cartItems': cartItems,
        'similar_books': similar_books,
        'user_rating': user_rating,
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

        Rating.objects.update_or_create(
            user=request.user,
            book=book,
            defaults={"score": score},
        )

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
        order, _ = Order.objects.get_or_create(
            user=request.user.username, complete=False
        )
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
        order, _ = Order.objects.get_or_create(
            user=request.user.username, complete=False
        )
        cartItems = order.get_cart_items

        if buy_now_product_id:
            single_item = order.orderitem_set.filter(
                Book_name_id=buy_now_product_id
            ).first()
            if single_item:
                items = [single_item]
                is_buy_now = True
                buy_now_total = single_item.Book_name.price * single_item.quantity
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

    product = get_object_or_404(Product, id=productId)
    order, _ = Order.objects.get_or_create(
        user=request.user.username, complete=False
    )
    orderItem, _ = OrderItem.objects.get_or_create(
        order=order, Book_name=product
    )

    if action == 'add':
        orderItem.quantity += 1
        product.quantity -= 1
        
        # Track cart addition for AI recommendations
        session_id = request.session.session_key
        track_cart_addition(request.user, product, session_id)

    elif action == 'remove':
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
        order, _ = Order.objects.get_or_create(
            user=request.user.username, complete=False
        )
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
    Search with AI-powered result ranking
    """
    query = request.GET.get('q', '').strip()
    books = Product.objects.none()
    cartItems = 0

    if request.user.is_authenticated:
        order, _ = Order.objects.get_or_create(
            user=request.user.username, complete=False
        )
        cartItems = order.get_cart_items

    if query:
        tokens = [t for t in query.split() if t]
        base_q = (
            Q(Book_name__icontains=query) |
            Q(Author__icontains=query) |
            Q(genre__icontains=query) |
            Q(description__icontains=query)
        )
        for token in tokens:
            base_q |= (
                Q(Book_name__icontains=token) |
                Q(Author__icontains=token) |
                Q(genre__icontains=token) |
                Q(description__icontains=token)
            )

        books = Product.objects.filter(base_q).annotate(
            score=(
                Case(When(Book_name__icontains=query, then=Value(5)), default=Value(0), output_field=IntegerField()) +
                Case(When(Author__icontains=query, then=Value(4)), default=Value(0), output_field=IntegerField()) +
                Case(When(genre__icontains=query, then=Value(3)), default=Value(0), output_field=IntegerField()) +
                Case(When(description__icontains=query, then=Value(2)), default=Value(0), output_field=IntegerField())
            )
        ).order_by('-score', 'Book_name').distinct()

        if request.user.is_authenticated:
            session_id = request.session.session_key
            if not session_id:
                request.session.create()
                session_id = request.session.session_key
            track_search(request.user, query, session_id)
    else:
        books = Product.objects.all().order_by('-id')

    return render(request, 'searchbar.html', {
        'query': query,
        'books': books,
        'cartItems': cartItems,
        'result_count': books.count()
    })


# -------------------------
# ORDERS
# -------------------------

@login_required
def orders(request):
    orders = Order.objects.filter(
        user=request.user.username
    ).exclude(order_status='Order Canceled').order_by('-date_ordered')

    return render(request, 'orders.html', {
        'orders': orders,
        'allowed_cancel_statuses': ['Order Received', 'Order Processing', 'On the way']
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
        return redirect('orders')

    return render(request, 'order.html', {'order': order})


# -------------------------
# PAYMENT
# -------------------------

def ProcessOrder(request):
    transaction_id = datetime.datetime.now().timestamp()
    data = json.loads(request.body)

    if request.user.is_authenticated:
        order, _ = Order.objects.get_or_create(
            user=request.user.username, complete=False
        )

        total = float(data['form']['total'])
        order.transaction_id = transaction_id

        if total == order.get_cart_total:
            order.complete = True

        order.save()
        
        # Track purchases for AI recommendations
        session_id = request.session.session_key
        for item in order.orderitem_set.all():
            if item.Book_name:
                track_purchase(request.user, item.Book_name, session_id)

        if not order.shipping:
            ShippingAddress.objects.create(
                user=request.user.username,
                order=order,
                address=data['shipping']['address'],
                city=data['shipping']['city'],
                ward_no=data['shipping']['ward_no'],
                email=data['shipping'].get('email') or data['shipping'].get('zip_code'),
                phone=data['shipping']['phone'],
            )

    return JsonResponse('Order processed', safe=False)


import requests
from django.http import JsonResponse
import json

def verify_payment(request):
    """
    Dummy payment verification endpoint.
    Keeps URL working without breaking server.
    """

    if request.method == "POST":
        return JsonResponse({
            "status": "success",
            "message": "Payment verified (test mode)"
        })

    return JsonResponse({
        "status": "error",
        "message": "Invalid request"
    }, status=400)
