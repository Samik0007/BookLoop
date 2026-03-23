from django.urls import path

from .views import SwapMatchesView, CreateSwapRequestView


urlpatterns = [
    path("swaps/matches/", SwapMatchesView.as_view(), name="swap_matches"),
    path("swaps/request/", CreateSwapRequestView.as_view(), name="create_swap_request"),
]
