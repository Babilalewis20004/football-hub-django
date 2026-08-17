from django.core.management import call_command
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase, Client
from django.urls import reverse

from blog.models import Category, Post

User = get_user_model()


class TaxonomyBaseTestCase(TestCase):

    def setUp(self):
        self.client = Client()

        call_command("setup_roles")

        self.author = User.objects.create_user(
            username="author",
            email="author@test.com",
            password="Password123!",
        )
        self.author.groups.add(Group.objects.get(name="Author"))

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
        self.published_post.tags.add("city", "football")

        self.draft_post = Post.objects.create(
            title="Unpublished Draft Post",
            author=self.author,
            category=self.category,
            content="Not ready yet.",
            is_published=False,
        )
        self.draft_post.tags.add("city")


class AuthorPostsViewTests(TaxonomyBaseTestCase):

    def test_author_posts_returns_200(self):
        response = self.client.get(
            reverse("author_posts", kwargs={"username": self.author.username})
        )
        self.assertEqual(response.status_code, 200)

    def test_author_posts_only_shows_published(self):
        response = self.client.get(
            reverse("author_posts", kwargs={"username": self.author.username})
        )
        posts = list(response.context["posts"])
        self.assertIn(self.published_post, posts)
        self.assertNotIn(self.draft_post, posts)

    def test_author_posts_missing_author_404(self):
        response = self.client.get(
            reverse("author_posts", kwargs={"username": "no-such-user"})
        )
        self.assertEqual(response.status_code, 404)

    def test_author_posts_logged_in_viewer(self):
        self.client.login(username="author", password="Password123!")
        response = self.client.get(
            reverse("author_posts", kwargs={"username": self.author.username})
        )
        self.assertEqual(response.status_code, 200)


class CategoryPostsViewTests(TaxonomyBaseTestCase):

    def test_category_posts_returns_200(self):
        response = self.client.get(
            reverse("category_posts", kwargs={"slug": self.category.slug})
        )
        self.assertEqual(response.status_code, 200)

    def test_category_posts_only_shows_published(self):
        response = self.client.get(
            reverse("category_posts", kwargs={"slug": self.category.slug})
        )
        posts = list(response.context["posts"])
        self.assertIn(self.published_post, posts)
        self.assertNotIn(self.draft_post, posts)

    def test_category_posts_missing_category_404(self):
        response = self.client.get(
            reverse("category_posts", kwargs={"slug": "no-such-category"})
        )
        self.assertEqual(response.status_code, 404)


class TagPostsViewTests(TaxonomyBaseTestCase):

    def test_tag_posts_returns_200(self):
        tag_slug = self.published_post.tags.first().slug
        response = self.client.get(reverse("tag_posts", kwargs={"slug": tag_slug}))
        self.assertEqual(response.status_code, 200)

    def test_tag_posts_only_shows_published(self):
        tag_slug = self.published_post.tags.get(name="city").slug
        response = self.client.get(reverse("tag_posts", kwargs={"slug": tag_slug}))
        posts = list(response.context["posts"])
        self.assertIn(self.published_post, posts)
        self.assertNotIn(self.draft_post, posts)

    def test_tag_posts_missing_tag_404(self):
        response = self.client.get(reverse("tag_posts", kwargs={"slug": "no-such-tag"}))
        self.assertEqual(response.status_code, 404)
