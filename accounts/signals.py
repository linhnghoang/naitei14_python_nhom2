from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings
from allauth.account.signals import user_signed_up
from allauth.socialaccount.signals import social_account_added

from .models import MemberProfile
from .enums import Status, Role


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_member_profile(sender, instance, created, **kwargs):
    """Create MemberProfile when a new user is created."""
    if created:
        if not hasattr(instance, "profile"):
            MemberProfile.objects.create(
                user=instance,
                full_name=instance.get_full_name() or instance.username,
                status=Status.ACTIVE,
                role=Role.USER,
            )


@receiver(user_signed_up)
def populate_profile_on_signup(sender, request, user, **kwargs):
    """Update profile with social account data when user signs up."""
    sociallogin = kwargs.get("sociallogin")
    if sociallogin:
        extra_data = sociallogin.account.extra_data
        profile, created = MemberProfile.objects.get_or_create(
            user=user,
            defaults={
                "full_name": extra_data.get("name", user.username),
                "status": Status.ACTIVE,
                "role": Role.USER,
                "avatar_url": extra_data.get("picture", ""),
            },
        )
        if not created:
            profile.full_name = extra_data.get("name", profile.full_name)
            profile.avatar_url = extra_data.get("picture", profile.avatar_url)
            profile.save()


@receiver(social_account_added)
def update_profile_on_social_connect(sender, request, sociallogin, **kwargs):
    """Update profile when a social account is connected to existing user."""
    user = sociallogin.user
    extra_data = sociallogin.account.extra_data

    profile, created = MemberProfile.objects.get_or_create(
        user=user,
        defaults={
            "full_name": extra_data.get("name", user.username),
            "status": Status.ACTIVE,
            "role": Role.USER,
            "avatar_url": extra_data.get("picture", ""),
        },
    )
    if not created and not profile.avatar_url:
        profile.avatar_url = extra_data.get("picture", "")
        profile.save()
