from django.db import models
from django.conf import settings
from django.urls import reverse
from django.utils.text import slugify

from taggit.managers import TaggableManager
from ckeditor.fields import RichTextField



class Category(models.Model):

    name = models.CharField(
        max_length=100,
        unique=True
    )

    slug = models.SlugField(
        unique=True
    )

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

class Post(models.Model):

    title = models.CharField(max_length=255)

    slug = models.SlugField(unique=True, blank=True)

    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE
    )

    # REMOVE related_name='posts' because tests expect category.post_set
    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE
    )

    content = RichTextField()

    # Make image optional to prevent homepage crashes in tests
    featured_image = models.ImageField(
        upload_to='posts/',
        blank=True,
        null=True
    )

    # Add excerpt (your views use it)
    excerpt = models.TextField(blank=True)

    tags = TaggableManager(blank=True)

    # Views must be inside the class
    views = models.PositiveIntegerField(default=0)

    # Likes must NOT be duplicated
    likes = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='liked_posts',
        blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    is_published = models.BooleanField(default=True)

    seo_title = models.CharField(max_length=255, blank=True)
    seo_description = models.TextField(blank=True)

    class Meta:
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse('post_detail', kwargs={'slug': self.slug})


class Comment(models.Model):

    post = models.ForeignKey(
        'Post',
        on_delete=models.CASCADE,
        related_name='comments'
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE
    )

    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='replies'
    )

    content = models.TextField()

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return self.content[:50]

class Bookmark(models.Model):

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE
    )

    post = models.ForeignKey(
        Post,
        on_delete=models.CASCADE
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:
        unique_together = ('user', 'post')

    def __str__(self):
        return f'{self.user} bookmarked {self.post}'