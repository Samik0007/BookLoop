# forms.py
from django import forms

class BookSearchForm(forms.Form):
    search_query = forms.CharField(label='Search', max_length=100)





