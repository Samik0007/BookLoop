from django.db import models
from django.utils import timezone
from django.conf import settings

from decimal import Decimal
import requests
from cloudinary.models import CloudinaryField
from cloudinary.uploader import upload as cloudinary_upload

# -------------------------
# CHOICES
# -------------------------

ORDER_STATUS = (
    ("Order Received", "Order Received"),
    ("Order Processing", "Order Processing"),
    ("On the way", "On the way"),
    ("Order Completed", "Order Completed"),
    ("Order Canceled", "Order Canceled"),
)

METHOD = (
    ("Cash On Delivery", "Cash On Delivery"),
    ("Khalti Pay", "Khalti Pay"),
)

LISTING_CHOICES = (
    ("sell", "Sell"),
    ("swap", "Swap"),
    ("donate", "Donate"),
)

LISTING_STATUS = (
    ("pending", "Pending"),
    ("approved", "Approved"),
    ("rejected", "Rejected"),
    ("archived", "Archived"),
)

# -------------------------
# MODELS
# -------------------------

class Product(models.Model):
    Book_name = models.CharField(max_length=50)
    Author = models.CharField(max_length=50, default="")
    genre = models.CharField(max_length=300)
    description = models.CharField(max_length=1000, default="")
    price = models.IntegerField(default=0)
    pub_date = models.DateField(default=timezone.now)
    quantity = models.PositiveBigIntegerField(default=1)
    # Optional seller for peer-to-peer listings (swaps/donations)
    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="products",
    )
    listing_type = models.CharField(
        max_length=10,
        choices=LISTING_CHOICES,
        default="sell",
    )
    listing_status = models.CharField(
        max_length=20,
        choices=LISTING_STATUS,
        default="approved",
    )
    # If listing_type is 'swap', what book or genre does the seller want?
    swap_preference = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Title or genre of the book you want in exchange.",
    )
    condition = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text=(
            "Physical condition of the book for swapping "
            "(e.g. New, Like New, Good, Heavily Used)."
        ),
    )
    location = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="City or neighborhood for the swap",
    )
    contact_email = models.EmailField(
        blank=True,
        null=True,
        help_text="Email for other users to contact you for swapping",
    )
    # Stored in Cloudinary; public ID is managed by Cloudinary and is unique
    image = CloudinaryField("image", folder="bookloop_covers", null=True, blank=True)
    sequence = models.IntegerField(default=0)
    # Total number of times this product has been viewed
    views = models.PositiveIntegerField(default=0)

    def __str__(self):
        return self.Book_name

    def save(self, *args, **kwargs):
        """Override save to auto-fetch a cover into Cloudinary when missing.

        Behaviour:
        - If ``self.image`` is empty and this save is not part of a manual
          cleanup (e.g. ``update_fields=['image']``), try to fetch a cover
          from the Open Library API using the book's title (Book_name).
        - If a cover is found, upload the image URL directly to Cloudinary
          and assign the resulting ``public_id`` to ``self.image``.
        - All external calls are wrapped in try/except with a short timeout,
          so failures never block saving the Product.
        """

        update_fields = kwargs.get("update_fields")
        # Skip auto-fetch if this save explicitly targets the image field
        # (e.g. during a bulk cleanup command).
        skip_auto_fetch = update_fields is not None and "image" in update_fields

        if not skip_auto_fetch and not self.image:
            try:
                title = (self.Book_name or "").strip()
                if title:
                    response = requests.get(
                        "https://openlibrary.org/search.json",
                        params={"title": title},
                        timeout=5,
                    )
                    response.raise_for_status()
                    data = response.json() or {}
                    docs = data.get("docs") or []

                    cover_id = None
                    for doc in docs:
                        cover_i = doc.get("cover_i")
                        if cover_i:
                            cover_id = cover_i
                            break

                    if cover_id:
                        image_url = f"https://covers.openlibrary.org/b/id/{cover_id}-L.jpg"
                        upload_result = cloudinary_upload(
                            image_url,
                            folder="bookloop_covers",
                        )
                        public_id = upload_result.get("public_id") if isinstance(upload_result, dict) else None
                        if public_id:
                            self.image = public_id
            except Exception:
                # Fail quietly – never block saving due to network/API issues.
                pass

        super().save(*args, **kwargs)

    @property
    def imageURL(self):
        try:
            return self.image.url
        except:
            return ""

    @property
    def display_price(self) -> Decimal:
        """Return the effective display price.

        Donations are always shown as 0, while other listing types
        reuse the dynamic discounted price logic.
        """

        if self.listing_type == "donate":
            return Decimal("0.00")
        return self.discounted_price

    @property
    def discounted_price(self) -> Decimal:
        """Return a dynamic 10% discounted price without changing base price.

        The underlying ``price`` field remains the source of truth in the
        database. This property is safe for business logic and can be used
        directly in templates.
        """

        return round(Decimal(self.price) * Decimal("0.90"), 2)


class Order(models.Model):
    user = models.CharField(max_length=20, null=True)
    date_ordered = models.DateTimeField(auto_now_add=True)
    complete = models.BooleanField(default=False)
    payment_method = models.CharField(max_length=20, choices=METHOD, default="Cash On Delivery")
    order_status = models.CharField(max_length=50, choices=ORDER_STATUS, default="Order Received")
    transaction_id = models.CharField(max_length=200, null=True)

    def __str__(self):
        return str(self.id)

    @property
    def get_cart_total(self):
        items = self.orderitem_set.all()
        return sum([item.get_total for item in items])

    @property
    def get_cart_items(self):
        items = self.orderitem_set.all()
        return sum([item.quantity for item in items])


class OrderItem(models.Model):
    Book_name = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True)
    order = models.ForeignKey(Order, on_delete=models.SET_NULL, null=True)
    quantity = models.IntegerField(default=0)
    date_added = models.DateTimeField(auto_now_add=True)

    @property
    def get_total(self):
        return self.Book_name.price * self.quantity


class ShippingAddress(models.Model):
    CITY_CHOICES = (
        ('Kathmandu', 'Kathmandu'),
        ('Bhaktapur', 'Bhaktapur'),
        ('Lalitpur', 'Lalitpur'),
    )

    user = models.CharField(max_length=20, null=True)
    order = models.ForeignKey(Order, on_delete=models.SET_NULL, null=True)
    address = models.CharField(max_length=100)
    city = models.CharField(max_length=100, choices=CITY_CHOICES)
    ward_no = models.IntegerField()
    zip_code = models.IntegerField()
    phone = models.IntegerField()
    date_added = models.DateTimeField(auto_now_add=True)
    rating = models.FloatField(default=0)

    def __str__(self):
        return self.user


class Wishlist(models.Model):
    user = models.CharField(max_length=20)
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(default=timezone.now)


class UserBehavior(models.Model):
    """
    Track user interactions for AI recommendations
    """
    INTERACTION_TYPES = (
        ('view', 'Product View'),
        ('search', 'Search Query'),
        ('cart_add', 'Added to Cart'),
        ('wishlist_add', 'Added to Wishlist'),
        ('purchase', 'Purchase'),
    )
    
    user = models.CharField(max_length=255)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, null=True, blank=True)
    interaction_type = models.CharField(max_length=20, choices=INTERACTION_TYPES)
    search_query = models.CharField(max_length=255, blank=True, null=True)
    timestamp = models.DateTimeField(default=timezone.now)
    session_id = models.CharField(max_length=255, blank=True, null=True)
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['user', 'interaction_type']),
            models.Index(fields=['product', 'interaction_type']),
            models.Index(fields=['timestamp']),
        ]
    
    def __str__(self):
        return f"{self.user} - {self.interaction_type}"


class UserGenrePreference(models.Model):
    """
    Cache user's genre preferences for faster AI recommendations
    """
    user = models.CharField(max_length=255, unique=True)
    genre_scores = models.JSONField(default=dict)
    last_updated = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.user}'s Preferences"
    
    @classmethod
    def update_for_user(cls, username, genre, score_increment=1.0):
        """
        Update genre preference for a user
        """
        preference, created = cls.objects.get_or_create(user=username)
        
        if not isinstance(preference.genre_scores, dict):
            preference.genre_scores = {}
        
        current_score = preference.genre_scores.get(genre.lower(), 0)
        preference.genre_scores[genre.lower()] = current_score + score_increment
        preference.save()
        
        return preference
