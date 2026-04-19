# forms.py
from django import forms

from .models import Product, ShippingAddress


class BookshopProductForm(forms.ModelForm):
    """Form for bookshop owners to submit a new book listing for admin approval."""

    class Meta:
        model = Product
        fields = [
            'Book_name', 'Author', 'genre', 'description',
            'price', 'quantity', 'condition', 'image',
        ]
        widgets = {
            'Book_name':   forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Book title'}),
            'Author':      forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Author name'}),
            'genre':       forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Fiction, Academic, Self-Help'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'price':       forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'quantity':    forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'condition':   forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Good, Like New'}),
        }


class BookSearchForm(forms.Form):
    search_query = forms.CharField(label="Search", max_length=100)


class SwapBookForm(forms.ModelForm):
    """Form for users to add a book to the swap list.

    Uses the Product model but only exposes the fields that are
    relevant for student-to-student swaps.
    """

    SUBJECT_CHOICES = (
        ("", "Select subject/category"),
        ("Computing", "Computing"),
        ("Engineering", "Engineering"),
        ("Management", "Management"),
        ("Science", "Science"),
        ("Arts", "Arts"),
        ("Other", "Other"),
    )

    CONDITION_CHOICES = (
        ("", "Select condition"),
        ("Excellent", "Excellent"),
        ("Very Good", "Very Good"),
        ("Good", "Good"),
        ("Fair", "Fair"),
        ("Poor", "Poor"),
    )

    genre = forms.CharField(
        required=True,
        max_length=100,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "e.g. Fiction, Science, Self-Help, Computing…",
            }
        ),
    )

    condition = forms.ChoiceField(
        required=True,
        choices=CONDITION_CHOICES,
        widget=forms.Select(
            attrs={
                "class": "form-select",
            }
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Enforce the UX contract (some model fields are nullable, but the
        # swap listing form should collect them reliably).
        required_fields = {
            "Book_name",
            "Author",
            "genre",
            "condition",
            "description",
            "location",
            "contact_email",
            "swap_preference",
        }
        for name, field in self.fields.items():
            if name in required_fields:
                field.required = True

        # Helper text (shown under inputs)
        self.fields["Book_name"].help_text = "Enter the exact book title on the cover."
        self.fields["Author"].help_text = "Who wrote the book?"
        self.fields["genre"].help_text = "Type the subject or genre — e.g. Fiction, Computing, History."
        self.fields["condition"].help_text = "Be honest—this helps build trust."
        self.fields["image"].help_text = "Upload a clear photo (cover or front page)."
        self.fields["description"].help_text = "Short details (edition, notes, missing pages, etc.)."
        self.fields["swap_preference"].help_text = (
            "What would you like in exchange? (books, authors, subjects, genres)"
        )
        self.fields["location"].help_text = "City/neighborhood where you can meet."
        self.fields["contact_email"].help_text = "We’ll show this so interested students can reach you."

        # Placeholders
        self.fields["Book_name"].widget.attrs.setdefault("placeholder", "e.g. Data Structures and Algorithms")
        self.fields["Author"].widget.attrs.setdefault("placeholder", "e.g. Thomas H. Cormen")
        self.fields["location"].widget.attrs.setdefault("placeholder", "e.g. Kathmandu, Baneshwor")
        self.fields["contact_email"].widget.attrs.setdefault("placeholder", "you@example.com")
        self.fields["description"].widget.attrs.setdefault(
            "placeholder", "e.g. Second edition, lightly used, some highlights."
        )
        self.fields["swap_preference"].widget.attrs.setdefault(
            "placeholder", "e.g. Any Engineering/Science books, or Python/Django books."
        )

        # Bootstrap base classes
        for name, field in self.fields.items():
            widget = field.widget
            existing = (widget.attrs.get("class") or "").strip()
            base_class = "form-select" if isinstance(widget, forms.Select) else "form-control"
            if base_class not in existing.split():
                widget.attrs["class"] = (f"{existing} {base_class}").strip()

        # Bootstrap validation classes (server-side validation feedback)
        if self.is_bound:
            _ = self.errors  # triggers validation once
            for name, field in self.fields.items():
                widget = field.widget
                existing = (widget.attrs.get("class") or "").strip()
                if name in self.errors:
                    widget.attrs["class"] = f"{existing} is-invalid".strip()
                else:
                    widget.attrs["class"] = f"{existing} is-valid".strip()

    class Meta:
        model = Product
        # Note: Book_name is the title field on Product.
        fields = [
            "Book_name",
            "Author",
            "genre",
            "condition",
            "location",
            "contact_email",
            "image",
            "description",
            "swap_preference",
        ]
        labels = {
            "Book_name": "Book Title",
            "Author": "Author",
            "genre": "Subject/Category",
            "condition": "Condition",
            "location": "Location",
            "contact_email": "Contact Email",
            "image": "Book Image",
            "description": "Description",
            "swap_preference": "Books/Genres Wanted in Exchange",
        }
        widgets = {
            "Book_name": forms.TextInput(
                attrs={
                    "class": "form-control",
                }
            ),
            "Author": forms.TextInput(
                attrs={
                    "class": "form-control",
                }
            ),
            # Note: `genre` is overridden as a ChoiceField above for a constrained dropdown.
            "location": forms.TextInput(
                attrs={
                    "class": "form-control",
                }
            ),
            "contact_email": forms.EmailInput(
                attrs={
                    "class": "form-control",
                }
            ),
            "image": forms.ClearableFileInput(
                attrs={
                    "class": "form-control",
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                }
            ),
            "swap_preference": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                }
            ),
        }


class DonateBookForm(forms.ModelForm):
    """Form for users to donate a book.

    Donation listings are always free, so price and swap fields are excluded.
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
                "class": "form-select",
            }
        ),
    )

    class Meta:
        model = Product
        fields = [
            "Book_name",
            "Author",
            "condition",
            "location",
            "contact_email",
            "image",
            "description",
        ]
        labels = {
            "Book_name": "Book Title",
            "Author": "Author",
            "condition": "Book Condition",
            "location": "Pickup Location",
            "contact_email": "Contact Email",
            "image": "Book Image",
            "description": "Description",
        }
        widgets = {
            "description": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 7,
                    "placeholder": "Add details about the book — edition, condition notes, missing pages, etc.",
                }
            ),
        }


class ShippingAddressForm(forms.ModelForm):
    """Form for collecting shipping/contact information at checkout.

    Uses the updated ShippingAddress model which stores a contact email
    instead of a numeric zip code.
    """

    class Meta:
        model = ShippingAddress
        fields = ["address", "city", "ward_no", "email", "phone"]
        widgets = {
            "address": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Address.."}
            ),
            "city": forms.Select(attrs={"class": "form-select"}),
            "ward_no": forms.NumberInput(
                attrs={"class": "form-control", "placeholder": "Ward no.."}
            ),
            "email": forms.EmailInput(
                attrs={"class": "form-control", "placeholder": "Email address.."}
            ),
            "phone": forms.NumberInput(
                attrs={"class": "form-control", "placeholder": "Phone no.."}
            ),
        }
        widgets = {
            "Book_name": forms.TextInput(
                attrs={
                    "class": "form-control mb-3",
                    "placeholder": "e.g. Atomic Habits",
                }
            ),
            "Author": forms.TextInput(
                attrs={
                    "class": "form-control mb-3",
                    "placeholder": "e.g. James Clear",
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
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "form-control mb-3",
                    "rows": 3,
                    "placeholder": "Short details about the book (edition, notes, etc.)",
                }
            ),
        }





