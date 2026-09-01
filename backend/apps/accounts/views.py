from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny

from .serializers import RegisterSerializer,LoginSerializer,UserSerializer
from .services import AuthService


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