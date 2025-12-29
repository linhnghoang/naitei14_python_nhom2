from django.urls import path
from .views.authentication import login_view
from .views.profile import profile_view
from .views.activation import signup_view, signup_done, activate_account

app_name = "accounts"

urlpatterns = [
    path("login/", login_view, name="login"),
    path("signup/", signup_view, name="signup"),
    path("signup/done/", signup_done, name="signup_done"),
    path("activate/<uidb64>/<token>/", activate_account, name="activate"),
    path("profile/", profile_view, name="profile"),
]
