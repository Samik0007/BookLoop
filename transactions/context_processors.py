from django.db.models import Sum

from books.models import OrderItem


def cart_item_count(request):
    """Provide a global cart count for the navbar.

    The app stores orders by username (Order.user is a CharField), so we compute
    the active cart item quantity via a single aggregate query.
    """

    if not request.user.is_authenticated:
        return {"cart_count": 0, "cartItems": 0}

    total = (
        OrderItem.objects.filter(
            order__user=request.user.username,
            order__complete=False,
        ).aggregate(total=Sum("quantity"))
    ).get("total")

    cart_count = int(total or 0)
    return {"cart_count": cart_count, "cartItems": cart_count}
