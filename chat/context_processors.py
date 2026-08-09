from .permissions import is_support_agent
from .services import get_unread_count


def unread_chat_count(request):
    user = getattr(request, 'user', None)
    if user is None or not is_support_agent(user):
        return {}

    return {'support_unread_count': get_unread_count()}
