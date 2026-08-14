# Register your models here.
from django.contrib import admin

from django.contrib.auth.admin import UserAdmin

from .forms import LockoutAwareAdminAuthenticationForm
from .models import CustomUser, LoginAttempt
from .twofactor import user_has_2fa_enabled, user_requires_2fa, reset_2fa_for_user

# Applies the same 5-attempt / 15-minute lockout used by the public login
# view to /admin/ - see LockoutAwareAdminAuthenticationForm.
admin.site.login_form = LockoutAwareAdminAuthenticationForm


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = UserAdmin.list_display + ("role", "has_2fa_enabled", "requires_2fa")
    list_filter = UserAdmin.list_filter + ("role",)
    actions = UserAdmin.actions + ("reset_two_factor_enrollment",)

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