from django.core.management import call_command
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase, Client
from django.urls import reverse

from blog.models import Category, Post, Bookmark
from blog.services.comments import create_comment
from blog.forms import CommentForm

User = get_user_model()


class InteractionsBaseTestCase(TestCase):

    def setUp(self):
        self.client = Client()

        call_command("setup_roles")

        self.author = User.objects.create_user(
            username="author",
            email="author@test.com",
            password="Password123!",
        )
        self.author.groups.add(Group.objects.get(name="Author"))

        self.reader = User.objects.create_user(
            username="reader",
            email="reader@test.com",
            password="Password123!",
        )
        self.reader.groups.add(Group.objects.get(name="Reader"))

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


class LikePostViewTests(InteractionsBaseTestCase):

    def test_like_requires_login(self):
        response = self.client.post(
            reverse("like_post", kwargs={"slug": self.published_post.slug})
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response.url)

    def test_like_requires_post_method(self):
        self.client.login(username="reader", password="Password123!")
        response = self.client.get(
            reverse("like_post", kwargs={"slug": self.published_post.slug})
        )
        self.assertEqual(response.status_code, 405)

    def test_like_unpublished_post_forbidden_for_non_author(self):
        self.client.login(username="reader", password="Password123!")
        response = self.client.post(
            reverse("like_post", kwargs={"slug": self.draft_post.slug})
        )
        self.assertEqual(response.status_code, 403)

    def test_like_unpublished_post_allowed_for_author(self):
        self.client.login(username="author", password="Password123!")
        response = self.client.post(
            reverse("like_post", kwargs={"slug": self.draft_post.slug})
        )
        self.assertEqual(response.status_code, 200)

    def test_like_post_adds_like(self):
        self.client.login(username="reader", password="Password123!")
        response = self.client.post(
            reverse("like_post", kwargs={"slug": self.published_post.slug})
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(self.reader, self.published_post.likes.all())

    def test_like_post_toggle_removes_like(self):
        self.client.login(username="reader", password="Password123!")
        url = reverse("like_post", kwargs={"slug": self.published_post.slug})

        self.client.post(url)
        self.assertIn(self.reader, self.published_post.likes.all())

        self.client.post(url)
        self.published_post.refresh_from_db()
        self.assertNotIn(self.reader, self.published_post.likes.all())

    def test_like_missing_post_404(self):
        self.client.login(username="reader", password="Password123!")
        response = self.client.post(
            reverse("like_post", kwargs={"slug": "does-not-exist"})
        )
        self.assertEqual(response.status_code, 404)


class BookmarkPostViewTests(InteractionsBaseTestCase):

    def test_bookmark_requires_login(self):
        response = self.client.post(
            reverse("bookmark_post", kwargs={"slug": self.published_post.slug})
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response.url)

    def test_bookmark_unpublished_post_forbidden_for_non_author(self):
        self.client.login(username="reader", password="Password123!")
        response = self.client.post(
            reverse("bookmark_post", kwargs={"slug": self.draft_post.slug})
        )
        self.assertEqual(response.status_code, 403)

    def test_bookmark_post_creates_bookmark(self):
        self.client.login(username="reader", password="Password123!")
        response = self.client.post(
            reverse("bookmark_post", kwargs={"slug": self.published_post.slug})
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            Bookmark.objects.filter(user=self.reader, post=self.published_post).exists()
        )

    def test_bookmark_post_toggle_removes_bookmark(self):
        self.client.login(username="reader", password="Password123!")
        url = reverse("bookmark_post", kwargs={"slug": self.published_post.slug})

        self.client.post(url)
        self.assertTrue(
            Bookmark.objects.filter(user=self.reader, post=self.published_post).exists()
        )

        self.client.post(url)
        self.assertFalse(
            Bookmark.objects.filter(user=self.reader, post=self.published_post).exists()
        )


class CreateCommentServiceTests(InteractionsBaseTestCase):

    def test_create_comment_sets_user_and_post_and_saves(self):
        form = CommentForm(data={"content": "Nice goal!"})
        self.assertTrue(form.is_valid())

        comment = create_comment(post=self.published_post, user=self.reader, form=form)

        self.assertEqual(comment.post, self.published_post)
        self.assertEqual(comment.user, self.reader)
        self.assertEqual(comment.content, "Nice goal!")
        self.assertIsNotNone(comment.pk)
        self.assertIn(comment, self.published_post.comments.all())

    def test_post_detail_post_creates_comment_via_service(self):
        self.client.login(username="reader", password="Password123!")
        response = self.client.post(
            reverse("post_detail", kwargs={"slug": self.published_post.slug}),
            {"content": "Great win!"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            self.published_post.comments.filter(content="Great win!", user=self.reader).exists()
        )

    def test_post_detail_post_unauthenticated_redirects_to_login(self):
        response = self.client.post(
            reverse("post_detail", kwargs={"slug": self.published_post.slug}),
            {"content": "Anonymous comment"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response.url)
        self.assertFalse(
            self.published_post.comments.filter(content="Anonymous comment").exists()
        )
