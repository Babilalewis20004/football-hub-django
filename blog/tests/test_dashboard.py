from django.contrib.auth import get_user_model
from django.test import TestCase, Client
from django.urls import reverse

from blog.models import Bookmark, Category, Post

User = get_user_model()


class SavedPostsViewTests(TestCase):

    def setUp(self):
        self.client = Client()

        self.author = User.objects.create_user(
            username="author", email="author@test.com", password="Password123!"
        )
        self.reader = User.objects.create_user(
            username="reader", email="reader@test.com", password="Password123!"
        )
        self.category = Category.objects.create(name="Premier League", slug="premier-league")
        self.post = Post.objects.create(
            title="Manchester City Win Again",
            author=self.author,
            category=self.category,
            content="Match report.",
            is_published=True,
        )

    def test_requires_login(self):
        response = self.client.get(reverse("saved_posts"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response.url)

    def test_shows_only_the_users_own_bookmarks(self):
        Bookmark.objects.create(user=self.reader, post=self.post)

        self.client.login(username="reader", password="Password123!")
        response = self.client.get(reverse("saved_posts"))

        self.assertEqual(response.status_code, 200)
        bookmarks = list(response.context["bookmarks"])
        self.assertEqual(len(bookmarks), 1)
        self.assertEqual(bookmarks[0].post, self.post)

    def test_empty_when_no_bookmarks(self):
        self.client.login(username="author", password="Password123!")
        response = self.client.get(reverse("saved_posts"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["bookmarks"]), [])
