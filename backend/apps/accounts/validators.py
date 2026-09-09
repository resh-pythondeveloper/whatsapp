from rest_framework import serializers


ALLOWED_IMAGE_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/jpg"
}

MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5 MB


def validate_profile_image(image):

    # -----------------------------
    # File size validation
    # -----------------------------

    if image.size > MAX_IMAGE_SIZE:
        raise serializers.ValidationError(
            "Profile image size must not exceed 5 MB."
        )

    # -----------------------------
    # Content type validation
    # -----------------------------

    if image.content_type not in ALLOWED_IMAGE_TYPES:
        raise serializers.ValidationError(
            "Only JPG, JPEG, PNG, and WEBP images are allowed."
        )

    # -----------------------------
    # Basic filename validation
    # -----------------------------

    if not image.name:
        raise serializers.ValidationError(
            "Invalid image file."
        )

    return image