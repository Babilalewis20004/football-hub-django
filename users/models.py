# Create your models here.
from django.db import models
from django.contrib.auth.models import AbstractUser


class CustomUser(AbstractUser):

    bio = models.TextField(
        blank=True,
        null=True
    )

    avatar = models.ImageField(
        upload_to='avatars/',
        default='avatars/default.png',
        blank=True
    )

    favorite_team = models.CharField(
        max_length=100,
        blank=True
    )

    ROLE_CHOICES = (
    ('admin', 'Admin'),
    ('editor', 'Editor'),
    ('author', 'Author'),
    ('reader', 'Reader'),
    )

    role = models.CharField(
    max_length=20,
    choices=ROLE_CHOICES,
    default='reader'
    )

def __str__(self):
        return self.username
