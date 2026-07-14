from django import forms

from .models import Post
from .models import Comment


class PostForm(forms.ModelForm):
    class Meta:
        model = Post
        fields = [
            "title",
            "category",
            "content",
            "excerpt",
            "featured_image",
            "tags",
            "is_published",
            "seo_title",
            "seo_description",
        ]

        widgets = {
            "title": forms.TextInput(attrs={"class": "form-control"}),
            "category": forms.Select(attrs={"class": "form-control"}),
            "content": forms.Textarea(attrs={"class": "form-control"}),
            "excerpt": forms.Textarea(attrs={"class": "form-control"}),
            "featured_image": forms.ClearableFileInput(attrs={"class": "form-control"}),
            "tags": forms.TextInput(attrs={"class": "form-control"}),
            "seo_title": forms.TextInput(attrs={"class": "form-control"}),
            "seo_description": forms.Textarea(attrs={"class": "form-control"}),
        }



class CommentForm(forms.ModelForm):

    class Meta:
        model = Comment

        fields = ['content']