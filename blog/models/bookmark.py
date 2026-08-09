from django.db import models
from django.conf import settings
from .post import Post


class Bookmark(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="bookmarks",
        db_index=True
    )

    post = models.ForeignKey(
        Post,
        on_delete=models.CASCADE,
        related_name="bookmarked_by",
        db_index=True
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "post"],
                name="unique_bookmark"
            )
        ]
        indexes = [
            models.Index(fields=["user"]),
            models.Index(fields=["post"]),
        ]

    def __str__(self):
        return f"{self.user} bookmarked {self.post}"
