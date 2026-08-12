from django import forms

from .models import Feedback, Subscriber


class FeedbackForm(forms.ModelForm):

    class Meta:
        model = Feedback
        fields = ["rating", "name", "email", "comment"]
        widgets = {
            "name": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Your name (optional)"
            }),
            "email": forms.EmailInput(attrs={
                "class": "form-control",
                "placeholder": "you@example.com (optional)"
            }),
            "comment": forms.Textarea(attrs={
                "class": "form-control",
                "rows": 4,
                "placeholder": "Tell us what you think, or how we can improve..."
            }),
        }


class SubscribeForm(forms.ModelForm):

    class Meta:
        model = Subscriber
        fields = ["email"]
        widgets = {
            "email": forms.EmailInput(attrs={
                "class": "form-control",
                "placeholder": "Your email",
            }),
        }
