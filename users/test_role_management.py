"""
Tests for centralized role management:

- Default Reader assignment on registration, and that the public
  registration form can never be used to set a different role.
- users.management.commands.backfill_user_roles: resetting accounts with
  an unrecognized `role` to Reader, preserving valid existing roles, and
  repairing Group membership that drifted from `role`.
- Role changes made through the Django admin UI (users.admin.CustomUserAdmin):
  that `role` is the single field that drives Group membership (and so
  permissions), that changing it never leaves a user in two roles' Groups
  at once, and that the Admin role can't be granted through the ordinary
  selector.
- Privilege-escalation protections: unauthenticated/unauthorized users
  can't reach the role-management UI at all, and invalid role values are
  rejected outright.
"""
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.core.management import call_command
from django.forms import ModelMultipleChoiceField, SplitDateTimeField
from django.test import Client, TestCase
from django.urls import reverse

from django_otp import DEVICE_ID_SESSION_KEY
from django_otp.plugins.otp_totp.models import TOTPDevice

from .test_two_factor import PASSWORD, _mark_session_verified
from .tests import _solved_captcha

User = get_user_model()


def _verified_client(user):
    """
    A logged-in test Client that also satisfies the mandatory-2FA gate for
    privileged roles (admin/editor/author - see users.twofactor), so
    requests made with it aren't intercepted by
    users.middleware.TwoFactorEnforcementMiddleware before reaching the
    view under test.
    """
    device = TOTPDevice.objects.create(user=user, name="test-device", confirmed=True)
    client = Client()
    client.force_login(user)
    _mark_session_verified(client, device)
    return client


def _admin_change_form_data(form, **overrides):
    """
    Builds valid POST data for a Django-admin ModelForm from its current
    `initial` values (as `response.context["adminform"].form` would be for
    a real change-page GET), then applies `overrides` on top. Needed
    because UserAdmin's change form mixes plain fields, a couple of
    SplitDateTimeFields (last_login/date_joined), and ModelMultipleChoiceFields
    (user_permissions), each of which need their own POST-encoding.
    """
    data = {}
    for name, field in form.fields.items():
        if field.disabled:
            continue
        value = form.initial.get(name)
        if isinstance(field, SplitDateTimeField):
            if value:
                data[f"{name}_0"] = value.date().isoformat()
                data[f"{name}_1"] = value.time().isoformat()
            continue
        if isinstance(field, ModelMultipleChoiceField):
            data[name] = [obj.pk for obj in value] if value else []
            continue
        if isinstance(value, bool):
            if value:
                data[name] = "on"
            continue
        if value is None:
            continue
        data[name] = value
    data.update(overrides)
    return data


class RegistrationDefaultRoleTests(TestCase):
    def setUp(self):
        self.register_url = reverse("register")

    def _register(self, extra=None):
        data = {
            "username": "newreader",
            "email": "newreader@example.com",
            "password1": "correct-horse-battery-staple",
            "password2": "correct-horse-battery-staple",
        }
        if extra:
            data.update(extra)
        data.update(_solved_captcha())
        return self.client.post(self.register_url, data)

    def test_new_registration_defaults_to_reader(self):
        self._register()
        user = User.objects.get(username="newreader")
        self.assertEqual(user.role, "reader")

    def test_new_reader_gets_only_the_reader_group(self):
        self._register()
        user = User.objects.get(username="newreader")
        self.assertEqual(set(user.groups.values_list("name", flat=True)), {"Reader"})

    def test_registration_ignores_injected_role_field(self):
        """
        RegisterForm.Meta.fields never lists `role`, so a ModelForm simply
        ignores anything else present in POST - this proves that holds for
        every non-Reader role, not just one.
        """
        for attempted_role in ("admin", "editor", "author", "contributor"):
            with self.subTest(attempted_role=attempted_role):
                User.objects.filter(username="newreader").delete()
                self._register({"role": attempted_role})
                user = User.objects.get(username="newreader")
                self.assertEqual(user.role, "reader")


class BackfillUserRolesCommandTests(TestCase):
    """users.management.commands.backfill_user_roles"""

    def test_user_with_unrecognized_role_becomes_reader(self):
        user = User.objects.create_user(username="legacy", password=PASSWORD, role="reader")
        # Simulates pre-existing bad data (e.g. a role value from before
        # validation existed) - bypasses model validation on purpose via a
        # bulk update, the same way a stray DB migration or import might.
        User.objects.filter(pk=user.pk).update(role="")

        call_command("backfill_user_roles")

        user.refresh_from_db()
        self.assertEqual(user.role, "reader")

    def test_backfilled_reader_gets_reader_group(self):
        user = User.objects.create_user(username="legacy2", password=PASSWORD, role="reader")
        User.objects.filter(pk=user.pk).update(role="not-a-real-role")

        call_command("backfill_user_roles")

        user.refresh_from_db()
        self.assertEqual(user.role, "reader")
        self.assertEqual(set(user.groups.values_list("name", flat=True)), {"Reader"})

    def test_existing_valid_roles_are_preserved(self):
        roles = ("reader", "contributor", "editor", "author", "admin")
        for role in roles:
            User.objects.create_user(username=f"existing_{role}", password=PASSWORD, role=role)

        call_command("backfill_user_roles")

        for role in roles:
            with self.subTest(role=role):
                user = User.objects.get(username=f"existing_{role}")
                self.assertEqual(user.role, role)

    def test_backfill_repairs_group_membership_drifted_from_role(self):
        """
        Simulates an account created before the role<->Group sync signal
        existed: `role` is valid and correct, but Group membership never
        got set. The command must fix membership without touching `role`.
        """
        user = User.objects.create_user(username="drifted", password=PASSWORD, role="editor")
        user.groups.clear()

        call_command("backfill_user_roles")

        user.refresh_from_db()
        self.assertEqual(user.role, "editor")
        self.assertEqual(set(user.groups.values_list("name", flat=True)), {"Editor"})

    def test_backfill_is_idempotent(self):
        User.objects.create_user(username="stable", password=PASSWORD, role="contributor")

        call_command("backfill_user_roles")
        call_command("backfill_user_roles")

        user = User.objects.get(username="stable")
        self.assertEqual(user.role, "contributor")
        self.assertEqual(set(user.groups.values_list("name", flat=True)), {"Contributor"})


class AdminRoleAssignmentTests(TestCase):
    """
    Role changes made through the Django admin UI
    (users.admin.CustomUserAdmin), and that they take effect immediately -
    Group membership (and therefore permissions) always ends up matching
    the newly selected role, never a leftover mix of old and new.
    """

    @classmethod
    def setUpTestData(cls):
        call_command("setup_roles")

    def setUp(self):
        self.superuser = User.objects.create_superuser(
            username="siteadmin", email="siteadmin@example.com",
            password=PASSWORD, role="admin",
        )
        self.target = User.objects.create_user(
            username="target", password=PASSWORD, role="reader"
        )
        self.client = _verified_client(self.superuser)
        self.change_url = reverse("admin:users_customuser_change", args=[self.target.pk])

    def _change_role(self, new_role):
        get_response = self.client.get(self.change_url)
        data = _admin_change_form_data(get_response.context["adminform"].form, role=new_role)
        return self.client.post(self.change_url, data, follow=True)

    def _refresh_target(self):
        """
        A fresh fetch rather than `self.target.refresh_from_db()` -
        `has_perm()` caches its result on the instance (`_perm_cache` /
        `_user_perm_cache` / `_group_perm_cache`), and `refresh_from_db()`
        only reloads DB fields, not those cache attributes. Tests that
        call `has_perm()` both before and after a role change need a
        genuinely new instance to see the post-change permissions, same
        as a real request does (AuthenticationMiddleware loads a fresh
        user object on every request).
        """
        self.target = User.objects.get(pk=self.target.pk)
        return self.target

    def test_reader_to_contributor(self):
        self._change_role("contributor")
        user = self._refresh_target()
        self.assertEqual(user.role, "contributor")
        self.assertEqual(set(user.groups.values_list("name", flat=True)), {"Contributor"})
        self.assertTrue(user.has_perm("blog.add_post"))

    def test_reader_to_editor(self):
        self._change_role("editor")
        user = self._refresh_target()
        self.assertEqual(user.role, "editor")
        self.assertEqual(set(user.groups.values_list("name", flat=True)), {"Editor"})
        self.assertTrue(user.has_perm("blog.can_publish_post"))

    def test_contributor_to_editor(self):
        self._change_role("contributor")
        self._change_role("editor")
        user = self._refresh_target()
        self.assertEqual(user.role, "editor")
        self.assertEqual(set(user.groups.values_list("name", flat=True)), {"Editor"})

    def test_editor_to_contributor_loses_publish_permission(self):
        self._change_role("editor")
        self.assertTrue(self._refresh_target().has_perm("blog.can_publish_post"))

        self._change_role("contributor")
        user = self._refresh_target()
        self.assertEqual(set(user.groups.values_list("name", flat=True)), {"Contributor"})
        self.assertFalse(user.has_perm("blog.can_publish_post"))
        self.assertTrue(user.has_perm("blog.add_post"))

    def test_editor_to_reader_loses_editor_permissions(self):
        self._change_role("editor")
        self._change_role("reader")
        user = self._refresh_target()
        self.assertEqual(user.role, "reader")
        self.assertEqual(set(user.groups.values_list("name", flat=True)), {"Reader"})
        self.assertFalse(user.has_perm("blog.add_post"))
        self.assertFalse(user.has_perm("blog.can_publish_post"))

    def test_contributor_to_reader_loses_add_post(self):
        self._change_role("contributor")
        self._change_role("reader")
        user = self._refresh_target()
        self.assertEqual(user.role, "reader")
        self.assertFalse(user.has_perm("blog.add_post"))

    def test_role_change_never_leaves_multiple_role_groups(self):
        role_group_names = {"Admin", "Editor", "Author", "Contributor", "Reader"}
        for role in ("contributor", "editor", "reader", "editor", "contributor"):
            self._change_role(role)
            user = self._refresh_target()
            held = set(user.groups.values_list("name", flat=True)) & role_group_names
            self.assertEqual(len(held), 1, f"expected exactly one role group after -> {role}, got {held}")

    def test_admin_choice_not_offered_to_non_superuser(self):
        """
        Direct check of the form-level protection: even a staff user who
        somehow has permission to reach this form (see
        AdminRoleSecurityTests for how normal roles are blocked from
        reaching it at all) is never offered "admin" as a role choice.
        """
        staff = User.objects.create_user(
            username="staffeditor", password=PASSWORD, role="editor", is_staff=True,
        )
        ct = ContentType.objects.get_for_model(User)
        staff.user_permissions.add(
            *Permission.objects.filter(content_type=ct, codename__in=["change_customuser", "view_customuser"])
        )
        client = _verified_client(staff)

        response = client.get(self.change_url)
        choice_values = [value for value, _ in response.context["adminform"].form.fields["role"].choices]

        self.assertNotIn("admin", choice_values)
        self.assertIn("reader", choice_values)
        self.assertIn("contributor", choice_values)
        self.assertIn("editor", choice_values)

    def test_non_superuser_cannot_grant_admin_via_crafted_post(self):
        """
        Even with a hand-crafted POST (bypassing the rendered dropdown
        entirely), a non-superuser staff member with role-management
        access can't set role="admin" - the form itself rejects the value.
        """
        staff = User.objects.create_user(
            username="staffeditor2", password=PASSWORD, role="editor", is_staff=True,
        )
        ct = ContentType.objects.get_for_model(User)
        staff.user_permissions.add(
            *Permission.objects.filter(content_type=ct, codename__in=["change_customuser", "view_customuser"])
        )
        client = _verified_client(staff)

        get_response = client.get(self.change_url)
        data = _admin_change_form_data(get_response.context["adminform"].form, role="admin")
        response = client.post(self.change_url, data)

        self.assertEqual(response.status_code, 200)
        self.assertIn("role", response.context["adminform"].form.errors)
        self.target.refresh_from_db()
        self.assertEqual(self.target.role, "reader")

    def test_invalid_role_value_is_rejected(self):
        get_response = self.client.get(self.change_url)
        data = _admin_change_form_data(get_response.context["adminform"].form, role="superadmin")
        response = self.client.post(self.change_url, data)

        self.assertEqual(response.status_code, 200)
        self.assertIn("role", response.context["adminform"].form.errors)
        self.target.refresh_from_db()
        self.assertEqual(self.target.role, "reader")


class AdminRoleSecurityTests(TestCase):
    """
    Non-admin users must never be able to reach role management at all -
    not the list page, not another user's change page, not even their own.
    """

    @classmethod
    def setUpTestData(cls):
        call_command("setup_roles")

    def setUp(self):
        self.target = User.objects.create_user(
            username="target", password=PASSWORD, role="reader"
        )
        self.change_url = reverse("admin:users_customuser_change", args=[self.target.pk])
        self.changelist_url = reverse("admin:users_customuser_changelist")

    def _assert_denied(self, client):
        response = client.get(self.change_url)
        self.assertNotEqual(response.status_code, 200)

        response = client.get(self.changelist_url)
        self.assertNotEqual(response.status_code, 200)

    def test_reader_cannot_access_role_management(self):
        reader = User.objects.create_user(username="plainreader", password=PASSWORD, role="reader")
        client = Client()
        client.force_login(reader)
        self._assert_denied(client)

    def test_contributor_cannot_access_role_management(self):
        contributor = User.objects.create_user(
            username="plaincontributor", password=PASSWORD, role="contributor"
        )
        client = Client()
        client.force_login(contributor)
        self._assert_denied(client)

    def test_editor_without_staff_cannot_access_role_management(self):
        # Editor role alone (no is_staff) can't reach /admin/ at all - it
        # doesn't carry Django admin site access on its own.
        editor = User.objects.create_user(username="plaineditor", password=PASSWORD, role="editor")
        client = _verified_client(editor)
        self._assert_denied(client)

    def test_editor_with_staff_but_no_permission_cannot_change_users(self):
        # is_staff alone isn't enough either - ModelAdmin still requires
        # the users.change_customuser/view_customuser permissions, which no
        # application-role Group grants.
        editor = User.objects.create_user(
            username="staffeditornoperm", password=PASSWORD, role="editor", is_staff=True,
        )
        client = _verified_client(editor)
        self._assert_denied(client)

    def test_user_cannot_change_own_role_via_crafted_post(self):
        reader = User.objects.create_user(username="selfpromoter", password=PASSWORD, role="reader")
        own_change_url = reverse("admin:users_customuser_change", args=[reader.pk])
        client = Client()
        client.force_login(reader)

        response = client.post(own_change_url, {"role": "admin", "username": reader.username})

        self.assertNotEqual(response.status_code, 200)
        reader.refresh_from_db()
        self.assertEqual(reader.role, "reader")

    def test_anonymous_cannot_access_role_management(self):
        self._assert_denied(Client())
