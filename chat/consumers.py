import json
import logging

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer

from .models import ChatSession, ChatMessage
from .permissions import is_support_agent
from .services import get_unread_count

logger = logging.getLogger('chat')

SUPPORT_GROUP = 'support_agents'


class ChatConsumer(AsyncWebsocketConsumer):
    """One room per ChatSession, shared by the visitor widget and the
    staff support room."""

    async def connect(self):
        self.session_id = self.scope['url_route']['kwargs']['session_id']
        self.room_group_name = f'chat_{self.session_id}'

        session = await self._get_session(self.session_id)
        if session is None:
            await self.close()
            return

        user = self.scope['user']
        staff = is_support_agent(user)

        if not staff:
            browser_session_key = self.scope['session'].session_key
            owns_session = (
                (user.is_authenticated and session.visitor_id == user.id)
                or (browser_session_key and session.session_key == browser_session_key)
            )
            if not owns_session:
                await self.close()
                return

        if staff and session.agent_id is None:
            await self._assign_agent(session, user)

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, 'room_group_name'):
            await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            return

        body = (data.get('message') or '').strip()
        if not body:
            return

        user = self.scope['user']
        staff = is_support_agent(user)
        sender_name = user.username if user.is_authenticated else (data.get('sender_name') or 'Visitor')

        message = await self._save_message(
            session_id=self.session_id,
            sender=user if user.is_authenticated else None,
            sender_name=sender_name,
            is_staff_message=staff,
            body=body,
        )
        if message is None:
            return

        payload = {
            'session_id': int(self.session_id),
            'message': message.body,
            'sender_name': message.sender_name,
            'is_staff_message': message.is_staff_message,
            'timestamp': message.created_at.isoformat(),
        }

        await self.channel_layer.group_send(
            self.room_group_name,
            {'type': 'chat.message', **payload},
        )
        await self.channel_layer.group_send(
            SUPPORT_GROUP,
            {'type': 'chat.notify', **payload},
        )

        if not staff:
            count = await database_sync_to_async(get_unread_count)()
            await self.channel_layer.group_send(
                SUPPORT_GROUP,
                {'type': 'unread.count', 'count': count},
            )

    async def chat_message(self, event):
        await self.send(text_data=json.dumps(event))

    @database_sync_to_async
    def _get_session(self, session_id):
        return ChatSession.objects.filter(pk=session_id).first()

    @database_sync_to_async
    def _assign_agent(self, session, user):
        session.agent = user
        session.save(update_fields=['agent'])

    @database_sync_to_async
    def _save_message(self, session_id, sender, sender_name, is_staff_message, body):
        try:
            session = ChatSession.objects.get(pk=session_id, status='open')
        except ChatSession.DoesNotExist:
            return None

        message = ChatMessage.objects.create(
            session=session,
            sender=sender,
            sender_name=sender_name,
            is_staff_message=is_staff_message,
            body=body,
        )
        session.save(update_fields=['updated_at'])
        return message


class SupportInboxConsumer(AsyncWebsocketConsumer):
    """Live feed for the staff support inbox: new sessions and new
    messages across every open chat, so agents don't have to poll."""

    async def connect(self):
        user = self.scope['user']
        if not is_support_agent(user):
            await self.close()
            return

        await self.channel_layer.group_add(SUPPORT_GROUP, self.channel_name)
        await self.accept()

        count = await database_sync_to_async(get_unread_count)()
        await self.send(text_data=json.dumps({'type': 'unread.count', 'count': count}))

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(SUPPORT_GROUP, self.channel_name)

    async def chat_notify(self, event):
        await self.send(text_data=json.dumps(event))

    async def session_started(self, event):
        await self.send(text_data=json.dumps(event))

    async def session_closed(self, event):
        await self.send(text_data=json.dumps(event))

    async def unread_count(self, event):
        await self.send(text_data=json.dumps(event))
