from datetime import datetime
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from library_management.models import Book, BookItem, BorrowRequest, BorrowRequestItem


# ==========================
#  BORROW: TẠO YÊU CẦU MƯỢN
# ==========================


@login_required
def create_borrow_request(request, book_id):
    """
    User đang đăng nhập tạo yêu cầu mượn 1 cuốn sách.
    - URL: /borrow/create/<book_id>/
    - Form POST gửi: requested_from, requested_to, quantity
    - Lưu: BorrowRequest (PENDING) + BorrowRequestItem
    """
    user = request.user
    book = get_object_or_404(Book, pk=book_id)

    if request.method == "POST":
        requested_from_str = request.POST.get("requested_from")
        requested_to_str = request.POST.get("requested_to")
        quantity_str = request.POST.get("quantity", "1")

        errors = []

        # --- Parse & kiểm tra ngày ---
        requested_from = None
        requested_to = None

        try:
            requested_from = datetime.strptime(requested_from_str, "%Y-%m-%d").date()
            requested_to = datetime.strptime(requested_to_str, "%Y-%m-%d").date()

            if requested_to < requested_from:
                errors.append("Ngày trả phải lớn hơn hoặc bằng ngày mượn.")

        except (TypeError, ValueError):
            errors.append("Định dạng ngày mượn/trả không hợp lệ.")

        # --- Kiểm tra số lượng ---
        try:
            quantity = int(quantity_str)
            if quantity <= 0:
                errors.append("Số lượng mượn phải lớn hơn 0.")
        except ValueError:
            errors.append("Số lượng mượn không hợp lệ.")

        # --- Kiểm tra tồn kho ---
        if not errors:
            available_count = BookItem.objects.filter(
                book=book,
                status=BookItem.Status.AVAILABLE,
            ).count()

            if quantity > available_count:
                errors.append(
                    f"Sách '{book.title}' chỉ còn {available_count} bản khả dụng."
                )

        # Nếu có lỗi → render lại form
        if errors:
            return render(
                request,
                "library_utilities/borrow_request_form.html",
                {
                    "book": book,
                    "errors": errors,
                    "old_data": {
                        "requested_from": requested_from_str,
                        "requested_to": requested_to_str,
                        "quantity": quantity_str,
                    },
                },
            )

        # --- Tạo BorrowRequest + BorrowRequestItem ---
        borrow_request = BorrowRequest.objects.create(
            user=user,
            requested_from=requested_from,
            requested_to=requested_to,
            status=BorrowRequest.Status.PENDING,
        )

        BorrowRequestItem.objects.create(
            request=borrow_request,
            book=book,
            quantity=quantity,
        )

        messages.success(
            request,
            "Đã tạo yêu cầu mượn, vui lòng chờ quản lý thư viện duyệt.",
        )

        return redirect("library_management:borrow_history")

    # GET: hiển thị form
    return render(
        request,
        "library_utilities/borrow_request_form.html",
        {
            "book": book,
        },
    )


# ==========================
#  BORROW: LỊCH SỬ MƯỢN
# ==========================


@login_required
def borrow_history(request):
    """
    Xem lịch sử yêu cầu mượn của chính user đang đăng nhập.
    - URL: /borrow/history/
    """
    user = request.user

    borrow_requests = (
        BorrowRequest.objects.filter(user=user)
        .order_by("-created_at")
        .prefetch_related("items__book", "items__book__publisher")
    )

    context = {
        "user": user,
        "borrow_requests": borrow_requests,
    }
    return render(request, "library_utilities/borrow_history.html", context)


# ==========================
#  Cancel: Huy yeu cau muon
# ==========================
@login_required
def cancel_borrow_request(request, request_id):
    """
    Hủy 1 yêu cầu mượn khi đang ở trạng thái PENDING.
    - Chỉ user sở hữu yêu cầu đó mới được hủy.
    - Sau khi hủy -> quay lại trang lịch sử mượn.
    """
    # Lấy request của đúng user đang đăng nhập
    borrow_request = get_object_or_404(
        BorrowRequest,
        pk=request_id,
        user=request.user,
    )

    # Chỉ cho hủy khi đang PENDING
    if borrow_request.status != BorrowRequest.Status.PENDING:
        messages.error(
            request,
            "Chỉ có thể hủy những yêu cầu đang ở trạng thái 'Đang chờ duyệt'.",
        )
        return redirect("library_management:borrow_history")

    if request.method == "POST":
        borrow_request.status = BorrowRequest.Status.CANCELLED
        borrow_request.save(update_fields=["status"])
        messages.success(request, "Đã hủy yêu cầu mượn sách.")
        return redirect("library_management:borrow_history")

    # Nếu là GET, có thể cho 1 trang confirm đơn giản
    return render(
        request,
        "library_management/cancel_confirm.html",
        {"borrow_request": borrow_request},
    )
