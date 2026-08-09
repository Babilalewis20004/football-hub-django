import json
import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from .models import ChatSession
from .permissions import is_support_agent, support_agent_required
from .services import get_unread_count

logger = logging.getLogger('chat')


def _ensure_session_key(request):
    if not request.session.session_key:
        request.session.save()
    return request.session.session_key


def _can_access_session(request, session):
    if is_support_agent(request.user):
        return True
    if request.user.is_authenticated and session.visitor_id == request.user.id:
        return True

    session_key = request.session.session_key
    return bool(session_key) and session.session_key == session_key


def _notify_support(payload):
    channel_layer = get_channel_layer()
    if channel_layer is not None:
        async_to_sync(channel_layer.group_send)('support_agents', payload)


# ---------------------------------------------------------
# Visitor-facing widget endpoints
# ---------------------------------------------------------

@require_POST
def start_chat(request):
    session_key = _ensure_session_key(request)

    try:
        payload = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        payload = {}

    session = None
    if request.user.is_authenticated:
        session = ChatSession.objects.filter(visitor=request.user, status='open').first()
    if session is None:
        session = ChatSession.objects.filter(session_key=session_key, status='open').first()

    if session is None:
        if request.user.is_authenticated:
            visitor_name = request.user.get_full_name() or request.user.username
        else:
            visitor_name = (payload.get('name') or '').strip() or 'Visitor'

        session = ChatSession.objects.create(
            visitor=request.user if request.user.is_authenticated else None,
            visitor_name=visitor_name,
            session_key=session_key,
        )

        logger.info(f'Chat session #{session.id} started by {visitor_name}')

        _notify_support({
            'type': 'session.started',
            'session_id': session.id,
            'visitor_name': session.visitor_name,
            'created_at': session.created_at.isoformat(),
        })

    return JsonResponse({
        'session_id': session.id,
        'visitor_name': session.visitor_name,
        'status': session.status,
    })


@require_GET
def chat_messages(request, session_id):
    session = get_object_or_404(ChatSession, pk=session_id)

    if not _can_access_session(request, session):
        return HttpResponseForbidden()

    return JsonResponse({
        'session_id': session.id,
        'status': session.status,
        'messages': [
            {
                'sender_name': message.sender_name,
                'message': message.body,
                'is_staff_message': message.is_staff_message,
                'timestamp': message.created_at.isoformat(),
            }
            for message in session.messages.all()
        ],
    })


@require_POST
def close_chat(request, session_id):
    session = get_object_or_404(ChatSession, pk=session_id)

    if not _can_access_session(request, session):
        return HttpResponseForbidden()

    session.status = 'closed'
    session.save(update_fields=['status', 'updated_at'])

    logger.info(f'Chat session #{session.id} closed by {request.user if request.user.is_authenticated else "visitor"}')

    channel_layer = get_channel_layer()
    if channel_layer is not None:
        async_to_sync(channel_layer.group_send)(
            f'chat_{session.id}',
            {
                'type': 'chat.message',
                'session_id': session.id,
                'message': 'This chat has been closed.',
                'sender_name': 'System',
                'is_staff_message': True,
                'system': True,
                'timestamp': timezone.now().isoformat(),
            },
        )
        async_to_sync(channel_layer.group_send)(
            'support_agents',
            {'type': 'session.closed', 'session_id': session.id},
        )

    _notify_support({'type': 'unread.count', 'count': get_unread_count()})

    return JsonResponse({'status': 'closed'})


# ---------------------------------------------------------
# Staff support dashboard
# ---------------------------------------------------------

@support_agent_required
def support_inbox(request):
    sessions = (
        ChatSession.objects
        .filter(status='open')
        .select_related('agent', 'visitor')
        .prefetch_related('messages')
    )

    return render(
        request,
        'chat/support_inbox.html',
        {
            'sessions': sessions,
            'title': 'Support Inbox',
        }
    )


@support_agent_required
def support_chat_room(request, session_id):
    session = get_object_or_404(ChatSession, pk=session_id)
    messages = session.messages.all()

    unread = messages.filter(is_staff_message=False, is_read=False)
    if unread.exists():
        unread.update(is_read=True)
        _notify_support({'type': 'unread.count', 'count': get_unread_count()})

    return render(
        request,
        'chat/support_room.html',
        {
            'session': session,
            'messages': messages,
            'title': f'Chat with {session.visitor_name}',
        }
    )
