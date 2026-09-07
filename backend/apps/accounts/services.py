from rest_framework_simplejwt.tokens import RefreshToken
import random
from django.core.mail import send_mail
from django.conf import settings



class AuthService:

    @staticmethod
    def get_tokens_for_user(user):
        refresh = RefreshToken.for_user(user)

        return {
            "refresh": str(refresh),
            "access": str(refresh.access_token),
        }

    @staticmethod
    def generate_otp():
        return str(random.randint(100000, 999999))

    @staticmethod
    def send_email_to_otp(email,otp):
        send_mail(
            subject="Verify your email address",
            message=f"""
    Your OTP for verifying your email address is:

    {otp}

    This OTP is valid for 5 minutes.

    If you did not request this change, please ignore this email.
    """,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=False,
        )