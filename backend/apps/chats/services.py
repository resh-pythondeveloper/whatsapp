from django.db import transaction
from rest_framework.exceptions import (
    NotFound,
    PermissionDenied,
    ValidationError,
)

from apps.accounts.models import User

from .models import (
    Conversation,
    ConversationMember,
    Message,
)


class ChatService:

    @staticmethod
    @transaction.atomic
    def create_one_to_one_conversation(
        user,
        other_user_id
    ):
        """
        Create a one-to-one conversation.
        Return existing conversation if already exists.
        """

        if str(user.id) == str(other_user_id):
            raise ValidationError(
                "You cannot create a conversation with yourself."
            )

        try:
            other_user = User.objects.get(
                id=other_user_id,
                is_active=True
            )
        except User.DoesNotExist:
            raise NotFound("User not found.")

        # Find existing one-to-one conversation
        existing_conversation = (
            Conversation.objects
            .filter(
                conversation_type=Conversation.ConversationType.ONE_TO_ONE
            )
            .filter(
                members__user=user
            )
            .filter(
                members__user=other_user
            )
            .distinct()
        )

        for conversation in existing_conversation:
            if conversation.members.count() == 2:
                return conversation

        # Create new conversation
        conversation = Conversation.objects.create(
            conversation_type=Conversation.ConversationType.ONE_TO_ONE,
            created_by=user
        )

        ConversationMember.objects.bulk_create([
            ConversationMember(
                conversation=conversation,
                user=user
            ),
            ConversationMember(
                conversation=conversation,
                user=other_user
            ),
        ])

        return conversation

    @staticmethod
    @transaction.atomic
    def create_group_conversation(
        user,
        name,
        member_ids
    ):
        """
        Create a group conversation.
        """

        if not name:
            raise ValidationError(
                "Group name is required."
            )

        member_ids = list(set(member_ids))

        users = User.objects.filter(
            id__in=member_ids,
            is_active=True
        )

        if users.count() != len(member_ids):
            raise ValidationError(
                "One or more users do not exist."
            )

        conversation = Conversation.objects.create(
            conversation_type=Conversation.ConversationType.GROUP,
            name=name,
            created_by=user
        )

        # Add creator if not included
        all_users = list(users)

        if user not in all_users:
            all_users.append(user)

        ConversationMember.objects.bulk_create([
            ConversationMember(
                conversation=conversation,
                user=member
            )
            for member in all_users
        ])

        return conversation

    @staticmethod
    def get_user_conversations(user):
        """
        Get all conversations for logged-in user.
        """

        return (
            Conversation.objects
            .filter(
                members__user=user,
                members__is_active=True
            )
            .select_related("created_by")
            .prefetch_related(
                "members__user"
            )
            .distinct()
            .order_by("-updated_at")
        )

    @staticmethod
    def get_conversation_messages(
        user,
        conversation_id
    ):
        """
        Get messages only if user belongs to conversation.
        """

        try:
            conversation = Conversation.objects.get(
                id=conversation_id
            )
        except Conversation.DoesNotExist:
            raise NotFound(
                "Conversation not found."
            )

        is_member = ConversationMember.objects.filter(
            conversation=conversation,
            user=user,
            is_active=True
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
    def send_message(
        user,
        conversation_id,
        content
    ):
        """
        Send a message to a conversation.
        """

        try:
            conversation = Conversation.objects.get(
                id=conversation_id
            )
        except Conversation.DoesNotExist:
            raise NotFound(
                "Conversation not found."
            )

        is_member = ConversationMember.objects.filter(
            conversation=conversation,
            user=user,
            is_active=True
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
            status=Message.MessageStatus.SENT
        )

        # Update conversation ordering
        conversation.save(
            update_fields=["updated_at"]
        )

        return message