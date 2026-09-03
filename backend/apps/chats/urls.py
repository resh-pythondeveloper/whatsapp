from django.urls import path

from .views import (
    CreateOneToOneConversationView,
    CreateGroupConversationView,
    ConversationListView,
    SendMessageView,MessageListAPIView,MessageSearchAPIView
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
        MessageListAPIView.as_view(),
        name="conversation-messages"
    ),

    path(
        "messages/send/",
        SendMessageView.as_view(),
        name="send-message"
    ),
    path(
        "conversations/<uuid:conversation_id>/messages/search/",
        MessageSearchAPIView.as_view(),
        name="message-search",
    ),

]