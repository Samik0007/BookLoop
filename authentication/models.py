from django.contrib.auth.models import User
from django.db import models
from cloudinary.models import CloudinaryField


class PreRegistration(models.Model):
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    username = models.CharField(max_length=150)
    email = models.CharField(max_length=254)
    password1 = models.CharField(max_length=200)
    password2 = models.CharField(max_length=200)
    otp = models.CharField(max_length=10, default='DEFAULT VALUE')
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    role = models.CharField(max_length=20, default='student')


class UserProfile(models.Model):
    ROLE_STUDENT  = 'student'
    ROLE_BOOKSHOP = 'bookshop'
    ROLE_CHOICES  = (
        (ROLE_STUDENT,  'Student'),
        (ROLE_BOOKSHOP, 'Bookshop Owner'),
    )
    user       = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role       = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_STUDENT)
    avatar     = CloudinaryField('avatar', folder='bookloop_avatars', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} ({self.role})"

    @property
    def is_bookshop_owner(self):
        return self.role == self.ROLE_BOOKSHOP

    @property
    def avatar_url(self):
        try:
            return self.avatar.url if self.avatar else None
        except Exception:
            return None


class BookshopProfile(models.Model):
    user        = models.OneToOneField(User, on_delete=models.CASCADE, related_name='bookshop')
    shop_name   = models.CharField(max_length=200)
    location    = models.CharField(max_length=300)
    phone       = models.CharField(max_length=20, blank=True)
    description = models.TextField(blank=True, help_text='Brief description of your bookshop')
    is_verified = models.BooleanField(default=False, help_text='Admin verifies the bookshop')
    created_at  = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.shop_name} ({self.user.username})"
