from django.shortcuts import render, redirect
from django.contrib.auth import login
from django.contrib.auth.forms import AuthenticationForm


def login_view(request):
    next_url = request.GET.get("next") or request.POST.get("next")

    if request.method == "POST":
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)

            if next_url:
                return redirect(next_url)

            if user.is_superuser:
                return redirect("library_management:admin_dashboard")

            return redirect("library_management:home")

    else:
        form = AuthenticationForm(request)

    return render(request, "registration/login.html", {"form": form, "next": next_url})
