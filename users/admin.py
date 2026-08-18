# Register your models here.
from django.contrib import admin

from django.contrib.auth.admin import UserAdmin

from .forms import LockoutAwareAdminAuthenticationForm
from .models import CustomUser, LoginAttempt
from .twofactor import user_has_2fa_enabled, user_requires_2fa, reset_2fa_for_user

# Applies the same 5-attempt / 15-minute lockout used by the public login
# view to /admin/ - see LockoutAwareAdminAuthenticationForm.
admin.site.login_form = LockoutAwareAdminAuthenticationForm


# Roles a non-superuser admin is allowed to hand out through the ordinary
# "Application role" selector on the user change form. "admin" is
# deliberately excluded: promoting someone to Admin stays restricted to
# Django superusers (see CustomUserAdmin.get_form), matching the project's
# existing convention of pairing role="admin" with is_staff/is_superuser by
# hand rather than exposing it as a routine, self-service dropdown choice.
NON_ADMIN_ROLE_CHOICES = tuple(
    choice for choice in CustomUser.ROLE_CHOICES if choice[0] != "admin"
)


def _drop_groups_field(fieldsets):
    """
    UserAdmin's stock "Permissions" fieldset includes a raw `groups`
    multi-select. Django admin's ModelForm machinery saves *every* m2m
    field present on the form after save_model() runs (form.save_m2m(),
    called from ModelAdmin.save_related) - so if `groups` stayed on this
    form, submitting the change page would silently re-apply whatever
    Group list was showing when the page loaded, overwriting the
    Reader/Contributor/Author/Editor/Admin Group that `role` (via
    users.signals.sync_role_group) had just been synced to by save_model().
    Dropping it from the form entirely - rather than leaving it editable
    alongside `role` - is what makes `role` the single, authoritative
    selector the admin UI actually uses for application-role management,
    instead of two controls that can disagree with each other.
    """
    rebuilt = []
    for name, options in fieldsets:
        options = dict(options)
        if "groups" in options.get("fields", ()):
            options["fields"] = tuple(f for f in options["fields"] if f != "groups")
        rebuilt.append((name, options))
    return tuple(rebuilt)


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = (
        "username",
        "email",
        "role",
        "is_active",
        "is_staff",
        "date_joined",
        "has_2fa_enabled",
        "requires_2fa",
    )
    list_filter = UserAdmin.list_filter + ("role",)
    fieldsets = _drop_groups_field(UserAdmin.fieldsets) + (
        ("Application role", {"fields": ("role",)}),
    )
    actions = UserAdmin.actions + ("reset_two_factor_enrollment",)

    def get_form(self, request, obj=None, **kwargs):
        """
        Restricts the "Application role" dropdown to Reader/Contributor/
        Author/Editor for anyone who isn't a Django superuser, so the
        routine role-management UI can never be used to grant (or,
        indirectly, to self-grant) the Admin role - see NON_ADMIN_ROLE_CHOICES.
        Superusers keep the full choice list, which is the deliberate,
        existing path for creating/promoting Admins in this project.
        """
        form = super().get_form(request, obj, **kwargs)
        role_field = form.base_fields.get("role")
        if role_field is not None and not request.user.is_superuser:
            role_field.choices = NON_ADMIN_ROLE_CHOICES
        return form

    @admin.display(boolean=True, description="2FA enabled")
    def has_2fa_enabled(self, obj):
        return user_has_2fa_enabled(obj)

    @admin.display(boolean=True, description="2FA required")
    def requires_2fa(self, obj):
        return user_requires_2fa(obj)

    @admin.action(description="Reset 2FA enrollment for selected users")
    def reset_two_factor_enrollment(self, request, queryset):
        for user in queryset:
            reset_2fa_for_user(user)

        count = queryset.count()
        self.message_user(
            request,
            f"2FA enrollment reset for {count} user(s). They will be prompted "
            "to set it up again the next time it's required.",
        )


@admin.register(LoginAttempt)
class LoginAttemptAdmin(admin.ModelAdmin):
    list_display = ("username", "successful", "reason", "ip_address", "timestamp")
    list_filter = ("successful", "reason")
    search_fields = ("username", "ip_address")
    ordering = ("-timestamp",)
    readonly_fields = [f.name for f in LoginAttempt._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False