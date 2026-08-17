from django.contrib.auth import get_user_model
from django.test import TestCase, Client
from django.urls import reverse

from blog.models import Category, Comment, Post

User = get_user_model()


class DeleteCommentViewTests(TestCase):

    def setUp(self):
        self.client = Client()

        self.author = User.objects.create_user(
            username="author", email="author@test.com", password="Password123!"
        )
        self.commenter = User.objects.create_user(
            username="commenter", email="commenter@test.com", password="Password123!"
        )
        self.other_user = User.objects.create_user(
            username="other", email="other@test.com", password="Password123!"
        )

        self.category = Category.objects.create(name="Premier League", slug="premier-league")
        self.post = Post.objects.create(
            title="Manchester City Win Again",
            author=self.author,
            category=self.category,
            content="Match report.",
            is_published=True,
        )
        self.comment = Comment.objects.create(
            post=self.post, user=self.commenter, content="Great win!"
        )

    def test_requires_login(self):
        response = self.client.post(reverse("delete_comment", kwargs={"pk": self.comment.pk}))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response.url)
        self.assertTrue(Comment.objects.filter(pk=self.comment.pk).exists())

    def test_get_not_allowed(self):
        self.client.login(username="commenter", password="Password123!")
        response = self.client.get(reverse("delete_comment", kwargs={"pk": self.comment.pk}))
        self.assertEqual(response.status_code, 405)

    def test_owner_can_delete_their_comment(self):
        self.client.login(username="commenter", password="Password123!")
        response = self.client.post(reverse("delete_comment", kwargs={"pk": self.comment.pk}))

        self.assertRedirects(response, reverse("post_detail", kwargs={"slug": self.post.slug}))
        self.assertFalse(Comment.objects.filter(pk=self.comment.pk).exists())

    def test_other_user_cannot_delete_comment(self):
        self.client.login(username="other", password="Password123!")
        response = self.client.post(reverse("delete_comment", kwargs={"pk": self.comment.pk}))

        self.assertRedirects(response, reverse("post_detail", kwargs={"slug": self.post.slug}))
        self.assertTrue(Comment.objects.filter(pk=self.comment.pk).exists())

    def test_missing_comment_404(self):
        self.client.login(username="commenter", password="Password123!")
        response = self.client.post(reverse("delete_comment", kwargs={"pk": 999999}))
        self.assertEqual(response.status_code, 404)

    def test_post_detail_renders_delete_button_only_for_owner(self):
        self.client.login(username="commenter", password="Password123!")
        response = self.client.get(reverse("post_detail", kwargs={"slug": self.post.slug}))
        self.assertContains(
            response, reverse("delete_comment", kwargs={"pk": self.comment.pk})
        )

        self.client.login(username="other", password="Password123!")
        response = self.client.get(reverse("post_detail", kwargs={"slug": self.post.slug}))
        self.assertNotContains(
            response, reverse("delete_comment", kwargs={"pk": self.comment.pk})
        )
