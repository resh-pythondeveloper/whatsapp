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
        ]


class ConversationSerializer(serializers.ModelSerializer):
    members = ConversationMemberSerializer(
        many=True,
        read_only=True
    )

    created_by = ChatUserSerializer(
        read_only=True
    )

    class Meta:
        model = Conversation
        fields = [
            "id",
            "conversation_type",
            "name",
            "created_by",
            "members",
            "created_at",
            "updated_at",
        ]


class MessageSerializer(serializers.ModelSerializer):
    sender = ChatUserSerializer(read_only=True)

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
    content = serializers.CharField()

class CreateOneToOneConversationSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()


class CreateGroupConversationSerializer(serializers.Serializer):
    name = serializers.CharField(
        max_length=255
    )

    member_ids = serializers.ListField(
        child=serializers.IntegerField(),
        allow_empty=False
    )