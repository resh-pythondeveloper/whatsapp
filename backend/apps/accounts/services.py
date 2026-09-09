from rest_framework_simplejwt.tokens import RefreshToken
import random
from django.core.mail import send_mail
from django.conf import settings
import os
from django.core.files.storage import default_storage
from django.db import transaction


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


class ProfileService:

    @staticmethod
    def update_profile_image(user, new_image):

        # Delete old image
        if user.profile_image:

            old_image_name = user.profile_image.name

            if old_image_name:
                default_storage.delete(old_image_name)

        # Save new image
        user.profile_image = new_image

        user.save(
            update_fields=[
                "profile_image",
                "updated_at",
            ]
        )

        return user

    @staticmethod
    def remove_profile_image(user):

        if not user.profile_image:
            return False

        image_name = user.profile_image.name

        if image_name:
            default_storage.delete(image_name)

        user.profile_image = None

        user.save(
            update_fields=[
                "profile_image",
                "updated_at",
            ]
        )

        return True