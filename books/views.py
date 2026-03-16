from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponseRedirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Case, When, IntegerField, Value
import json
import datetime

from .models import Product, Order, OrderItem, Wishlist, ShippingAddress
from .recommendation_engine import get_recommendations_for_user, get_similar_books
from .user_interaction import (
    track_product_view, track_search, track_cart_addition, 
    track_wishlist_addition, track_purchase
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
    all_books = Product.objects.all().order_by('-id')
    featured_books = Product.objects.all().order_by('-sequence', '-id')[:4]
    nepali_books = Product.objects.filter(
        Q(genre__icontains='nepal') | Q(genre__icontains='nepali')
    ).order_by('-id')[:4]
    if not nepali_books.exists():
        nepali_books = Product.objects.all().order_by('-id')[4:8]
    
    if request.user.is_authenticated:
        order, _ = Order.objects.get_or_create(
            user=request.user.username, complete=False
        )
        cartItems = order.get_cart_items
        
        # Get AI recommendations
        recommended_books = get_recommendations_for_user(request.user, num_recommendations=8)
    else:
        # For anonymous users, show popular books
        from django.db.models import Count
        recommended_books = Product.objects.annotate(
            order_count=Count('orderitem', filter=Q(orderitem__order__complete=True))
        ).order_by('-order_count')[:8]
        if not recommended_books.exists():
            recommended_books = Product.objects.all()[:8]
    
    return render(request, 'index.html', {
        'cartItems': cartItems,
        'recommended_books': recommended_books,
        'all_books': all_books,
        'featured_books': featured_books,
        'nepali_books': nepali_books
    })


def about(request):
    return render(request, 'about.html')


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
    products = Product.objects.all()
    cartItems = 0

    if request.user.is_authenticated:
        order, _ = Order.objects.get_or_create(
            user=request.user.username, complete=False
        )
        cartItems = order.get_cart_items

    return render(request, 'store.html', {
        'products': products,
        'cartItems': cartItems
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

    if request.user.is_authenticated:
        order, _ = Order.objects.get_or_create(
            user=request.user.username, complete=False
        )
        cartItems = order.get_cart_items
        
        # Track product view for recommendations
        session_id = request.session.session_key
        track_product_view(request.user, product, session_id)
    
    # Get similar books using AI
    similar_books = get_similar_books(product, limit=6)

    return render(request, 'productdetails.html', {
        'data': product,
        'cartItems': cartItems,
        'similar_books': similar_books
    })


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

    return render(request, 'cart.html', {
        'items': items,
        'order': order,
        'cartItems': cartItems
    })


def checkout(request):
    items = []
    order = None
    cartItems = 0

    if request.user.is_authenticated:
        order, _ = Order.objects.get_or_create(
            user=request.user.username, complete=False
        )
        items = order.orderitem_set.all()
        cartItems = order.get_cart_items

    return render(request, 'checkout.html', {
        'items': items,
        'order': order,
        'cartItems': cartItems
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
    recommended_books = []

    if request.user.is_authenticated:
        order, _ = Order.objects.get_or_create(
            user=request.user.username, complete=False
        )
        cartItems = order.get_cart_items
        recommended_books = get_recommendations_for_user(request.user, num_recommendations=8)
    else:
        from django.db.models import Count
        recommended_books = Product.objects.annotate(
            order_count=Count('orderitem', filter=Q(orderitem__order__complete=True))
        ).order_by('-order_count')[:8]
        if not recommended_books.exists():
            recommended_books = Product.objects.all()[:8]

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
        'recommended_books': recommended_books,
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
                zip_code=data['shipping']['zip_code'],
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
