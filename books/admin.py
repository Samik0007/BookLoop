from django.contrib import admin

# Register your models here.

from .models import *

admin.site.register(Product)
admin.site.register(Order)
admin.site.register(OrderItem)
admin.site.register(ShippingAddress)
admin.site.register(Wishlist)


# Custom admin for better visualization
@admin.register(UserBehavior)
class UserBehaviorAdmin(admin.ModelAdmin):
    list_display = ('user', 'product', 'interaction_type', 'timestamp')
    list_filter = ('interaction_type', 'timestamp')
    search_fields = ('user', 'search_query')
    date_hierarchy = 'timestamp'


@admin.register(UserGenrePreference)
class UserGenrePreferenceAdmin(admin.ModelAdmin):
    list_display = ('user', 'last_updated')
    search_fields = ('user',)
    readonly_fields = ('last_updated',)


