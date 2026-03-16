from django.db import models

# Create your models here.

class PreRegistration(models.Model):
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    username = models.CharField(max_length=150)
    email = models.CharField(max_length=254)
    password1 = models.CharField(max_length=200)
    password2 = models.CharField(max_length=200)
    otp = models.CharField(max_length=10, default='DEFAULT VALUE')
    created_at = models.DateTimeField(auto_now_add=True, null=True)

