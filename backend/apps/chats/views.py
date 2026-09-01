from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import (
    ConversationSerializer,
    MessageSerializer,
    CreateOneToOneConversationSerializer,
    CreateGroupConversationSerializer,
    SendMessageSerializer,
)

from apps.chats.services import ChatService


class CreateOneToOneConversationView(APIView):

    def post(self, request):

        serializer = CreateOneToOneConversationSerializer(
            data=request.data
        )

        serializer.is_valid(raise_exception=True)

        conversation = (
            ChatService.create_one_to_one_conversation(
                user=request.user,
                other_user_id=serializer.validated_data["user_id"]
            )
        )

        return Response(
            {
                "message": "Conversation created successfully.",
                "data": ConversationSerializer(
                    conversation
                ).data,
            },
            status=status.HTTP_201_CREATED
        )


class CreateGroupConversationView(APIView):

    def post(self, request):

        serializer = CreateGroupConversationSerializer(
            data=request.data
        )

        serializer.is_valid(raise_exception=True)

        conversation = (
            ChatService.create_group_conversation(
                user=request.user,
                name=serializer.validated_data["name"],
                member_ids=serializer.validated_data["member_ids"]
            )
        )

        return Response(
            {
                "message": "Group created successfully.",
                "data": ConversationSerializer(
                    conversation
                ).data,
            },
            status=status.HTTP_201_CREATED
        )


class ConversationListView(APIView):

    def get(self, request):

        conversations = (
            ChatService.get_user_conversations(
                request.user
            )
        )

        serializer = ConversationSerializer(
            conversations,
            many=True
        )

        return Response(
            {
                "count": conversations.count(),
                "data": serializer.data,
            }
        )


class ConversationMessagesView(APIView):

    def get(self, request, conversation_id):

        messages = (
            ChatService.get_conversation_messages(
                user=request.user,
                conversation_id=conversation_id
            )
        )

        serializer = MessageSerializer(
            messages,
            many=True
        )

        return Response(
            {
                "count": messages.count(),
                "data": serializer.data,
            }
        )


class SendMessageView(APIView):

    def post(self, request):

        serializer = SendMessageSerializer(
            data=request.data
        )

        serializer.is_valid(raise_exception=True)

        message = ChatService.send_message(
            user=request.user,
            conversation_id=serializer.validated_data[
                "conversation_id"
            ],
            content=serializer.validated_data["content"]
        )

        return Response(
            {
                "message": "Message sent successfully.",
                "data": MessageSerializer(
                    message
                ).data,
            },
            status=status.HTTP_201_CREATED
        )