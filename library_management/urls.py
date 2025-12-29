from django.urls import path
from .views import (
    home,
    admin_dashboard,
    create_borrow_request,
    borrow_history,
    cancel_borrow_request,
)


app_name = "library_management"

urlpatterns = [
    path("", home, name="home"),
    path("admin/dashboard/", admin_dashboard, name="admin_dashboard"),
    # Borrow
    path(
        "borrow/create/<int:book_id>/",
        create_borrow_request,
        name="create_borrow_request",
    ),
    path("borrow/history/", borrow_history, name="borrow_history"),
    path(
        "borrow/cancel/<int:request_id>/",
        cancel_borrow_request,
        name="cancel_borrow_request",
    ),
]
