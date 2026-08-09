from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType


class Command(BaseCommand):
    help = "Create default user roles for Football Hub"

    def handle(self, *args, **kwargs):
        post_ct = ContentType.objects.get(app_label="blog", model="post")

        roles = ["Admin", "Editor", "Author", "Contributor", "Reader"]
        groups = {name: Group.objects.get_or_create(name=name)[0] for name in roles}

        admin_perms = Permission.objects.filter(content_type=post_ct)

        editor_perms = Permission.objects.filter(
            codename__in=[
                "add_post",
                "change_post",
                "delete_post",
                "view_post",
                "can_publish_post",
                "can_feature_post",
                "can_approve_post",
            ]
        )

        # NOTE: deliberately excludes "change_post" — that permission is
        # checked globally (not per-object) in post_update, so granting it
        # here would let any Author edit every other Author's posts instead
        # of only their own. Authors edit their own posts via the object-
        # level ownership check in post_update, which needs no permission.
        author_perms = Permission.objects.filter(
            codename__in=[
                "add_post",
                "view_post",
            ]
        )

        contributor_perms = Permission.objects.filter(
            codename__in=[
                "add_post",
                "view_post",
            ]
        )

        reader_perms = Permission.objects.filter(
            codename__in=[
                "view_post",
            ]
        )

        groups["Admin"].permissions.set(admin_perms)
        groups["Editor"].permissions.set(editor_perms)
        groups["Author"].permissions.set(author_perms)
        groups["Contributor"].permissions.set(contributor_perms)
        groups["Reader"].permissions.set(reader_perms)

        self.stdout.write(self.style.SUCCESS("Roles created and updated successfully."))
