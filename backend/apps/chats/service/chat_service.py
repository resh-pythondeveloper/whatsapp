from django.db import transaction
from django.db.models import F, OuterRef, Subquery
from django.utils import timezone
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError

from apps.accounts.models import User
from apps.chats.models import Conversation, ConversationMember, Message


class ChatService:

    @staticmethod
    @transaction.atomic
    def create_one_to_one_conversation(user, other_user_id):
        if str(user.id) == str(other_user_id):
            raise ValidationError(
                "You cannot create a conversation with yourself."
            )

        try:
            other_user = User.objects.get(
                id=other_user_id,
                is_active=True,
            )
        except User.DoesNotExist:
            raise NotFound("User not found.")

        existing_conversations = (
            Conversation.objects
            .filter(
                conversation_type=Conversation.ConversationType.ONE_TO_ONE,
            )
            .filter(
                members__user=user,
                members__is_active=True,
            )
            .filter(
                members__user=other_user,
                members__is_active=True,
            )
            .distinct()
        )

        for conversation in existing_conversations:
            member_count = (
                ConversationMember.objects
                .filter(
                    conversation=conversation,
                    is_active=True,
                )
                .count()
            )

            if member_count == 2:
                return conversation

        conversation = Conversation.objects.create(
            conversation_type=Conversation.ConversationType.ONE_TO_ONE,
            created_by=user,
        )

        ConversationMember.objects.bulk_create([
            ConversationMember(
                conversation=conversation,
                user=user,
            ),
            ConversationMember(
                conversation=conversation,
                user=other_user,
            ),
        ])

        return conversation

    @staticmethod
    @transaction.atomic
    def create_group_conversation(user, name, member_ids):
        if not name or not name.strip():
            raise ValidationError("Group name is required.")

        member_ids = list(dict.fromkeys(member_ids))

        if user.id in member_ids:
            member_ids.remove(user.id)

        users = User.objects.filter(
            id__in=member_ids,
            is_active=True,
        )

        if users.count() != len(member_ids):
            raise ValidationError(
                "One or more users do not exist."
            )

        conversation = Conversation.objects.create(
            conversation_type=Conversation.ConversationType.GROUP,
            name=name.strip(),
            created_by=user,
        )

        all_users = [user] + list(users)

        ConversationMember.objects.bulk_create([
            ConversationMember(
                conversation=conversation,
                user=member,
            )
            for member in all_users
        ])

        return conversation

    @staticmethod
    def get_user_conversations(user):

        # Get the user's active memberships
        memberships = list(
            ConversationMember.objects
            .filter(
                user=user,
                is_active=True,
            )
            .select_related("conversation")
        )

        if not memberships:
            return []

        conversation_ids = [
            membership.conversation_id
            for membership in memberships
        ]

        # Latest message subquery
        latest_message = (
            Message.objects
            .filter(
                conversation_id=OuterRef("pk")
            )
            .order_by("-created_at")
        )

        # Get conversations + members in optimized queries
        conversations = list(
            Conversation.objects
            .filter(
                id__in=conversation_ids
            )
            .select_related("created_by")
            .prefetch_related(
                "members__user"
            )
            .annotate(
                latest_message_id=Subquery(
                    latest_message.values("id")[:1]
                ),
                latest_message_content=Subquery(
                    latest_message.values("content")[:1]
                ),
                latest_message_type=Subquery(
                    latest_message.values("message_type")[:1]
                ),
                latest_message_sender_id=Subquery(
                    latest_message.values("sender_id")[:1]
                ),
                latest_message_created_at=Subquery(
                    latest_message.values("created_at")[:1]
                ),
            )
            .order_by("-updated_at")
        )

        # Map membership by conversation
        membership_map = {
            membership.conversation_id: membership
            for membership in memberships
        }

        # Attach latest message + unread count
        for conversation in conversations:

            membership = membership_map.get(
                conversation.id
            )

            conversation.user_unread_count = (
                membership.unread_count
                if membership
                else 0
            )

            if conversation.latest_message_id:

                conversation.latest_message = Message(
                    id=conversation.latest_message_id,
                    conversation_id=conversation.id,
                    content=conversation.latest_message_content,
                    message_type=conversation.latest_message_type,
                    sender_id=conversation.latest_message_sender_id,
                    created_at=conversation.latest_message_created_at,
                )

            else:
                conversation.latest_message = None

        return conversations

    @staticmethod
    def get_conversation_messages(user, conversation_id):

        try:
            conversation = Conversation.objects.get(
                id=conversation_id
            )
        except Conversation.DoesNotExist:
            raise NotFound("Conversation not found.")

        is_member = ConversationMember.objects.filter(
            conversation=conversation,
            user=user,
            is_active=True,
        ).exists()

        if not is_member:
            raise PermissionDenied(
                "You are not a member of this conversation."
            )

        return (
            Message.objects
            .filter(conversation=conversation)
            .select_related("sender")
            .order_by("created_at")
        )

    @staticmethod
    @transaction.atomic
    def send_message(user, conversation_id, content):

        if not content or not content.strip():
            raise ValidationError(
                "Message cannot be empty."
            )

        content = content.strip()

        try:
            conversation = Conversation.objects.get(
                id=conversation_id
            )
        except Conversation.DoesNotExist:
            raise NotFound("Conversation not found.")

        is_member = ConversationMember.objects.filter(
            conversation=conversation,
            user=user,
            is_active=True,
        ).exists()

        if not is_member:
            raise PermissionDenied(
                "You are not a member of this conversation."
            )

        message = Message.objects.create(
            conversation=conversation,
            sender=user,
            content=content,
            message_type=Message.MessageType.TEXT,
            status=Message.MessageStatus.SENT,
        )

        ConversationMember.objects.filter(
            conversation_id=conversation_id,
            is_active=True,
        ).exclude(
            user_id=user.id
        ).update(
            unread_count=F("unread_count") + 1
        )

        conversation.updated_at = timezone.now()

        conversation.save(
            update_fields=["updated_at"]
        )

        return message

    @staticmethod
    def increment_unread_counts(
        conversation_id,
        sender_id,
    ):
        return (
            ConversationMember.objects
            .filter(
                conversation_id=conversation_id,
                is_active=True,
            )
            .exclude(
                user_id=sender_id
            )
            .update(
                unread_count=F("unread_count") + 1
            )
        )

    @staticmethod
    @transaction.atomic
    def mark_conversation_as_read(conversation_id, user_id, message_id):
        try:
            membership = ConversationMember.objects.select_for_update().get(
                conversation_id=conversation_id,
                user_id=user_id,
                is_active=True,
            )
        except ConversationMember.DoesNotExist:
            raise PermissionDenied("You are not a member of this conversation.")

        try:
            message = Message.objects.get(
                id=message_id,
                conversation_id=conversation_id,
            )
        except Message.DoesNotExist:
            raise NotFound("Message not found.")

        # The user cannot mark their own message as read
        if message.sender_id == user_id:
            return {
                "last_read_at": membership.last_read_at,
                "unread_count": membership.unread_count,
            }

        # Move read position forward only
        if (
            membership.last_read_at is None
            or message.created_at > membership.last_read_at
        ):
            membership.last_read_at = message.created_at

        # Count only messages after the new read position
        unread_count = (
            Message.objects
            .filter(
                conversation_id=conversation_id,
                created_at__gt=membership.last_read_at,
            )
            .exclude(sender_id=user_id)
            .count()
        )

        membership.unread_count = unread_count

        membership.save(
            update_fields=[
                "last_read_at",
                "unread_count",
            ]
        )

        return {
            "last_read_at": membership.last_read_at,
            "unread_count": membership.unread_count,
        }

    @staticmethod
    def get_unread_count(
        conversation_id,
        user_id,
    ):
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