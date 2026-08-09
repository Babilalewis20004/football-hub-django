from django.urls import path

from . import views

urlpatterns = [
    path('start/', views.start_chat, name='chat_start'),
    path('<int:session_id>/messages/', views.chat_messages, name='chat_messages'),
    path('<int:session_id>/close/', views.close_chat, name='chat_close'),

    path('support/', views.support_inbox, name='support_inbox'),
    path('support/<int:session_id>/', views.support_chat_room, name='support_chat_room'),
]
