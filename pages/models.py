from django.conf import settings
from django.db import models


class Feedback(models.Model):
    RATING_CHOICES = [(i, str(i)) for i in range(1, 6)]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="feedback_entries",
        null=True,
        blank=True,
    )

    name = models.CharField(max_length=150, blank=True)
    email = models.EmailField(blank=True)
    rating = models.PositiveSmallIntegerField(choices=RATING_CHOICES)
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "Feedback"

    def __str__(self):
        submitter = self.name or (self.user and self.user.get_username()) or "Anonymous"
        return f"{self.rating}★ feedback from {submitter}"
