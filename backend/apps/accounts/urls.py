from django.urls import path

from .views import RegisterView,LoginView,ProfileView,UserSearchView,ListUsersView,VerifyEmailChangeOTPView,ProfileImageView,UserEmailVerifyView

from rest_framework_simplejwt.views import TokenRefreshView


urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("verify-email/",UserEmailVerifyView.as_view()),
    path("login/", LoginView.as_view(), name="login"),
    path("profile/", ProfileView.as_view(), name="profile"),
    path("profile/image/",ProfileImageView.as_view()),
    path("token/refresh/",TokenRefreshView.as_view(),),
    path("users/search/",UserSearchView.as_view()),
    path("users/",ListUsersView.as_view()),
    path("verify-email-change-otp/",VerifyEmailChangeOTPView.as_view(),name="verify-email-change-otp"),
]