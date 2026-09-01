from apps.chats.models import (
    Conversation,
    ConversationMember,
    Message,
)


class ConversationService:

    @staticmethod
    def get_unread_count(
        conversation_id,
        user_id,
    ):

        try:

            member = ConversationMember.objects.get(
                conversation_id=conversation_id,
                user_id=user_id,
                is_active=True,
            )

        except ConversationMember.DoesNotExist:

            return 0

        # Use last read time.
        # If never read, start counting after joining.
        read_from = (
            member.last_read_at
            or member.joined_at
        )

        return (
            Message.objects.filter(
                conversation_id=conversation_id,
                created_at__gt=read_from,
            )
            .exclude(
                sender_id=user_id
            )
            .count()
        )


    @staticmethod
    def get_conversation_summary(
        conversation_id,
        user_id,
    ):

        try:

            conversation = Conversation.objects.get(
                id=conversation_id
            )

        except Conversation.DoesNotExist:

            return None

        last_message = (
            conversation.messages
            .order_by("-created_at")
            .first()
        )

        unread_count = (
            ConversationService.get_unread_count(
                conversation_id=conversation_id,
                user_id=user_id,
            )
        )

        return {
            "conversation_id": str(
                conversation.id
            ),

            "conversation_type": (
                conversation.conversation_type
            ),

            "name": conversation.name,

            "last_message": (
                {
                    "id": str(last_message.id),
                    "content": last_message.content,
                    "message_type": (
                        last_message.message_type
                    ),
                    "sender_id": str(
                        last_message.sender_id
                    ),
                    "created_at": (
                        last_message.created_at.isoformat()
                    ),
                }
                if last_message
                else None
            ),

            "unread_count": unread_count,

            "updated_at": (
                conversation.updated_at.isoformat()
            ),
        }