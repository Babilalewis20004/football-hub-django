from django.contrib.auth import get_user_model
from django.test import TestCase, Client
from django.urls import reverse

from blog.models import Category, Post
from blog.sitemaps import CategorySitemap, PostSitemap, StaticViewSitemap

User = get_user_model()


class SitemapClassTests(TestCase):

    def setUp(self):
        self.author = User.objects.create_user(
            username="author",
            email="author@test.com",
            password="Password123!",
        )
        self.category = Category.objects.create(
            name="Premier League",
            slug="premier-league",
        )
        self.published_post = Post.objects.create(
            title="Manchester City Win Again",
            author=self.author,
            category=self.category,
            content="Match report.",
            is_published=True,
        )
        self.draft_post = Post.objects.create(
            title="Unpublished Draft Post",
            author=self.author,
            category=self.category,
            content="Not ready yet.",
            is_published=False,
        )

    def test_post_sitemap_only_includes_published(self):
        items = list(PostSitemap().items())
        self.assertIn(self.published_post, items)
        self.assertNotIn(self.draft_post, items)

    def test_post_sitemap_lastmod_is_updated_at(self):
        sitemap = PostSitemap()
        self.assertEqual(sitemap.lastmod(self.published_post), self.published_post.updated_at)

    def test_category_sitemap_includes_all_categories(self):
        items = list(CategorySitemap().items())
        self.assertIn(self.category, items)

    def test_category_sitemap_location(self):
        sitemap = CategorySitemap()
        expected = reverse("category_posts", kwargs={"slug": self.category.slug})
        self.assertEqual(sitemap.location(self.category), expected)

    def test_static_view_sitemap_items(self):
        items = StaticViewSitemap().items()
        self.assertIn("home", items)
        self.assertIn("about_us", items)

    def test_static_view_sitemap_location_resolves(self):
        sitemap = StaticViewSitemap()
        self.assertEqual(sitemap.location("home"), reverse("home"))


class SitemapViewTests(TestCase):

    def setUp(self):
        self.client = Client()
        self.author = User.objects.create_user(
            username="author",
            email="author@test.com",
            password="Password123!",
        )
        self.category = Category.objects.create(
            name="Premier League",
            slug="premier-league",
        )
        Post.objects.create(
            title="Manchester City Win Again",
            author=self.author,
            category=self.category,
            content="Match report.",
            is_published=True,
        )

    def test_sitemap_endpoint_returns_200_xml(self):
        response = self.client.get(reverse("sitemap"))
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"<urlset", response.content)
        self.assertIn(b"manchester-city-win-again", response.content)
