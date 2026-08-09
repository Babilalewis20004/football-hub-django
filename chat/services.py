from .models import ChatMessage


def get_unread_count():
    return ChatMessage.objects.filter(
        is_staff_message=False,
        is_read=False,
        session__status='open',
    ).count()
