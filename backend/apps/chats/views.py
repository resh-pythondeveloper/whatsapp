from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from .serializers import (
    ConversationSerializer,
    MessageSerializer,
    CreateOneToOneConversationSerializer,
    CreateGroupConversationSerializer,
    SendMessageSerializer,
)
from apps.chats.models import Conversation, ConversationMember, Message
from apps.chats.service.chat_service import ChatService
from apps.chats.pagination import MessageCursorPagination
from apps.chats.service.message_cache_service import (
    MessageCacheService
)

class CreateOneToOneConversationView(APIView):
    permission_classes = [IsAuthenticated]

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
    permission_classes = [IsAuthenticated]

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
    permission_classes = [IsAuthenticated]

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
                "count": len(conversations),
                "data": serializer.data,
            }
        )


class SendMessageView(APIView):
    permission_classes = [IsAuthenticated]
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

class MessageListAPIView(APIView):

    permission_classes = [
        IsAuthenticated
    ]

    def get(
        self,
        request,
        conversation_id,
    ):

        # ==========================================
        # 1. Check conversation
        # ==========================================

        try:

            conversation = Conversation.objects.get(
                id=conversation_id
            )

        except Conversation.DoesNotExist:

            return Response(
                {
                    "message": "Conversation not found"
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        # ==========================================
        # 2. Check membership
        # ==========================================

        is_member = (
            ConversationMember.objects.filter(
                conversation_id=conversation_id,
                user=request.user,
                is_active=True,
            ).exists()
        )

        if not is_member:

            return Response(
                {
                    "message": (
                        "You are not a member "
                        "of this conversation"
                    )
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # ==========================================
        # 3. Get cursor
        # ==========================================

        cursor = request.query_params.get(
            "cursor"
        )

        # ==========================================
        # 4. Redis cache
        # ==========================================

        cache_service = MessageCacheService()
        try:

            cached_data = (
                cache_service.get_messages(
                    conversation_id=str(
                        conversation_id
                    ),
                    cursor=cursor,
                )
            )
        except Exception:
            cached_data = None

        if cached_data:

            return Response(
                cached_data,
                status=status.HTTP_200_OK,
            )

        # ==========================================
        # 5. PostgreSQL
        # ==========================================

        messages = (
            Message.objects
            .filter(conversation_id=conversation_id)
            .select_related(
                "sender"
            )
            .order_by(
                "-created_at"
            )
        )

        # ==========================================
        # 6. Pagination
        # ==========================================

        paginator = MessageCursorPagination()

        page = paginator.paginate_queryset(
            messages,
            request,view=self,
        )

        serializer = MessageSerializer(
            page,
            many=True
        )

        response = (
            paginator.get_paginated_response(
                serializer.data
            )
        )

        # ==========================================
        # 7. Convert Response to JSON data
        # ==========================================

        response_data = response.data

        # ==========================================
        # 8. Save to Redis
        # ==========================================
        try:

            cache_service.set_messages(
                conversation_id=str(
                    conversation_id
                ),
                cursor=cursor,
                data=response_data,
            )
        except Exception:
            pass

        # ==========================================
        # 9. Return response
        # ==========================================

        return Response(
            response_data,status=status.HTTP_200_OK,
        )

class MessageSearchAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, conversation_id):
        query = request.query_params.get("q", "").strip()

        # Validate search query
        if not query:
            return Response(
                {
                    "message": "Search query is required."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        # Check conversation exists
        if not Conversation.objects.filter(id=conversation_id).exists():
            return Response(
                {
                    "message": "Conversation not found."
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        # Check conversation membership
        is_member = ConversationMember.objects.filter(
            conversation_id=conversation_id,
            user=request.user,
            is_active=True,
        ).exists()

        if not is_member:
            return Response(
                {
                    "message": "You are not a member of this conversation."
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # Search messages
        messages = (
            Message.objects
            .filter(
                conversation_id=conversation_id,
                content__icontains=query,
            )
            .select_related("sender")
            .order_by("-created_at")
        )

        # Cursor pagination
        paginator = MessageCursorPagination()

        page = paginator.paginate_queryset(
            messages,
            request,
            view=self,
        )

        serializer = MessageSerializer(
            page,
            many=True,
        )


        response = paginator.get_paginated_response(
            serializer.data
        )

        # Add search query to response
        response.data["query"] = query

        return response