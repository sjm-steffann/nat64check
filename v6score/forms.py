from django import forms
from django.forms.fields import BooleanField, URLField


class URLForm(forms.Form):
    url = URLField(widget=forms.TextInput(attrs={'title': 'URL',
                                                 'placeholder': 'http://www.example.com/'}),
                   required=True)
    force_new = BooleanField(required=False)
