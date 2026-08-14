from django.core.management import call_command
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.contrib.messages import get_messages
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

        call_command("setup_roles")

        # Users

        self.author = User.objects.create_user(
            username="author",
            email="author@test.com",
            password="Password123!"
        )
        self.author.groups.add(Group.objects.get(name="Author"))

        self.reader = User.objects.create_user(
            username="reader",
            email="reader@test.com",
            password="Password123!"
        )
        self.reader.groups.add(Group.objects.get(name="Reader"))

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

        response = self.client.post(
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

        self.assertRedirects(response, reverse("author_dashboard"))

    def test_post_created(self):

        self.assertEqual(
            Post.objects.count(),
            1
        )

    def test_edit_page(self):
        # Authors can only edit their own posts while still a draft/pending —
        # once published, editing requires an Editor/Admin permission.
        self.post.is_published = False
        self.post.save()

        response = self.client.get(
            reverse(
                "post_update",
                args=[self.post.slug]
            )
        )

        self.assertEqual(response.status_code, 200)

    def test_delete_page(self):
        # Deleting posts requires the delete_post permission, which the
        # Author role does not carry by default (see setup_roles).
        delete_permission = Permission.objects.get(
            content_type__app_label="blog",
            codename="delete_post",
        )
        self.author.user_permissions.add(delete_permission)

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
        self.assertEqual(self.category.posts.count(), 1)

    def test_user_post_relationship(self):
        self.assertEqual(self.author.posts.count(), 1)

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


class PostWorkflowTransitionTests(BaseTestCase):
    """Covers the submit-for-review / withdraw / request-changes transitions
    added alongside the editor & author dashboard redesign."""

    def setUp(self):
        super().setUp()

        self.editor = User.objects.create_user(
            username="editor",
            email="editor@test.com",
            password="Password123!"
        )
        self.editor.groups.add(Group.objects.get(name="Editor"))

        self.other_author = User.objects.create_user(
            username="other_author",
            email="other_author@test.com",
            password="Password123!"
        )
        self.other_author.groups.add(Group.objects.get(name="Author"))

        self.draft = Post.objects.create(
            title="A Draft Post For Review",
            author=self.author,
            category=self.category,
            content="Draft content.",
        )

    def test_author_can_submit_draft_for_review(self):
        self.client.login(username="author", password="Password123!")
        response = self.client.post(
            reverse("post_submit_for_review", kwargs={"slug": self.draft.slug})
        )
        self.assertEqual(response.status_code, 302)
        self.draft.refresh_from_db()
        self.assertEqual(self.draft.status, "in_review")
        self.assertIsNotNone(self.draft.status_changed_at)

    def test_non_owner_cannot_submit_for_review(self):
        self.client.login(username="other_author", password="Password123!")
        response = self.client.post(
            reverse("post_submit_for_review", kwargs={"slug": self.draft.slug})
        )
        self.assertEqual(response.status_code, 403)
        self.draft.refresh_from_db()
        self.assertEqual(self.draft.status, "draft")

    def test_author_can_withdraw_from_review(self):
        self.draft.status = "in_review"
        self.draft.save()

        self.client.login(username="author", password="Password123!")
        response = self.client.post(
            reverse("post_withdraw_from_review", kwargs={"slug": self.draft.slug})
        )
        self.assertEqual(response.status_code, 302)
        self.draft.refresh_from_db()
        self.assertEqual(self.draft.status, "draft")

    def test_editor_can_request_changes_with_feedback(self):
        self.draft.status = "in_review"
        self.draft.save()

        self.client.login(username="editor", password="Password123!")
        response = self.client.post(
            reverse("post_request_changes", kwargs={"slug": self.draft.slug}),
            {"feedback": "Please add a source for the transfer fee."},
        )
        self.assertEqual(response.status_code, 302)
        self.draft.refresh_from_db()
        self.assertEqual(self.draft.status, "needs_changes")
        self.assertFalse(self.draft.is_approved)
        self.assertEqual(
            self.draft.editor_feedback,
            "Please add a source for the transfer fee."
        )

    def test_author_can_resubmit_after_needs_changes(self):
        self.draft.status = "needs_changes"
        self.draft.editor_feedback = "Fix the typo."
        self.draft.save()

        self.client.login(username="author", password="Password123!")
        response = self.client.post(
            reverse("post_submit_for_review", kwargs={"slug": self.draft.slug})
        )
        self.assertEqual(response.status_code, 302)
        self.draft.refresh_from_db()
        self.assertEqual(self.draft.status, "in_review")

    def test_editor_can_approve_in_review_post(self):
        self.draft.status = "in_review"
        self.draft.save()

        self.client.login(username="editor", password="Password123!")
        response = self.client.post(
            reverse("post_approve", kwargs={"slug": self.draft.slug})
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("editor_dashboard"))
        self.draft.refresh_from_db()
        self.assertEqual(self.draft.status, "approved")
        self.assertTrue(self.draft.is_approved)
        self.assertIsNotNone(self.draft.status_changed_at)

    def test_author_cannot_approve_post(self):
        self.draft.status = "in_review"
        self.draft.save()

        self.client.login(username="author", password="Password123!")
        response = self.client.post(
            reverse("post_approve", kwargs={"slug": self.draft.slug})
        )
        self.assertEqual(response.status_code, 403)
        self.draft.refresh_from_db()
        self.assertEqual(self.draft.status, "in_review")

    def test_anonymous_cannot_approve_post(self):
        # login_required runs before the permission check, so an
        # unauthenticated request is bounced to the login page rather
        # than a bare 403 - same as any other login-gated view.
        self.draft.status = "in_review"
        self.draft.save()

        response = self.client.post(
            reverse("post_approve", kwargs={"slug": self.draft.slug})
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)
        self.draft.refresh_from_db()
        self.assertEqual(self.draft.status, "in_review")

    def test_editor_can_publish_approved_post(self):
        self.draft.status = "approved"
        self.draft.is_approved = True
        self.draft.save()

        self.client.login(username="editor", password="Password123!")
        response = self.client.post(
            reverse("post_publish", kwargs={"slug": self.draft.slug})
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("editor_dashboard"))
        self.draft.refresh_from_db()
        self.assertEqual(self.draft.status, "published")
        self.assertTrue(self.draft.is_published)
        self.assertTrue(self.draft.is_approved)
        self.assertIsNotNone(self.draft.published_at)

    def test_author_cannot_publish_post(self):
        self.draft.status = "approved"
        self.draft.is_approved = True
        self.draft.save()

        self.client.login(username="author", password="Password123!")
        response = self.client.post(
            reverse("post_publish", kwargs={"slug": self.draft.slug})
        )
        self.assertEqual(response.status_code, 403)
        self.draft.refresh_from_db()
        self.assertEqual(self.draft.status, "approved")
        self.assertFalse(self.draft.is_published)

    def test_anonymous_cannot_publish_post(self):
        # Same login_required-before-permission ordering as approve above.
        self.draft.status = "approved"
        self.draft.is_approved = True
        self.draft.save()

        response = self.client.post(
            reverse("post_publish", kwargs={"slug": self.draft.slug})
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)
        self.draft.refresh_from_db()
        self.assertEqual(self.draft.status, "approved")
        self.assertFalse(self.draft.is_published)

    def test_author_edit_redirects_to_author_dashboard(self):
        self.client.login(username="author", password="Password123!")
        response = self.client.post(
            reverse("post_update", kwargs={"slug": self.draft.slug}),
            {
                "title": self.draft.title,
                "category": self.category.id,
                "content": "Updated draft content.",
            },
        )
        self.assertRedirects(response, reverse("author_dashboard"))

    def test_editor_edit_redirects_to_editor_dashboard(self):
        self.client.login(username="editor", password="Password123!")
        response = self.client.post(
            reverse("post_update", kwargs={"slug": self.draft.slug}),
            {
                "title": self.draft.title,
                "category": self.category.id,
                "content": "Editor-updated content.",
            },
        )
        self.assertRedirects(response, reverse("editor_dashboard"))

    def test_editor_delete_redirects_to_editor_dashboard(self):
        # Editors already carry delete_post via the Editor group (setup_roles).
        self.client.login(username="editor", password="Password123!")
        response = self.client.post(
            reverse("post_delete", kwargs={"slug": self.draft.slug})
        )
        self.assertRedirects(response, reverse("editor_dashboard"))
        self.assertFalse(Post.objects.filter(slug=self.draft.slug).exists())

        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(len(messages), 1)
        self.assertEqual(str(messages[0]), "Deleted successfully")

