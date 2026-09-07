from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from django.db.models import Q
from .serializers import RegisterSerializer,LoginSerializer,UserSerializer,EmailChangeSerializer
from .services import AuthService
from apps.accounts.models import User,EmailVerifyOTP
from rest_framework.permissions import IsAuthenticated
from apps.chats.models import Conversation, ConversationMember
from django.db import transaction

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
    permission_classes = [IsAuthenticated]

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
    
            # Check whether email is being changed
            new_email = request.data.get("email")
    
            if new_email:
    
                serializer = EmailChangeSerializer(
                    data={"new_email": new_email},
                    context={"request": request}
                )
    
                serializer.is_valid(raise_exception=True)
    
                new_email = serializer.validated_data["new_email"]
    
                # Generate OTP
                otp = AuthService.generate_otp()
    
                # Optional: invalidate previous OTPs
                EmailVerifyOTP.objects.filter(
                    user=user,
                    is_verified=False
                ).update(is_verified=True)
    
                # Create new OTP
                EmailVerifyOTP.objects.create(
                    new_email=new_email,
                    user=user,
                    otp=otp
                )
    
                # Send OTP
                AuthService.send_email_to_otp(
                    new_email,
                    otp
                )
    
                return Response(
                    {
                        "message": "OTP sent to your new email address.",
                        "email": new_email
                    },
                    status=status.HTTP_200_OK
                )
    
            # Update other allowed fields
            serializer = UserSerializer(
                user,
                data=request.data,
                partial=True
            )
    
            serializer.is_valid(raise_exception=True)
            serializer.save()
    
            return Response(
                serializer.data,
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

    

class VerifyEmailChangeOTPView(APIView):

    permission_classes = [IsAuthenticated]

    def post(self, request):

        user = User.objects.get(
            id=request.user.id,
            is_active=True
        )

        otp = request.data.get("otp")

        if not otp:
            return Response(
                {
                    "message": "OTP is required."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        otp_obj = EmailVerifyOTP.objects.filter(
            user=user,
            is_verified=False
        ).order_by("-created_at").first()

        if not otp_obj:
            return Response(
                {
                    "message": "OTP not found or already verified."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        if otp_obj.is_expired():
            otp_obj.delete()
            return Response(
                {
                    "message": "OTP has expired."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        if str(otp_obj.otp).strip() != str(otp).strip():
            return Response(
                {"message": "Invalid OTP."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Update email
        with transaction.atomic():

            if (
                User.objects
                .filter(
                    email=otp_obj.new_email
                )
                .exclude(
                    id=user.id
                )
                .exists()
            ):

                return Response(
                    {
                        "message":
                            "This email is already registered."
                    },

                    status=status.HTTP_400_BAD_REQUEST
                )

            user.email = otp_obj.new_email
            user.save(
                update_fields=[
                    "email",
                ]
            )

            otp_obj.delete()

        return Response(
            {
                "message": "Email address updated successfully.",
                "email": user.email
            },
            status=status.HTTP_200_OK
        )