from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from .serializers import RegisterSerializer,LoginSerializer,UserSerializer,EmailChangeSerializer
from .services import AuthService,ProfileService
from apps.accounts.models import User
from rest_framework.permissions import IsAuthenticated
from apps.chats.models import Conversation, ConversationMember
from django.db import transaction
from rest_framework.parsers import MultiPartParser, FormParser
from django.utils import timezone

from datetime import timedelta

class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):

        serializer = RegisterSerializer(
            data=request.data
        )

        serializer.is_valid(
            raise_exception=True
        )

        # Create user
        user = serializer.save()

        return Response(
            {
                "message": "User registered successfully.",
                "user": {
                    "id": user.id,
                    "email": user.email,
                    "username": user.username,
                },
            },
            status=status.HTTP_201_CREATED
        )

class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):

        serializer = LoginSerializer(data=request.data)

        serializer.is_valid(raise_exception=True)

        user = serializer.validated_data["user"]

        tokens = AuthService.get_tokens_for_user(user)

        return Response(
            {
                "message": "Login successful",
                "user": {
                    "id": user.id,
                    "email": user.email,
                    "username": user.username,
                },
                "tokens": tokens,
            },
            status=status.HTTP_200_OK
        )

class ProfileView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser,]

    def get(self, request):

        serializer = UserSerializer(request.user)

        return Response(
            {
                "user": serializer.data
            }
        )

    def patch(self, request):

        user = User.objects.get(
            id=request.user.id,
            is_active=True
        )

        # =====================================================
        # EMAIL CHANGE
        # =====================================================

        new_email = request.data.get("email")

        if new_email:

            serializer = EmailChangeSerializer(
                data={
                    "new_email": new_email
                },
                context={
                    "request": request
                }
            )

            serializer.is_valid(
                raise_exception=True
            )

            new_email = serializer.validated_data["new_email"]
            user.email = new_email
            user.save(update_fields=["email"])

            return Response(
                {
                    "message": "Email updated successfully.",
                    "email": user.email
                },
                status=status.HTTP_200_OK
            )

        # =====================================================
        # PROFILE UPDATE
        # =====================================================

        serializer = UserSerializer(
            user,
            data=request.data,
            partial=True,
            context={
                "request": request
            }
        )

        serializer.is_valid(
            raise_exception=True
        )

        # =====================================================
        # PROFILE IMAGE
        # =====================================================

        if "profile_image" in serializer.validated_data:

            new_image = serializer.validated_data.pop(
                "profile_image"
            )

            if new_image is None:

                ProfileService.remove_profile_image(
                    user
                )

            else:

                ProfileService.update_profile_image(
                    user,
                    new_image
                )

        # Save username / other fields
        serializer.save()

        user.refresh_from_db()

        response_serializer = UserSerializer(
            user,
            context={
                "request": request
            }
        )

        return Response(
            {
                "message": "Profile updated successfully.",
                "user": response_serializer.data
            },
            status=status.HTTP_200_OK
        ) 

    def delete(self, request):

        user = User.objects.get(
            id=request.user.id,
            is_active=True
        )
        if user.profile_image:
            ProfileService.delete_profile_image(
                user
            )

        user.delete()

        return Response(
            {
                "message": (
                    "Profile deleted successfully."
                )
            },
            status=status.HTTP_200_OK
        )

class ProfileImageView(APIView):

    permission_classes = [IsAuthenticated]

    def patch(self, request):

        user = User.objects.get(
            id=request.user.id,
            is_active=True
        )

        if not user.profile_image:
            return Response(
                {
                    "message": "Profile image doesn't exist."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        ProfileService.remove_profile_image(user)

        return Response(
            {
                "message": "Profile image removed successfully."
            },
            status=status.HTTP_200_OK
        )

class UserSearchView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        query = request.query_params.get("q", "").strip()

        # =====================================================
        # GET USERS ALREADY IN ONE-TO-ONE CHATS
        # =====================================================

        existing_chat_user_ids = (
            ConversationMember.objects
            .filter(
                conversation__conversation_type=
                    Conversation.ConversationType.ONE_TO_ONE,
                conversation__members__user=request.user,
                conversation__members__is_active=True,
                is_active=True,
            )
            .exclude(
                user=request.user
            )
            .values_list(
                "user_id",
                flat=True
            )
            .distinct()
        )

        # =====================================================
        # GET USERS WHO ARE NOT YET CHATTED
        # =====================================================

        users = (
            User.objects
            .filter(
                is_active=True,
            )
            .exclude(
                id=request.user.id
            )
            .exclude(
                id__in=existing_chat_user_ids
            )
            .order_by("username")
        )

        # =====================================================
        # SEARCH BY USERNAME
        # =====================================================

        if query:
            users = users.filter(
                username__icontains=query
            )

        # =====================================================
        # LIMIT RESULTS
        # =====================================================

        users = users[:50]

        data = [
            {
                "id": user.id,
                "username": user.username,
                "is_online": user.is_online,
                "last_seen": (
                    user.last_seen.isoformat()
                    if user.last_seen
                    else None
                ),
            }
            for user in users
        ]

        return Response(data)


class ListUsersView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        users = (
            User.objects
            .filter(is_active=True)
            .exclude(id=request.user.id)
            .order_by("username")
        )
        serializer = UserSerializer(users, many=True)
        return Response(serializer.data,status=status.HTTP_200_OK)

    
