from apps.chats.models import ConversationMember


class ConversationService:

    @staticmethod
    def get_unread_count(conversation_id, user_id):
        """
        Return the stored unread count for the user.

        ConversationMember.unread_count is the source of truth.
        """

        membership = (
            ConversationMember.objects
            .filter(
                conversation_id=conversation_id,
                user_id=user_id,
                is_active=True,
            )
            .only("unread_count")
            .first()
        )

        if not membership:
            return 0

        return membership.unread_count

    @staticmethod
    def get_conversation_summary(conversation_id, user_id):
        """
        Return the conversation summary used by WebSocket
        conversation_update events.

        The unread count always comes from the user's
        ConversationMember.unread_count.
        """

        try:
            membership = (
                ConversationMember.objects
                .select_related(
                    "conversation",
                    "conversation__created_by",
                )
                .prefetch_related(
                    "conversation__members__user",
                )
                .get(
                    conversation_id=conversation_id,
                    user_id=user_id,
                    is_active=True,
                )
            )
        except ConversationMember.DoesNotExist:
            return None

        conversation = membership.conversation

        last_message = (
            conversation.messages
            .select_related("sender")
            .order_by("-created_at")
            .first()
        )

        return {
            "conversation_id": str(conversation.id),
            "conversation_type": conversation.conversation_type,
            "name": conversation.name,

            "created_by": {
                "id": str(conversation.created_by.id),
                "email": conversation.created_by.email,
                "username": conversation.created_by.username,
                "is_online": conversation.created_by.is_online,
                "last_seen": (
                    conversation.created_by.last_seen.isoformat()
                    if conversation.created_by.last_seen
                    else None
                ),
            } if conversation.created_by else None,

            "members": [
                {
                    "id": member.id,
                    "user": {
                        "id": str(member.user.id),
                        "email": member.user.email,
                        "username": member.user.username,
                        "is_online": member.user.is_online,
                        "last_seen": (
                            member.user.last_seen.isoformat()
                            if member.user.last_seen
                            else None
                        ),
                    },
                    "joined_at": member.joined_at.isoformat(),
                    "last_read_at": (
                        member.last_read_at.isoformat()
                        if member.last_read_at
                        else None
                    ),
                    "unread_count": member.unread_count,
                }
                for member in conversation.members.all()
            ],

            "last_message": {
                "id": str(last_message.id),
                "content": last_message.content,
                "message_type": last_message.message_type,
                "sender_id": str(last_message.sender_id),
                "created_at": last_message.created_at.isoformat(),
            } if last_message else None,

            "unread_count": membership.unread_count,

            "created_at": conversation.created_at.isoformat(),
            "updated_at": conversation.updated_at.isoformat(),
        }
