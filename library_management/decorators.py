from django.contrib.auth.decorators import user_passes_test
from accounts.models import MemberProfile
from django.core.exceptions import RelatedObjectDoesNotExist


def admin_required(view_func):
    def check(user):
        try:
            return (
                user.is_authenticated and user.profile.role == MemberProfile.Role.ADMIN
            )
        except RelatedObjectDoesNotExist:
            return False

    decorated_view_func = user_passes_test(check, login_url="login")(view_func)
    return decorated_view_func
