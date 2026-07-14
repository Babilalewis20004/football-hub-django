from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils.text import slugify

from blog.models import (
    Category,
    Post,
    Comment,
    Bookmark,
)

User = get_user_model()


class BaseTestCase(TestCase):
    """
    Base class used by every test.
    Creates reusable test data.
    """

    def setUp(self):

        self.client = Client()

        # Users

        self.author = User.objects.create_user(
            username="author",
            email="author@test.com",
            password="Password123!"
        )

        self.reader = User.objects.create_user(
            username="reader",
            email="reader@test.com",
            password="Password123!"
        )

        # Category

        self.category = Category.objects.create(
            name="Premier League",
            slug="premier-league"
        )

        # Post

        self.post = Post.objects.create(
            title="Manchester City Win Again",
            slug="manchester-city-win-again",
            author=self.author,
            category=self.category,
            content="Premier League match report.",
            is_published=True
        )

        # Comment

        self.comment = Comment.objects.create(
            post=self.post,
            user=self.reader,
            content="Great article!"
        )

class UserModelTests(BaseTestCase):

    def test_create_author(self):

        self.assertEqual(
            self.author.username,
            "author"
        )

    def test_create_reader(self):

        self.assertEqual(
            self.reader.username,
            "reader"
        )

    def test_user_email(self):

        self.assertEqual(
            self.author.email,
            "author@test.com"
        )

    def test_password_is_hashed(self):

        self.assertTrue(
            self.author.check_password(
                "Password123!"
            )
        )

    def test_two_users_exist(self):

        self.assertEqual(
            User.objects.count(),
            2
        )

class CategoryModelTests(BaseTestCase):

    def test_category_creation(self):

        self.assertEqual(
            self.category.name,
            "Premier League"
        )

    def test_category_slug(self):

        self.assertEqual(
            self.category.slug,
            "premier-league"
        )

    def test_category_string(self):

        self.assertEqual(
            str(self.category),
            "Premier League"
        )

    def test_category_exists(self):

        self.assertTrue(
            Category.objects.filter(
                slug="premier-league"
            ).exists()
        )

class PostModelTests(BaseTestCase):

    def test_post_creation(self):

        self.assertEqual(
            self.post.title,
            "Manchester City Win Again"
        )

    def test_post_author(self):

        self.assertEqual(
            self.post.author,
            self.author
        )

    def test_post_category(self):

        self.assertEqual(
            self.post.category,
            self.category
        )

    def test_post_slug(self):

        self.assertEqual(
            self.post.slug,
            slugify(self.post.title)
        )

    def test_post_content(self):

        self.assertIn(
            "Premier League",
            self.post.content
        )

    def test_post_published(self):

        self.assertTrue(
            self.post.is_published
        )

    def test_post_string(self):

        self.assertEqual(
            str(self.post),
            self.post.title
        )

class CommentModelTests(BaseTestCase):

    def test_comment_creation(self):

        self.assertEqual(
            self.comment.content,
            "Great article!"
        )

    def test_comment_post(self):

        self.assertEqual(
            self.comment.post,
            self.post
        )

    def test_comment_user(self):

        self.assertEqual(
            self.comment.user,
            self.reader
        )

    def test_comment_exists(self):

        self.assertEqual(
            Comment.objects.count(),
            1
        )

    def test_comment_string(self):

        self.assertIn(
            "Great",
            str(self.comment)
        )        

class AuthenticationTests(BaseTestCase):

    def test_login_success(self):

        response = self.client.login(
            username="author",
            password="Password123!"
        )

        self.assertTrue(response)

    def test_login_failure(self):

        response = self.client.login(
            username="author",
            password="wrongpassword"
        )

        self.assertFalse(response)

    def test_logout(self):

        self.client.login(
            username="author",
            password="Password123!"
        )

        response = self.client.get(
            reverse("logout")
        )

        self.assertEqual(
            response.status_code,
            302
        )

    def test_register_page_loads(self):

        response = self.client.get(
            reverse("register")
        )

        self.assertEqual(response.status_code, 200)

    def test_login_page_loads(self):

        response = self.client.get(
            reverse("login")
        )

        self.assertEqual(response.status_code, 200)

    def test_dashboard_requires_login(self):

        response = self.client.get(
            reverse("dashboard")
        )

        self.assertEqual(response.status_code, 302)

    def test_authenticated_dashboard(self):

        self.client.login(
            username="author",
            password="Password123!"
        )

        response = self.client.get(
            reverse("dashboard")
        )

        self.assertEqual(response.status_code, 200)

class ViewTests(BaseTestCase):

    def test_homepage(self):

        response = self.client.get(
            reverse("home")
        )

        self.assertEqual(response.status_code, 200)

    def test_post_detail(self):

        response = self.client.get(
            self.post.get_absolute_url()
        )

        self.assertEqual(response.status_code, 200)

    def test_category_page(self):

        response = self.client.get(
            reverse(
                "category_posts",
                args=[self.category.slug]
            )
        )

        self.assertEqual(response.status_code, 200)

    def test_search_page(self):

        response = self.client.get(
            reverse("search")
        )

        self.assertEqual(response.status_code, 200)

    def test_search_results(self):

        response = self.client.get(
            reverse("search"),
            {"q": "Manchester"}
        )

        self.assertContains(
            response,
            "Manchester"
        )

    def test_post_exists(self):

        response = self.client.get(
            self.post.get_absolute_url()
        )

        self.assertContains(
            response,
            self.post.title
        )

    def test_404(self):

        response = self.client.get(
            "/invalid-page/"
        )

        self.assertEqual(response.status_code, 404)

    def test_home_template(self):

        response = self.client.get(
            reverse("home")
        )

        self.assertTemplateUsed(
            response,
            "blog/home.html"
        )                

class CRUDTests(BaseTestCase):

    def setUp(self):

        super().setUp()

        self.client.login(
            username="author",
            password="Password123!"
        )

    def test_create_post(self):

        response = self.client.post(
            reverse("post_create"),
            {
                "title": "Chelsea News",
                "category": self.category.id,
                "content": "Latest update",
                "is_published": True,
            }
        )

        self.assertEqual(response.status_code, 302)

    def test_post_created(self):

        self.assertEqual(
            Post.objects.count(),
            1
        )

    def test_edit_page(self):

        response = self.client.get(
            reverse(
                "post_update",
                args=[self.post.slug]
            )
        )

        self.assertEqual(response.status_code, 200)

    def test_delete_page(self):

        response = self.client.get(
            reverse(
                "post_delete",
                args=[self.post.slug]
            )
        )

        self.assertEqual(response.status_code, 200)

    def test_author_owns_post(self):

        self.assertEqual(
            self.post.author,
            self.author
        )

    def test_post_has_category(self):

        self.assertEqual(
            self.post.category,
            self.category
        )

    def test_post_slug_exists(self):

        self.assertTrue(
            self.post.slug
        )

    def test_post_title(self):

        self.assertEqual(
            self.post.title,
            "Manchester City Win Again"
        )        

class BookmarkTests(BaseTestCase):

    def setUp(self):

        super().setUp()

        self.client.login(
            username="reader",
            password="Password123!"
        )

    def test_create_bookmark(self):

        Bookmark.objects.create(
            user=self.reader,
            post=self.post
        )

        self.assertEqual(
            Bookmark.objects.count(),
            1
        )

    def test_bookmark_user(self):

        bookmark = Bookmark.objects.create(
            user=self.reader,
            post=self.post
        )

        self.assertEqual(
            bookmark.user,
            self.reader
        )

    def test_bookmark_post(self):

        bookmark = Bookmark.objects.create(
            user=self.reader,
            post=self.post
        )

        self.assertEqual(
            bookmark.post,
            self.post
        )

    def test_like_post(self):

        self.post.likes.add(
            self.reader
        )

        self.assertEqual(
            self.post.likes.count(),
            1
        )

    def test_unlike_post(self):

        self.post.likes.add(self.reader)

        self.post.likes.remove(self.reader)

        self.assertEqual(
            self.post.likes.count(),
            0
        )

    def test_multiple_likes(self):

        self.post.likes.add(self.reader)

        self.post.likes.add(self.author)

        self.assertEqual(
            self.post.likes.count(),
            2
        )

class IntegrationTests(BaseTestCase):

    def test_complete_workflow(self):

        login = self.client.login(
            username="author",
            password="Password123!"
        )

        self.assertTrue(login)

        response = self.client.get(
            self.post.get_absolute_url()
        )

        self.assertEqual(response.status_code, 200)

        comment = Comment.objects.create(
            post=self.post,
            user=self.author,
            content="Integration Test"
        )

        self.assertEqual(
            comment.content,
            "Integration Test"
        )

        self.post.likes.add(
            self.author
        )

        self.assertEqual(
            self.post.likes.count(),
            1
        )

        Bookmark.objects.create(
            user=self.author,
            post=self.post
        )

        self.assertEqual(
            Bookmark.objects.count(),
            1
        )

    def test_search_integration(self):
        response = self.client.get(reverse("search"), {"q": "Manchester"})
        self.assertEqual(response.status_code, 200)

    def test_dashboard_redirect(self):
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 302)

    def test_authenticated_dashboard(self):
        self.client.login(username="author", password="Password123!")
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 200)

    def test_comment_count(self):
        self.assertEqual(self.post.comments.count(), 1)

    def test_post_relationship(self):
        self.assertEqual(self.category.post_set.count(), 1)

    def test_user_post_relationship(self):
        self.assertEqual(self.author.post_set.count(), 1)

    def test_comment_relationship(self):
        self.assertEqual(self.comment.post, self.post)

    def test_like_relationship(self):
        self.post.likes.add(self.reader)
        self.assertTrue(self.reader in self.post.likes.all())

    def test_bookmark_relationship(self):
        bookmark = Bookmark.objects.create(user=self.reader, post=self.post)
        self.assertEqual(bookmark.post, self.post)

    def test_database_integrity(self):
        self.assertEqual(Post.objects.count(), 1)              

        