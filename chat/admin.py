from django.contrib import admin

from .models import ChatSession, ChatMessage


class ChatMessageInline(admin.TabularInline):
    model = ChatMessage
    extra = 0
    readonly_fields = ('sender', 'sender_name', 'is_staff_message', 'body', 'created_at')
    can_delete = False


@admin.register(ChatSession)
class ChatSessionAdmin(admin.ModelAdmin):
    list_display = ('id', 'visitor_name', 'agent', 'status', 'created_at', 'updated_at')
    list_filter = ('status',)
    search_fields = ('visitor_name', 'session_key')
    inlines = [ChatMessageInline]


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'session', 'sender_name', 'is_staff_message', 'created_at')
    list_filter = ('is_staff_message',)
    search_fields = ('sender_name', 'body')
