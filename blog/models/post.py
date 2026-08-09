from django.db import models
from django.conf import settings
from django.urls import reverse
from django.utils.text import slugify
from django.utils.html import strip_tags

from taggit.managers import TaggableManager
from ckeditor.fields import RichTextField
from .category import Category

class Post(models.Model):
    title = models.CharField(max_length=255)
    slug = models.SlugField(unique=True, blank=True, db_index=True)

    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="posts",
        db_index=True
    )

    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name="posts",
        db_index=True
    )

    content = RichTextField()
    featured_image = models.ImageField(upload_to="posts/", blank=True, null=True)
    excerpt = models.TextField(blank=True)

    tags = TaggableManager(blank=True)

    views = models.PositiveIntegerField(default=0, db_index=True)

    likes = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name="liked_posts",
        blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Editorial workflow fields
    is_published = models.BooleanField(default=False, db_index=True)
    is_approved = models.BooleanField(default=False, db_index=True)
    status = models.CharField(
        max_length=20,
        choices=[
            ("draft", "Draft"),
            ("pending", "Pending Approval"),
            ("published", "Published"),
        ],
        default="draft",
        db_index=True,
    )

    seo_title = models.CharField(max_length=255, blank=True)
    seo_description = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["views"]),
            models.Index(fields=["author"]),
            models.Index(fields=["is_published"]),
        ]
        permissions = [
            ("can_publish_post", "Can publish posts"),
            ("can_feature_post", "Can feature posts"),
            ("can_approve_post", "Can approve posts"),
        ]

    def save(self, *args, **kwargs):
        if not self.excerpt and self.content:
            self.excerpt = strip_tags(self.content)[:200]

        if self.pk:
            title_changed = (
                Post.objects.filter(pk=self.pk).exclude(title=self.title).exists()
            )
        else:
            title_changed = True

        # Only recompute the slug on creation or when the title actually
        # changed — recomputing on every save let an already-unique slug
        # (e.g. "foo-1") get regenerated on unrelated saves (publish, approve),
        # silently reassigning it if the post it once collided with was
        # later deleted or renamed, breaking existing permalinks.
        if title_changed or not self.slug:
            base_slug = slugify(self.title)
            slug = base_slug
            counter = 1

            while Post.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1

            self.slug = slug

        super().save(*args, **kwargs)

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("post_detail", kwargs={"slug": self.slug})
