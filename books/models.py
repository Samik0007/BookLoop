from django.db import models
from django.utils import timezone

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
    image = models.ImageField(upload_to='books/images', null=True, blank=True)
    sequence = models.IntegerField(default=0)

    def __str__(self):
        return self.Book_name

    @property
    def imageURL(self):
        try:
            return self.image.url
        except:
            return ""


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
