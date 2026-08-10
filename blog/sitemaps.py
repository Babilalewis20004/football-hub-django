from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from .models import Category, Post


class PostSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.8

    def items(self):
        return Post.objects.filter(is_published=True).order_by("-created_at")

    def lastmod(self, post):
        return post.updated_at


class CategorySitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.5

    def items(self):
        return Category.objects.all()

    def location(self, category):
        return reverse("category_posts", kwargs={"slug": category.slug})


class StaticViewSitemap(Sitemap):
    changefreq = "monthly"
    priority = 0.3

    def items(self):
        return [
            "home",
            "about_us",
            "contact_us",
            "privacy_policy",
            "terms_of_use",
            "cookies",
            "careers",
        ]

    def location(self, name):
        return reverse(name)
