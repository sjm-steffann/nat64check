from django import forms
from django.forms.fields import URLField, BooleanField


class URLForm(forms.Form):
    url = URLField(widget=forms.URLInput(attrs={'title': 'URL',
                                                'placeholder': 'http://www.example.com/'}),
                   required=True)
    force_new = BooleanField(required=False)
