from datetime import datetime

from django.utils.dateparse import parse_datetime

from apps.chats.models import (
    ConversationMember,
    Message,
)


class MessageService:

    DEFAULT_LIMIT = 20
    MAX_LIMIT = 100

    @staticmethod
    def get_paginated_messages(
        conversation_id,
        user_id,
        cursor=None,
        limit=None,
    ):

        # -----------------------------------
        # Validate conversation membership
        # -----------------------------------

        is_member = (
            ConversationMember.objects.filter(
                conversation_id=conversation_id,
                user_id=user_id,
                is_active=True,
            ).exists()
        )

        if not is_member:
            return None

        # -----------------------------------
        # Validate limit
        # -----------------------------------

        try:
            limit = int(limit or MessageService.DEFAULT_LIMIT)

        except (TypeError, ValueError):
            limit = MessageService.DEFAULT_LIMIT

        # Prevent very large queries
        limit = min(
            max(limit, 1),
            MessageService.MAX_LIMIT
        )

        # -----------------------------------
        # Base queryset
        # -----------------------------------

        queryset = (
            Message.objects.filter(
                conversation_id=conversation_id
            )
            .select_related("sender")
            .order_by("-created_at")
        )

        # -----------------------------------
        # Apply cursor
        # -----------------------------------

        if cursor:

            cursor_datetime = parse_datetime(
                cursor
            )

            if cursor_datetime:

                queryset = queryset.filter(
                    created_at__lt=cursor_datetime
                )

        # -----------------------------------
        # Fetch limit + 1
        # -----------------------------------

        messages = list(
            queryset[:limit + 1]
        )

        # -----------------------------------
        # Check if more messages exist
        # -----------------------------------

        has_more = (
            len(messages) > limit
        )

        # Remove extra message
        if has_more:
            messages = messages[:limit]

        # -----------------------------------
        # Build next cursor
        # -----------------------------------

        next_cursor = None

        if has_more and messages:

            next_cursor = (
                messages[-1]
                .created_at
                .isoformat()
            )

        # -----------------------------------
        # Serialize messages
        # -----------------------------------

        message_data = []

        for message in messages:

            message_data.append(
                {
                    "id": str(message.id),

                    "conversation_id": str(
                        message.conversation_id
                    ),

                    "sender_id": str(
                        message.sender_id
                    ),

                    "content": message.content,

                    "message_type": (
                        message.message_type
                    ),

                    "status": message.status,

                    "created_at": (
                        message.created_at.isoformat()
                    ),
                }
            )

        return {
            "messages": message_data,

            "pagination": {
                "next_cursor": next_cursor,

                "has_more": has_more,

                "limit": limit,
            },
        }