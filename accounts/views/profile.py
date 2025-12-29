from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from ..forms import ProfileForm


@login_required
def profile_view(request):
    if request.method == "POST":
        form = ProfileForm(request.POST, instance=request.user)
        updated = form.is_valid()
        if updated:
            form.save()
    else:
        form = ProfileForm(instance=request.user)
        updated = False

    return render(request, "accounts/profile.html", {"form": form, "updated": updated})
