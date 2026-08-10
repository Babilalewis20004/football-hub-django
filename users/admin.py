# Register your models here.
from django.contrib import admin

from django.contrib.auth.admin import UserAdmin

from .forms import LockoutAwareAdminAuthenticationForm
from .models import CustomUser, LoginAttempt

# Applies the same 5-attempt / 15-minute lockout used by the public login
# view to /admin/ - see LockoutAwareAdminAuthenticationForm.
admin.site.login_form = LockoutAwareAdminAuthenticationForm


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    pass


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