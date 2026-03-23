from typing import Any, Dict

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import TemplateView

from books.models import Product
from .models import SwapRequest
from .services import find_swap_matches


class SwapMatchesView(LoginRequiredMixin, TemplateView):
    """Display potential swap matches for the current user."""

    template_name = "transactions/swap_matches.html"
    login_url = reverse_lazy("login")

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:  # type: ignore[override]
        context = super().get_context_data(**kwargs)
        context["matches"] = find_swap_matches(self.request.user)
        return context


class CreateSwapRequestView(LoginRequiredMixin, View):
    """Create a swap request between two books.

    Expects ``my_book_id`` and ``their_book_id`` in POST data.
    """

    login_url = reverse_lazy("login")

    def post(self, request, *args, **kwargs):  # type: ignore[override]
        my_book_id = request.POST.get("my_book_id")
        their_book_id = request.POST.get("their_book_id")

        if not my_book_id or not their_book_id:
            messages.error(request, "Invalid swap data submitted.")
            return redirect("swap_matches")

        my_book = get_object_or_404(
            Product,
            id=my_book_id,
            seller=request.user,
            listing_type="swap",
        )
        their_book = get_object_or_404(
            Product,
            id=their_book_id,
            listing_type="swap",
        )

        if their_book.seller == request.user:
            messages.error(request, "You cannot create a swap with your own listing.")
            return redirect("swap_matches")

        if their_book.seller is None:
            messages.error(request, "This listing is not associated with a student.")
            return redirect("swap_matches")

        swap_request, created = SwapRequest.objects.get_or_create(
            requester=request.user,
            receiver=their_book.seller,
            requested_book=their_book,
            offered_book=my_book,
        )

        if created:
            messages.success(request, "Swap request sent successfully.")
        else:
            messages.info(request, "You have already sent a swap request for this match.")

        return redirect("swap_matches")
