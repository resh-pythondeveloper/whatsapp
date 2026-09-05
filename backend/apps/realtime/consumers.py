import json
import logging
import asyncio
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone
from apps.chats.models import ConversationMember, Message,MessageReceipt,Conversation
from apps.realtime.services.presence_service import (
    PresenceService
)
from apps.realtime.services.typing_service import (
    TypingService
)
from apps.chats.service.message_cache_service import (
    MessageCacheService
)
from apps.chats.service.conversation_service import (
    ConversationService
)

from apps.chats.service.message_status_service import (
    MessageStatusService,
)
from apps.chats.service.chat_service import ChatService
logger = logging.getLogger(__name__)

class ChatConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        self.typing_timeout_task = None

        # Get authenticated user from JWT middleware
        self.user = self.scope["user"]

        # Reject unauthenticated users
        if self.user.is_anonymous:
            await self.close(code=4001)
            return

        # Get conversation UUID from URL
        self.conversation_id = str(
            self.scope["url_route"]["kwargs"]["conversation_id"]
        )

        # Validate conversation membership
        is_member = await self.validate_conversation_member()

        if not is_member:
            await self.close(code=4003)
            return

        # Typing service
        self.typing_service = TypingService()
        self.typing_timeout_task = None

        # Redis group name
        self.room_group_name = (
            f"conversation_{self.conversation_id}"
        )

        # Join Redis group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        # Accept WebSocket
        await self.accept()

        logger.info( "User %s connected to conversation %s", 
                    self.user.id, self.conversation_id, )

    async def disconnect(self, close_code):

        # Cancel automatic typing timeout task
        if getattr(self, "typing_timeout_task", None) is not None:

            self.typing_timeout_task.cancel()

            try:
                await self.typing_timeout_task
            except asyncio.CancelledError:
                pass

            self.typing_timeout_task = None

        # Stop typing if connected
        if (
            hasattr(self, "typing_service")
            and hasattr(self, "conversation_id")
            and hasattr(self, "user")
            and not self.user.is_anonymous
        ):
            try:

                state_changed = await self.typing_service.stop_typing(
                conversation_id=self.conversation_id,
                user_id=self.user.id,
            )

            # Notify other users
                if (state_changed
                    and hasattr(self, "room_group_name")
                ):

                    await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        "type": "typing_event",

                        "user_id": str(
                            self.user.id
                        ),

                        "is_typing": False,
                    }
                )
            except Exception: 
                logger.exception( "Failed to remove typing state for user %s", self.user.id, )

        # Remove from Redis conversation group
        if hasattr(self, "room_group_name"):

            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )

        logger.info( "User %s disconnected from conversation %s. Code: %s", 
                    getattr(self.user, "id", None), 
                    getattr(self, "conversation_id", None), 
                    close_code, )

    async def receive(self, text_data):

        try:
            data = json.loads(text_data)

        except json.JSONDecodeError:

            await self.send_error(
                "Invalid JSON format"
            )
            return

        action = data.get("action")

        if action == "message":

            await self.handle_message(
                data
            )
        elif action == "typing":

            await self.handle_typing(data)

        elif action == "delivered":

            await self.handle_delivered(
                data
            )

        elif action == "read":

            await self.handle_read(
                data
            )

        else:

            await self.send_error(
                "Invalid action"
            )

    async def typing_timeout(self):
        """
        Automatically stop typing after TYPING_TIMEOUT seconds
        if the user does not send another typing event.
        """

        try:
            await asyncio.sleep(
                self.typing_service.TYPING_TIMEOUT
            )

            state_changed = await (
                self.typing_service.stop_typing(
                    conversation_id=self.conversation_id,
                    user_id=self.user.id,
                )
            )

            if not state_changed:
                return

            # Notify other users that typing has stopped
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "typing_event",

                    "user_id": str(
                        self.user.id
                    ),

                    "is_typing": False,
                }
            )

            logger.info(
                "Automatic typing timeout for user %s "
                "in conversation %s",
                self.user.id,
                self.conversation_id,
            )

        except asyncio.CancelledError:
            # Task was cancelled because:
            # - user sent false
            # - user sent another true
            # - user sent a message
            # - user disconnected
            return

        except Exception:
            logger.exception(
                "Automatic typing timeout failed "
                "for user %s",
                self.user.id,
            )

    async def handle_typing(self, data):

        is_typing = data.get(
            "is_typing",
            False
        )
        if not isinstance(is_typing, bool):
            await self.send_error(
                "is_typing must be true or false"
            )
            return

        try:
            if is_typing:

                # Store temporary typing state in Redis
                state_changed =(await self.typing_service.start_typing(
                conversation_id=self.conversation_id,
                user_id=self.user.id,
            ))
                # Cancel previous timeout task
                if self.typing_timeout_task:

                    self.typing_timeout_task.cancel()

                    try:
                        await self.typing_timeout_task
                    except asyncio.CancelledError:
                        pass

                    self.typing_timeout_task = None

                # Start a new automatic timeout
                self.typing_timeout_task = asyncio.create_task(
                    self.typing_timeout()
                )

            else:
                # Cancel automatic timeout task
                if self.typing_timeout_task:

                    self.typing_timeout_task.cancel()

                    try:
                        await self.typing_timeout_task
                    except asyncio.CancelledError:
                        pass

                    self.typing_timeout_task = None

            # Remove typing state
                state_changed = (await self.typing_service.stop_typing(
                conversation_id=self.conversation_id,
                user_id=self.user.id,
            ))
        except Exception:
            logger.exception( "Typing service failed for user %s", 
                             self.user.id, )
            await self.send_error(
                 "Typing service is temporarily unavailable." 
                 )
            return

                
        if not state_changed:
            return

        # Broadcast typing event
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "typing_event",

                "user_id": str(
                    self.user.id
                ),

                "is_typing": is_typing,
            }
        )

    async def auto_stop_typing(self):

        try:

            # Wait for typing timeout
            await asyncio.sleep(
                self.typing_service.TYPING_TIMEOUT
            )

            logger.info(
                "Typing timeout reached for user %s",
                self.user.id,
            )

            # Remove Redis typing state
            state_changed = await self.typing_service.stop_typing(
                conversation_id=self.conversation_id,
                user_id=self.user.id,
            )

            if not state_changed:
                logger.info(
                    "Typing state already removed for user %s",
                    self.user.id,
                )
                return

            # Tell other users typing has stopped
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "typing_event",
                    "user_id": str(self.user.id),
                    "is_typing": False,
                }
            )

            logger.info(
                "Automatic typing false sent for user %s",
                self.user.id,
            )

        except asyncio.CancelledError:

            logger.info(
                "Typing timeout cancelled for user %s",
                self.user.id,
            )

        except Exception:

            logger.exception(
                "Automatic typing timeout failed for user %s",
                self.user.id,
            )

    async def typing_event(self, event):

        # Don't send typing event back to sender
        if str(self.user.id) == event["user_id"]:
            return

        await self.send(
            text_data=json.dumps(
                {
                    "type": "typing",

                    "data": {
                        "user_id": event["user_id"],

                        "is_typing": (
                            event["is_typing"]
                        ),
                    }
                }
            )
        )

    async def handle_message(self, data):

        message_content = data.get("message")

        if (
            not message_content
            or not isinstance(message_content, str)
            or not message_content.strip()
        ):
            await self.send_error(
                "Message cannot be empty"
            )
            return

        # Clear typing status
        # Stop typing when message is sent
        if self.typing_timeout_task:

            self.typing_timeout_task.cancel()

            self.typing_timeout_task = None

        try:
            state_changed = (
                await self.typing_service.stop_typing(
                    conversation_id=self.conversation_id,
                    user_id=self.user.id,
                )
            )

        # Broadcast only if user was actually typing
            if state_changed:

                await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "typing_event",

                    "user_id": str(
                        self.user.id
                    ),

                    "is_typing": False,
                }
            )
        except Exception:
            logger.exception( "Failed to stop typing before message." )

        # Save message to PostgreSQL
        try:
            message = await self.create_message(
                content=message_content.strip()
            )
        except Exception:
            logger.exception( "Failed to create message for user %s", 
                             self.user.id, )
            await self.send_error("Failed to send message.")
            return

        # Invalidate message cache
        try:
            await self.invalidate_message_cache()
        except Exception:
            logger.exception( "Failed to invalidate message cache for conversation %s", 
                             self.conversation_id, )

        # Broadcast through Redis
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "chat_message",

                "message_id": str(message.id),

                "conversation_id": str(
                    message.conversation_id
                ),

                "sender_id": str(
                    message.sender_id
                ),

                "content": message.content,

                "message_type": message.message_type,

                "status": message.status,

                "created_at": (
                    message.created_at.isoformat()
                ),
            }
        )
        # Update conversation list
        await self.broadcast_conversation_update()


    async def handle_delivered(self, data):

        message_id = data.get("message_id")

        if not message_id:

            await self.send_error(
                "message_id is required"
            )
            return

        result = await self.mark_delivered(
            message_id
        )

        if result is None: 
            await self.send_error( "Message not found." ) 
            return

        if not result["changed"]:
            return
    
        receipt = result["receipt"]

        overall_status = (
            result["overall_status"]
        )

        # Notify conversation members
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "message_status",

                "message_id": message_id,

                "user_id": str(self.user.id),

                "status": receipt.status,

                "overall_status": overall_status,

                "timestamp": (
                    receipt.delivered_at.isoformat()
                    if receipt.delivered_at
                    else None
                ),
            }
        )

    @database_sync_to_async
    def mark_delivered(self, message_id):

        try:

            message = Message.objects.get(
                id=message_id,
                conversation_id=self.conversation_id
            )
        except Message.DoesNotExist: 
            return None

            # Sender cannot mark own message delivered
        if message.sender_id == self.user.id:
            return None

        receipt, created = (
                MessageReceipt.objects.get_or_create(
                    message=message,
                    user=self.user,
                    defaults={
                        "status": (
                            MessageReceipt.ReceiptStatus.DELIVERED
                        ),
                        "delivered_at": timezone.now()
                    }
                )
            )
        changed = created

            # Existing receipt
        if not created:

                # Already delivered or read
            if receipt.status in [
                    MessageReceipt.ReceiptStatus.DELIVERED,
                    MessageReceipt.ReceiptStatus.READ,
                ]:
                return {
                        "receipt": receipt,
                        "overall_status": message.status,
                        "changed": False,
                    }

            receipt.status = (
                    MessageReceipt.ReceiptStatus.DELIVERED
                )

            receipt.delivered_at = (
                    receipt.delivered_at
                    or timezone.now()
                )

            receipt.save(
                    update_fields=[
                        "status",
                        "delivered_at",
                        "updated_at",
                    ]
                )

            changed = True

            # Recalculate overall message status
        overall_status = (
                MessageStatusService
                .update_message_status(
                    message.id
                )
            )

        return {
                "receipt": receipt,
                "overall_status": overall_status,
                "changed": changed,
            }


    async def chat_message(self, event):

        await self.send(
            text_data=json.dumps(
                {
                    "type": "message",

                    "data": {
                        "id": event["message_id"],
                        "conversation_id": event["conversation_id"],
                        "sender_id": event["sender_id"],
                        "content": event["content"],
                        "message_type": event["message_type"],
                        "status": event["status"],
                        "created_at": event["created_at"],
                    }
                }
            )
        )

    async def handle_read(self, data):

        message_id = data.get("message_id")

        if not message_id:
            await self.send_error("message_id is required")
            return

        # Mark all messages up to this message as READ
        result = await self.mark_messages_read(message_id)

        if result is None:
            await self.send_error("Message not found.")
            return

        # Update conversation read position and unread count
        read_state = await self.mark_conversation_read(message_id)

        # Broadcast status changes for all messages
        for message_data in result["messages"]:

            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "message_status",

                    "message_id": message_data["message_id"],

                    "user_id": str(self.user.id),

                    "status": message_data["status"],

                    "overall_status": message_data["overall_status"],

                    "timestamp": message_data["timestamp"],
                }
            )

        # Update unread count for current user
        await self.channel_layer.group_send(
            f"user_{self.user.id}",
            {
                "type": "conversation_update",

                "conversation": {
                    "conversation_id": self.conversation_id,

                    "unread_count": read_state["unread_count"],

                    "last_read_at": (
                        read_state["last_read_at"].isoformat()
                        if read_state["last_read_at"]
                        else None
                    ),
                },
            },
        )

    @database_sync_to_async
    def mark_messages_read(self, message_id):

        try:
            target_message = Message.objects.get(
                id=message_id,
                conversation_id=self.conversation_id,
            )

        except Message.DoesNotExist:
            return None

        # User must be a member
        is_member = ConversationMember.objects.filter(
            conversation_id=self.conversation_id,
            user=self.user,
            is_active=True,
        ).exists()

        if not is_member:
            return None

        # Only messages sent by OTHER users can be marked as read
        messages = (
            Message.objects
            .filter(
                conversation_id=self.conversation_id,
                created_at__lte=target_message.created_at,
            )
            .exclude(
                sender_id=self.user.id
            )
            .order_by("created_at")
        )

        updated_messages = []

        now = timezone.now()

        for message in messages:

            receipt, created = MessageReceipt.objects.get_or_create(
                message=message,
                user=self.user,
                defaults={
                    "status": MessageReceipt.ReceiptStatus.READ,
                    "delivered_at": now,
                    "read_at": now,
                },
            )

            changed = created

            # Existing receipt
            if not created:

                # Already read
                if receipt.status == MessageReceipt.ReceiptStatus.READ:
                    continue

                receipt.status = MessageReceipt.ReceiptStatus.READ

                if not receipt.delivered_at:
                    receipt.delivered_at = now

                receipt.read_at = now

                receipt.save(
                    update_fields=[
                        "status",
                        "delivered_at",
                        "read_at",
                        "updated_at",
                    ]
                )

                changed = True

            if not changed:
                continue

            # Recalculate overall message status
            overall_status = (
                MessageStatusService.update_message_status(
                    message.id
                )
            )

            updated_messages.append(
                {
                    "message_id": str(message.id),

                    "status": receipt.status,

                    "overall_status": overall_status,

                    "timestamp": (
                        receipt.read_at.isoformat()
                        if receipt.read_at
                        else None
                    ),
                }
            )

        return {
            "messages": updated_messages
        }


    @database_sync_to_async
    def mark_conversation_read(self, message_id):
        return ChatService.mark_conversation_as_read(
            conversation_id=self.conversation_id,
            user_id=self.user.id,
            message_id=message_id,
        )


    async def message_status(self, event):

        await self.send(
            text_data=json.dumps(
                {
                    "type": "message_status",

                    "data": {
                        "message_id": (
                            event["message_id"]
                        ),

                        "user_id": (
                            event["user_id"]
                        ),

                        "status": (
                            event["status"]
                        ),

                        # Overall message status
                        "overall_status": (
                            event.get(
                                "overall_status"
                            )
                        ),

                        "timestamp": (
                            event.get(
                                "timestamp"
                            )
                        ),
                    }
                }
            )
        )

    @database_sync_to_async
    def validate_conversation_member(self):

        return ConversationMember.objects.filter(
                conversation_id=self.conversation_id,
                user=self.user,
                is_active=True
            ).exists()
    
    @database_sync_to_async
    def create_message(self, content):
    
        return ChatService.send_message(
                user=self.user,
                conversation_id=self.conversation_id,
                content=content,
            )
    
    @database_sync_to_async
    def invalidate_message_cache(
            self,
        ):
        try:
    
            cache_service = MessageCacheService()
        
            cache_service.delete_conversation_cache(
                    self.conversation_id
                )
        except Exception as exc:
            print(f"Redis cache invalidation failed: {exc}")


    async def broadcast_conversation_update(self):
    
            member_ids = await (
                self.get_conversation_member_ids()
            )
    
            for user_id in member_ids:
    
                # Don't send conversation update to sender
                # optional — frontend can update locally
                if str(user_id) == str(self.user.id):
                    continue
    
                conversation_data = await (
                    self.get_conversation_summary(
                        user_id
                    )
                )
    
                await self.channel_layer.group_send(
                    f"user_{user_id}",
                    {
                        "type": "conversation_update",
    
                        "conversation": (
                            conversation_data
                        ),
                    }
                )
    
    @database_sync_to_async
    def get_conversation_member_ids(self):
    
        return list(
                ConversationMember.objects.filter(
                    conversation_id=self.conversation_id,
                    is_active=True,
                ).values_list(
                    "user_id",
                    flat=True
                )
            )
    
    @database_sync_to_async
    def get_conversation_summary(self,user_id,):
    
            return (
                ConversationService.get_conversation_summary(
                    conversation_id=self.conversation_id,
                    user_id=user_id,
                )
            )

    async def send_error(self, message):
    
        await self.send(
                text_data=json.dumps(
                    {
                        "type": "error",
                        "message": message
                    }
                )
            )

class PresenceConsumer(AsyncWebsocketConsumer):

    async def connect(self):

        self.user = self.scope["user"]

        # Reject unauthenticated users
        if self.user.is_anonymous:
            await self.close(code=4001)
            return

        # Personal user group
        self.user_group_name = (
            f"user_{self.user.id}"
        )

        # Join personal Redis group
        await self.channel_layer.group_add(
            self.user_group_name,
            self.channel_name
        )

        # Presence service
        self.presence_service = PresenceService()

        # Add WebSocket connection
        try:
            connection_count = (
                await self.presence_service.add_connection(
                    user_id=self.user.id,
                    connection_id=self.channel_name,
                )
            )
        except Exception:

            logger .exception( "Failed to add presence connection for user %s",
                              self.user.id, ) 
            await self.channel_layer.group_discard( self.user_group_name, self.channel_name, ) 
            await self.close(code=1011) 
            return

        # Accept WebSocket
        await self.accept()

        # Send current presence status of related users
        try:
            await self.send_initial_presence()
        except Exception: 
            logger.exception( "Failed to send initial presence for user %s", 
                             self.user.id, )

        logger.info( "User %s connected. Connections: %s", 
                    self.user.id, 
                    connection_count, )

        # Broadcast ONLINE only for first connection
        if connection_count == 1:
            try:

                await self.broadcast_presence(
                status="online"
            )
            except Exception: 
                logger.exception( "Failed to broadcast online status for user %s", 
                                 self.user.id, )

    async def disconnect(self, close_code):

        # Remove user from personal group
        if hasattr(self, "user_group_name"):

            await self.channel_layer.group_discard(
                self.user_group_name,
                self.channel_name
            )

        # Remove presence connection
        if (
            hasattr(self, "presence_service")
            and hasattr(self, "user")
            and not self.user.is_anonymous
        ):
            try:

                connection_count = (
                await self.presence_service.remove_connection(
                    user_id=self.user.id,
                    connection_id=self.channel_name,
                )
                )

                logger.info( "User %s disconnected. Connections remaining: %s", 
                        self.user.id, connection_count, )
            
                # Broadcast OFFLINE only for last connection
                if connection_count == 0:
                    last_seen = await self.update_last_seen()

                    await self.broadcast_presence(
                        status="offline",
                        last_seen=last_seen.isoformat(),
                    )
            except Exception: 
                logger.exception( "Failed to handle disconnect presence for user %s", 
                                 self.user.id, )

    # ============================================================
    # BROADCAST PRESENCE
    # ============================================================
    @database_sync_to_async
    def update_last_seen(self):
        last_seen = timezone.now()

        self.user.last_seen = last_seen

        self.user.save(
            update_fields=["last_seen"]
        )
        return last_seen

    
    async def broadcast_presence(self, status,last_seen=None,):

        user_ids = await self.get_related_user_ids()

        for user_id in user_ids:

            await self.channel_layer.group_send(
                f"user_{user_id}",
                {
                    "type": "presence_update",

                    "user_id": str(
                        self.user.id
                    ),

                    "status": status,
                    "last_seen": last_seen,
                }
            )

    # ============================================================
    # RECEIVE PRESENCE EVENT
    # ============================================================

    async def presence_update(self, event):

        await self.send(
            text_data=json.dumps(
                {
                    "type": "presence",

                    "data": {
                        "user_id": event["user_id"],

                        "status": event["status"],
                        "last_seen": event.get("last_seen"),
                    }
                }
            )
        )

    # ============================================================
    # GET USERS WHO SHARE CONVERSATIONS
    # ============================================================

    @database_sync_to_async
    def get_related_user_ids(self):

        return list(
            ConversationMember.objects.filter(
                conversation__members__user=self.user,
                conversation__members__is_active=True,
                is_active=True,
            )
            .exclude(
                user=self.user
            )
            .values_list(
                "user_id",
                flat=True
            )
            .distinct()
        )

    @database_sync_to_async
    def get_users_last_seen(self, user_ids):

        users = (
            self.user.__class__.objects
            .filter(id__in=user_ids)
            .values(
                "id",
                "last_seen"
            )
        )

        return {
            str(user["id"]): (
                user["last_seen"].isoformat()
                if user["last_seen"]
                else None
            )
            for user in users
        }

    async def send_initial_presence(self):

        user_ids = await self.get_related_user_ids()

        if not user_ids: 
            return

        last_seen_data = (await self.get_users_last_seen(
            user_ids
        ))

        for user_id in user_ids:
            try:

                is_online = await (
                self.presence_service.is_online(
                    user_id
                )
                )
            except Exception: 
                logger.exception( "Failed to check presence for user %s", 
                                 user_id, )
                 # Redis unavailable. 
                 # Don't assume the user is online. 
                is_online = False

            await self.send(
                text_data=json.dumps(
                    {
                        "type": "presence",

                        "data": {
                            "user_id": str(user_id),

                            "status": (
                                "online"
                                if is_online
                                else "offline"
                            ),
                            "last_seen": (
                                None
                                if is_online
                                else last_seen_data.get(
                                    str(user_id)
                                )
                            ),
                        }
                    }
                )
            )

    async def conversation_update(
        self,
        event,
    ):

        await self.send(
            text_data=json.dumps(
                {
                    "type": "conversation_update",

                    "data": event[
                        "conversation"
                    ],
                }
            )
        )

    