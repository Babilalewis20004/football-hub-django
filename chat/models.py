from django.conf import settings
from django.db import models

SUPPORT_ROLES = ('admin', 'editor')


class ChatSession(models.Model):
    STATUS_CHOICES = [
        ('open', 'Open'),
        ('closed', 'Closed'),
    ]

    visitor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='chat_sessions',
    )
    visitor_name = models.CharField(max_length=100)

    # Ties an anonymous visitor's browser session to this chat so they
    # can reconnect (e.g. after a page reload) without an account.
    session_key = models.CharField(max_length=40, db_index=True)

    agent = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_chats',
    )

    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default='open',
        db_index=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True, db_index=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return f'Chat #{self.pk} with {self.visitor_name}'


class ChatMessage(models.Model):
    session = models.ForeignKey(
        ChatSession,
        on_delete=models.CASCADE,
        related_name='messages',
    )

    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    sender_name = models.CharField(max_length=100)
    is_staff_message = models.BooleanField(default=False)

    body = models.TextField()

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    is_read = models.BooleanField(default=False)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f'{self.sender_name}: {self.body[:30]}'
