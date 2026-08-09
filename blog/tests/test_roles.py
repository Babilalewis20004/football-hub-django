from django.core.management import call_command
from django.test import TestCase
from django.contrib.auth.models import Group
from django.contrib.auth import get_user_model

User = get_user_model()


class RolePermissionTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        call_command("setup_roles")

    def test_editor_can_publish(self):
        editor = User.objects.create_user(
            username="editor",
            password="pass123"
        )

        editor.groups.add(Group.objects.get(name="Editor"))

        self.assertTrue(
            editor.has_perm("blog.can_publish_post")
        )

    def test_author_cannot_publish(self):
        author = User.objects.create_user(
            username="author",
            password="pass123"
        )

        author.groups.add(Group.objects.get(name="Author"))

        self.assertFalse(
            author.has_perm("blog.can_publish_post")
        )

    def test_reader_cannot_create_post(self):
        reader = User.objects.create_user(
            username="reader",
            password="pass123"
        )

        reader.groups.add(Group.objects.get(name="Reader"))

        self.assertFalse(
            reader.has_perm("blog.add_post")
        )