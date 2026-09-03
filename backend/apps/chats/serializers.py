from rest_framework import serializers

from apps.accounts.models import User
from .models import Conversation, ConversationMember, Message


class ChatUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "username",
            "is_online",
            "last_seen",
        ]


class ConversationMemberSerializer(serializers.ModelSerializer):
    user = ChatUserSerializer(read_only=True)

    class Meta:
        model = ConversationMember
        fields = [
            "id",
            "user",
            "joined_at",
            "last_read_at",
            "unread_count"
        ]


class ConversationSerializer(serializers.ModelSerializer):
    members = ConversationMemberSerializer(
        many=True,
        read_only=True
    )

    created_by = ChatUserSerializer(
        read_only=True
    )
    last_message = serializers.SerializerMethodField()

    unread_count = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = [
            "id",
            "conversation_type",
            "name",
            "created_by",
            "members",
            "last_message",
            "unread_count",
            "created_at",
            "updated_at",
        ]
    def get_last_message(self, obj):

        message = getattr(
            obj,
            "latest_message",
            None
        )

        if not message:
            return None

        return {
            "id": str(message.id),
            "content": message.content,
            "message_type": message.message_type,
            "sender_id": str(message.sender_id),
            "created_at": message.created_at.isoformat(),
        }

    def get_unread_count(self, obj):

        return getattr(
            obj,
            "user_unread_count",
            0
        )


class MessageSenderSerializer(serializers.ModelSerializer):

    class Meta:
        model = User
        fields = [
            "id",
            "username",
        ]


class MessageSerializer(serializers.ModelSerializer):
    sender = MessageSenderSerializer(read_only=True)

    class Meta:
        model = Message
        fields = [
            "id",
            "conversation",
            "sender",
            "content",
            "message_type",
            "status",
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "id",
            "sender",
            "status",
            "created_at",
            "updated_at",
        ]


class SendMessageSerializer(serializers.Serializer):
    conversation_id = serializers.UUIDField()
    content = serializers.CharField(
        allow_blank=False,
        trim_whitespace=True,
    )

    def validate_content(self, value):
        value = value.strip()

        if not value:
            raise serializers.ValidationError(
                "Message cannot be empty."
            )

        return value

class CreateOneToOneConversationSerializer(serializers.Serializer):
    user_id = serializers.IntegerField(
        min_value=1,
    )


class CreateGroupConversationSerializer(serializers.Serializer):
    name = serializers.CharField(
        max_length=255,allow_blank=False,
        trim_whitespace=True,
    )

    member_ids = serializers.ListField(
        child=serializers.IntegerField(),
        allow_empty=False
    )

    def validate_name(self, value):
        value = value.strip()

        if not value:
            raise serializers.ValidationError(
                "Group name is required."
            )

        return value

    def validate_member_ids(self, value):
        # Remove duplicate IDs
        value = list(dict.fromkeys(value))

        if not value:
            raise serializers.ValidationError(
                "At least one member is required."
            )

        return value
