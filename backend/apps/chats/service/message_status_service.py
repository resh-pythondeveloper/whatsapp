from django.db import transaction

from apps.chats.models import (
    ConversationMember,
    Message,
    MessageReceipt,
)


class MessageStatusService:

    @staticmethod
    @transaction.atomic
    def update_message_status(message_id):

        try:
            message = (
                Message.objects
                .select_for_update()
                .get(id=message_id)
            )

        except Message.DoesNotExist:
            return None

        # Get all active recipients except sender
        recipient_ids = list(
            ConversationMember.objects.filter(
                conversation=message.conversation,
                is_active=True,
            )
            .exclude(
                user=message.sender
            )
            .values_list(
                "user_id",
                flat=True
            )
        )

        # No recipients
        if not recipient_ids:
            return message.status

        # Get receipts for recipients
        receipts = MessageReceipt.objects.filter(
            message=message,
            user_id__in=recipient_ids,
        )

        delivered_count = receipts.filter(
            status__in=[
                MessageReceipt.ReceiptStatus.DELIVERED,
                MessageReceipt.ReceiptStatus.READ,
            ]
        ).count()

        read_count = receipts.filter(
            status=MessageReceipt.ReceiptStatus.READ
        ).count()

        total_recipients = len(recipient_ids)

        # =====================================
        # STATUS AGGREGATION
        # =====================================

        new_status = Message.MessageStatus.SENT

        # All recipients read
        if read_count == total_recipients:

            new_status = (
                Message.MessageStatus.READ
            )

        # All recipients received message
        elif delivered_count == total_recipients:

            new_status = (
                Message.MessageStatus.DELIVERED
            )

        # Update only when changed
        if message.status != new_status:

            message.status = new_status

            message.save(
                update_fields=[
                    "status",
                    "updated_at",
                ]
            )

        return new_status