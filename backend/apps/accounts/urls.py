from django.urls import path

from .views import RegisterView,LoginView,ProfileView,UserSearchView,ListUsersView

from rest_framework_simplejwt.views import TokenRefreshView


urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("login/", LoginView.as_view(), name="login"),
    path("profile/", ProfileView.as_view(), name="profile"),
    path("token/refresh/",TokenRefreshView.as_view(),),
    path("users/search/",UserSearchView.as_view()),
    path("users/",ListUsersView.as_view())
]