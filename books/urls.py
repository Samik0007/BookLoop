from django.urls import path
from books import views

urlpatterns = [
    path('', views.index_page, name="home"),
    path('store/',views.store,name="store"),
    path('cart/',views.cart,name="cart"),
    path('checkout/',views.checkout,name="checkout"),
    path('product/<int:id>/',views.prod_detail,name="product"),
    path('product/<int:book_id>/rate/', views.RateBookView.as_view(), name='rate_book'),
    path('update_item/',views.updateItem,name="update_item"),
    path('remove_cart/<int:id>/',views.remove_from_cart,name="remove_cart"),
    path('remove_wishlist/<int:id>/',views.remove_from_wishlist,name="remove_wishlist"),
    path('process_order/',views.ProcessOrder,name='process_order'),
    path('search/', views.search, name = 'search'),
    path('wishlist',views.wishlist, name="wishlist"),
    path('add-to-wishlist',views.addtowishlist, name = "addtowishlist"),
    path('profile/',views.profile,name="profile"),
    path('about/',views.about,name="about"),
    path('order/', views.orders, name='order'),
    path('delete_order/<int:order_id>/', views.delete_order, name='delete_order'),
    path('verify_payment/', views.verify_payment, name='verify_payment'),
    path('offers/discounts/', views.DiscountOffersView.as_view(), name='discount_offers'),
    path('swap/add/', views.AddSwapBookView.as_view(), name='add_swap_book'),
    path('swaps/browse/', views.BrowseSwapBooksView.as_view(), name='browse_swaps'),
]
