from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from django.db.models import Q
from .serializers import RegisterSerializer,LoginSerializer,UserSerializer,EmailChangeSerializer
from .services import AuthService,ProfileService
from apps.accounts.models import User,EmailVerifyOTP,EmailVerify
from rest_framework.permissions import IsAuthenticated
from apps.chats.models import Conversation, ConversationMember
from django.db import transaction
from rest_framework.parsers import MultiPartParser, FormParser


from datetime import timedelta

from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status

from .serializers import RegisterSerializer
from .models import User, EmailVerify
from .services import AuthService


class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):

        serializer = RegisterSerializer(
            data=request.data
        )

        serializer.is_valid(
            raise_exception=True
        )

        email = serializer.validated_data["email"]

        # Generate OTP
        otp = AuthService.generate_otp()

        # Create user
        user = serializer.save()

        user.is_active = False
        user.save(update_fields=["is_active"])

        # OTP expiration time - 5 minutes
        expired_at = (
            timezone.now() +
            timedelta(minutes=5)
        )

        # Save OTP
        EmailVerify.objects.create(
            user=user,
            otp=otp,
            expired_at=expired_at
        )

        # Send OTP email
        AuthService.send_email_to_otp(
            email,
            otp
        )

        return Response(
            {
                "message": "User registered successfully. OTP sent to your email.",
                "user": {
                    "id": user.id,
                    "email": user.email,
                    "username": user.username,
                },
            },
            status=status.HTTP_201_CREATED
        )

class UserEmailVerifyView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):

        email = request.data.get("email")
        otp = request.data.get("otp")

        if not email:
            return Response(
                {
                    "message": "Email is required."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        if not otp:
            return Response(
                {
                    "message": "OTP is required."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            user = User.objects.get(
                email=email,
                is_verified=False
            )
        except User.DoesNotExist:
            return Response(
                {
                    "message": "User not found or email already verified."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        email_verify = (
            EmailVerify.objects
            .filter(user=user)
            .order_by("-created_at")
            .first()
        )

        if not email_verify:
            return Response(
                {
                    "message": "OTP not found."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        if email_verify.otp != otp:
            return Response(
                {
                    "message": "Enter valid OTP."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        if email_verify.expired_at < timezone.now():
            return Response(
                {
                    "message": "OTP expired."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        user.is_verified = True
        user.is_active = True

        user.save(
            update_fields=[
                "is_verified",
                "is_active"
            ]
        )

        email_verify.delete()

        return Response(
            {
                "message": "Email verified successfully."
            },
            status=status.HTTP_200_OK
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

            otp = AuthService.generate_otp()

            EmailVerifyOTP.objects.filter(
                user=user,
                is_verified=False
            ).update(
                is_verified=True
            )

            EmailVerifyOTP.objects.create(
                user=user,
                new_email=new_email,
                otp=otp
            )

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