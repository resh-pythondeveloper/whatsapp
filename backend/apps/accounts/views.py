from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from django.db.models import Q
from .serializers import RegisterSerializer,LoginSerializer,UserSerializer
from .services import AuthService
from apps.accounts.models import User
from rest_framework.permissions import IsAuthenticated
from apps.chats.models import Conversation, ConversationMember

class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):

        serializer = RegisterSerializer(data=request.data)

        serializer.is_valid(raise_exception=True)

        user = serializer.save()

        tokens = AuthService.get_tokens_for_user(user)

        return Response(
            {
                "message": "User registered successfully",
                "user": {
                    "id": user.id,
                    "email": user.email,
                    "username": user.username,
                },
                "tokens": tokens,
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

    def get(self, request):

        serializer = UserSerializer(request.user)

        return Response(
            {
                "user": serializer.data
            }
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
        # SEARCH BY USERNAME IF QUERY EXISTS
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