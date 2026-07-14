from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import CustomUser


class RegisterForm(UserCreationForm):

    email = forms.EmailField()

    class Meta:
        model = CustomUser

        fields = (
            'username',
            'email',
            'password1',
            'password2'
        )


class ProfileUpdateForm(forms.ModelForm):

    class Meta:
        model = CustomUser

        fields = (
            'avatar',
            'bio',
            'favorite_team'
        )
        