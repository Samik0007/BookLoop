# forms.py
from django import forms

from .models import Product


class BookSearchForm(forms.Form):
    search_query = forms.CharField(label="Search", max_length=100)


class SwapBookForm(forms.ModelForm):
    """Form for users to add a book to the swap list.

    Uses the Product model but only exposes the fields that are
    relevant for student-to-student swaps.
    """

    condition = forms.ChoiceField(
        required=False,
        choices=(
            ("", "Select condition"),
            ("New", "New"),
            ("Like New", "Like New"),
            ("Good", "Good"),
            ("Fair", "Fair"),
            ("Used", "Used"),
        ),
        widget=forms.Select(
            attrs={
                "class": "form-select mb-3",
            }
        ),
    )

    class Meta:
        model = Product
        # Note: Book_name is the title field on Product.
        fields = [
            "Book_name",
            "Author",
            "condition",
            "location",
            "contact_email",
            "image",
            "description",
            "swap_preference",
        ]
        labels = {
            "Book_name": "Book Name",
            "Author": "Author",
            "condition": "Book Condition",
            "location": "Location",
            "contact_email": "Contact Email",
            "image": "Book Image",
            "description": "Description",
            "swap_preference": "Swap Preference",
        }
        widgets = {
            "Book_name": forms.TextInput(
                attrs={
                    "class": "form-control mb-3",
                    "placeholder": "e.g. The Hobbit",
                }
            ),
            "Author": forms.TextInput(
                attrs={
                    "class": "form-control mb-3",
                    "placeholder": "e.g. J.R.R. Tolkien",
                }
            ),
            "location": forms.TextInput(
                attrs={
                    "class": "form-control mb-3",
                    "placeholder": "e.g. Kathmandu, Baneshwor",
                }
            ),
            "contact_email": forms.EmailInput(
                attrs={
                    "class": "form-control mb-3",
                    "placeholder": "you@example.com",
                }
            ),
            "image": forms.ClearableFileInput(
                attrs={
                    "class": "form-control mb-3",
                    "placeholder": "Upload book cover",
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "form-control mb-3",
                    "rows": 3,
                    "placeholder": "Add short details about this copy.",
                }
            ),
            "swap_preference": forms.Textarea(
                attrs={
                    "class": "form-control mb-3",
                    "rows": 3,
                    "placeholder": "Books/genres you want in exchange",
                }
            ),
        }





