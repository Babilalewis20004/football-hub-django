from django.db import models
from django.contrib.auth.models import AbstractUser


class CustomUser(AbstractUser):
    bio = models.TextField(
        blank=True,
        null=True
    )

    avatar = models.ImageField(
        upload_to='avatars/',
        default='avatars/default.jpg',
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


class LoginAttempt(models.Model):
    """
    Audit trail of login attempts, also used to derive account lockout
    state. Stores the raw submitted username (not a FK) so attempts against
    usernames that don't map to a real account are recorded and counted the
    same way as attempts against real ones - this keeps the lockout
    response indistinguishable regardless of whether the account exists,
    which avoids turning "account locked" into a username-enumeration
    oracle.
    """

    username = models.CharField(max_length=150, db_index=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    successful = models.BooleanField(default=False)
    reason = models.CharField(max_length=32, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-timestamp"]

    def __str__(self):
        status = "success" if self.successful else "failed"
        return f"{self.username} - {status} @ {self.timestamp:%Y-%m-%d %H:%M}"

