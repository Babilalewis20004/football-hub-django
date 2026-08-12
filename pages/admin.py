from django.contrib import admin

from .models import Feedback, Subscriber


@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = ("rating", "name", "email", "user", "created_at")
    list_filter = ("rating", "created_at")
    search_fields = ("name", "email", "comment", "user__username")
    readonly_fields = ("created_at",)


@admin.register(Subscriber)
class SubscriberAdmin(admin.ModelAdmin):
    list_display = ("email", "created_at")
    search_fields = ("email",)
    readonly_fields = ("created_at",)
