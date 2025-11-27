from django.shortcuts import render, redirect
from django.contrib.auth import login
from django.core.mail import send_mail
from django.urls import reverse
from django.contrib.auth.models import User
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.contrib.auth.tokens import default_token_generator
from django.conf import settings

from ..forms import SignUpForm


def signup_view(request):
    if request.method == "POST":
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.is_active = False
            user.save()
            send_activation_email(request, user)
            return redirect("accounts:signup_done")
    else:
        form = SignUpForm()

    return render(request, "accounts/signup.html", {"form": form})


def send_activation_email(request, user):
    uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)

    activation_url = reverse("accounts:activate", args=[uidb64, token])
    activation_link = request.build_absolute_uri(activation_url)

    subject = "Kích hoạt tài khoản trên Library Management"
    message = (
        f"Xin chào {user.username},\n\n"
        f"Vui lòng nhấp vào liên kết bên dưới để kích hoạt tài khoản của bạn:\n"
        f"{activation_link}\n\n"
        f"Nếu bạn không đăng ký tài khoản, vui lòng bỏ qua email này.\n"
    )

    send_mail(
        subject, message, settings.DEFAULT_FROM_EMAIL, [user.email], fail_silently=False
    )


def signup_done(request):
    return render(request, "accounts/signup_done.html")


def activate_account(request, uidb64, token):
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user is not None and default_token_generator.check_token(user, token):
        user.is_active = True
        user.save()
        login(request, user)
        return render(request, "accounts/activation_success.html", {"user": user})
    else:
        return render(request, "accounts/activation_invalid.html")
