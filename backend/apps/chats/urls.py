from django.urls import path

from .views import (
    CreateOneToOneConversationView,
    CreateGroupConversationView,
    ConversationListView,
    ConversationMessagesView,
    SendMessageView,
)


urlpatterns = [

    path(
        "conversations/one-to-one/",
        CreateOneToOneConversationView.as_view(),
        name="create-one-to-one-conversation"
    ),

    path(
        "conversations/group/",
        CreateGroupConversationView.as_view(),
        name="create-group-conversation"
    ),

    path(
        "conversations/",
        ConversationListView.as_view(),
        name="conversation-list"
    ),

    path(
        "conversations/<uuid:conversation_id>/messages/",
        ConversationMessagesView.as_view(),
        name="conversation-messages"
    ),

    path(
        "messages/send/",
        SendMessageView.as_view(),
        name="send-message"
    ),
]