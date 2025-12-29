"""
Helper functions for admin views.
"""
from django.utils import timezone
from django.utils.translation import gettext as _


def get_pagination_params(request, default_page=1, default_page_size=20, max_page_size=100):
    """
    Safely extract and validate pagination parameters from request.

    Returns tuple of (page, page_size) with validated values.
    """
    try:
        page = int(request.GET.get("page", default_page))
        if page < 1:
            page = default_page
    except (ValueError, TypeError):
        page = default_page

    try:
        page_size = int(request.GET.get("page_size", default_page_size))
        if page_size < 1:
            page_size = default_page_size
        elif page_size > max_page_size:
            page_size = max_page_size
    except (ValueError, TypeError):
        page_size = default_page_size

    return page, page_size


def time_ago(dt):
    """
    Return a human-readable relative time like '5m ago'.

    Handles both naive and aware datetimes by converting naive values
    into the current timezone before subtraction.
    """
    if not dt:
        return "-"

    # Normalize dt to an aware datetime to avoid naive/aware subtraction errors
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.get_current_timezone())

    now = timezone.now()
    delta = now - dt
    seconds = int(delta.total_seconds())

    if seconds < 60:
        return _("%(count)ss ago") % {"count": seconds}

    minutes = seconds // 60
    if minutes < 60:
        return _("%(count)sm ago") % {"count": minutes}

    hours = minutes // 60
    if hours < 24:
        return _("%(count)sh ago") % {"count": hours}

    days = hours // 24
    return _("%(count)sd ago") % {"count": days}
