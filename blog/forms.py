import nh3
from django import forms
from taggit.forms import TagWidget

from .models import Post, Comment


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
            "seo_title",
            "seo_description",
        ]

        widgets = {
            "title": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Enter post title"
            }),

            "category": forms.Select(attrs={
                "class": "form-select"
            }),

            # CKEditor provides its own widget — do NOT override it
            "excerpt": forms.Textarea(attrs={
                "class": "form-control",
                "rows": 3,
                "placeholder": "Short summary of the post"
            }),

            "featured_image": forms.ClearableFileInput(attrs={
                "class": "form-control"
            }),

            "tags": TagWidget(attrs={
                "class": "form-control",
                "placeholder": "Comma-separated tags"
            }),

            "seo_title": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "SEO title (optional)"
            }),

            "seo_description": forms.Textarea(attrs={
                "class": "form-control",
                "rows": 3,
                "placeholder": "SEO description (optional)"
            }),
        }

    def clean_title(self):
        title = self.cleaned_data.get("title")
        if len(title) < 5:
            raise forms.ValidationError("Title must be at least 5 characters long.")
        return title

    def clean_content(self):
        # CKEditor's sanitization runs client-side only, so a malicious
        # request bypassing the browser could submit raw <script>/on*= HTML.
        # Sanitize server-side before it's ever stored or rendered with |safe.
        content = self.cleaned_data.get("content", "")
        return nh3.clean(content)


class CommentForm(forms.ModelForm):

    class Meta:
        model = Comment
        fields = ["content"]
        widgets = {
            "content": forms.Textarea(attrs={
                "class": "form-control ig-comment-input",
                "rows": 1,
                "placeholder": "Add a comment..."
            })
        }
