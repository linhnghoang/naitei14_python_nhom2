from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required


@login_required
def admin_dashboard(request):
    if not (
        request.user.is_superuser
        or (hasattr(request.user, "profile") and request.user.profile.is_admin)
    ):
        return redirect("library_management:home")

    return render(
        request,
        "library_management/admin_dashboard.html",
        {"active_section": "dashboard"},
    )
