from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from datetime import timedelta

# =========================
#  AUTHORS / PUBLISHERS / CATEGORIES
# =========================


class Author(models.Model):
    name = models.CharField(_("Name"), max_length=255)
    biography = models.TextField(_("Biography"), blank=True, null=True)
    birth_date = models.DateField(_("Birth date"), blank=True, null=True)
    death_date = models.DateField(_("Death date"), blank=True, null=True)
    created_at = models.DateTimeField(_("Created at"), auto_now_add=True)

    class Meta:
        db_table = "authors"
        verbose_name = _("Author")
        verbose_name_plural = _("Authors")

    def __str__(self):
        return self.name


class Publisher(models.Model):
    name = models.CharField(_("Name"), max_length=255, unique=True)
    description = models.TextField(_("Description"), blank=True, null=True)
    founded_year = models.SmallIntegerField(_("Founded year"), blank=True, null=True)
    website = models.CharField(_("Website"), max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(_("Created at"), auto_now_add=True)

    class Meta:
        db_table = "publishers"
        verbose_name = _("Publisher")
        verbose_name_plural = _("Publishers")

    def __str__(self):
        return self.name


class Category(models.Model):
    name = models.CharField(_("Name"), max_length=255)
    slug = models.SlugField(_("Slug"), max_length=255, unique=True)
    description = models.TextField(_("Description"), blank=True, null=True)
    parent = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="children",
        verbose_name=_("Parent category"),
    )

    class Meta:
        db_table = "categories"
        verbose_name = _("Category")
        verbose_name_plural = _("Categories")

    def __str__(self):
        return self.name


# =========================
#  BOOKS
# =========================


class Book(models.Model):
    title = models.CharField(_("Title"), max_length=500)
    description = models.TextField(_("Description"), blank=True, null=True)
    isbn13 = models.CharField(_("ISBN-13"), max_length=13, unique=True, blank=True, null=True)
    publish_year = models.SmallIntegerField(_("Publish year"), blank=True, null=True)
    pages = models.IntegerField(_("Pages"), blank=True, null=True)
    cover_url = models.CharField(_("Cover URL"), max_length=500, blank=True, null=True)
    language_code = models.CharField(_("Language code"), max_length=16, blank=True, null=True)
    publisher = models.ForeignKey(
        Publisher,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="books",
        verbose_name=_("Publisher"),
    )
    created_at = models.DateTimeField(_("Created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated at"), auto_now=True)

    authors = models.ManyToManyField(
        Author,
        through="BookAuthor",
        related_name="books",
        verbose_name=_("Authors"),
    )
    categories = models.ManyToManyField(
        Category,
        through="BookCategory",
        related_name="books",
        verbose_name=_("Categories"),
    )

    class Meta:
        db_table = "books"
        verbose_name = _("Book")
        verbose_name_plural = _("Books")

    def __str__(self):
        return self.title


class BookAuthor(models.Model):
    book = models.ForeignKey(Book, on_delete=models.CASCADE, verbose_name=_("Book"))
    author = models.ForeignKey(Author, on_delete=models.CASCADE, verbose_name=_("Author"))
    author_order = models.SmallIntegerField(_("Author order"), default=1)

    class Meta:
        db_table = "book_authors"
        unique_together = ("book", "author")
        verbose_name = _("Book Author")
        verbose_name_plural = _("Book Authors")

    def __str__(self):
        return f"{self.book} - {self.author} (#{self.author_order})"


class BookCategory(models.Model):
    book = models.ForeignKey(Book, on_delete=models.CASCADE, verbose_name=_("Book"))
    category = models.ForeignKey(Category, on_delete=models.CASCADE, verbose_name=_("Category"))

    class Meta:
        db_table = "book_categories"
        unique_together = ("book", "category")
        verbose_name = _("Book Category")
        verbose_name_plural = _("Book Categories")

    def __str__(self):
        return f"{self.book} - {self.category}"


class BookItem(models.Model):
    class Status(models.TextChoices):
        AVAILABLE = "AVAILABLE", _("Available")
        RESERVED = "RESERVED", _("Reserved")
        LOANED = "LOANED", _("Loaned")
        LOST = "LOST", _("Lost")
        DAMAGED = "DAMAGED", _("Damaged")

    book = models.ForeignKey(
        Book,
        on_delete=models.CASCADE,
        related_name="items",
        verbose_name=_("Book"),
    )
    barcode = models.CharField(_("Barcode"), max_length=100, unique=True)
    status = models.CharField(
        _("Status"),
        max_length=20,
        choices=Status.choices,
        default=Status.AVAILABLE,
    )
    location_code = models.CharField(_("Location code"), max_length=100, blank=True, null=True)
    created_at = models.DateTimeField(_("Created at"), auto_now_add=True)

    class Meta:
        db_table = "book_items"
        verbose_name = _("Book Item")
        verbose_name_plural = _("Book Items")

    def __str__(self):
        return f"{self.book.title} - {self.barcode}"


# =========================
#  SOCIAL (FAVORITES, FOLLOW, COMMENTS, RATINGS)
# =========================


class UserFavorite(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="favorite_books",
        verbose_name=_("User"),
    )
    book = models.ForeignKey(
        Book,
        on_delete=models.CASCADE,
        related_name="favorited_by",
        verbose_name=_("Book"),
    )
    created_at = models.DateTimeField(_("Created at"), auto_now_add=True)

    class Meta:
        db_table = "user_favorites"
        unique_together = ("user", "book")
        verbose_name = _("User Favorite")
        verbose_name_plural = _("User Favorites")

    def __str__(self):
        return f"{self.user} ❤ {self.book}"


class FollowAuthor(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="followed_authors",
        verbose_name=_("User"),
    )
    author = models.ForeignKey(
        Author,
        on_delete=models.CASCADE,
        related_name="followers",
        verbose_name=_("Author"),
    )
    created_at = models.DateTimeField(_("Created at"), auto_now_add=True)

    class Meta:
        db_table = "follow_authors"
        unique_together = ("user", "author")
        verbose_name = _("Follow Author")
        verbose_name_plural = _("Follow Authors")

    def __str__(self):
        return f"{self.user} follows {self.author}"


class FollowPublisher(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="followed_publishers",
        verbose_name=_("User"),
    )
    publisher = models.ForeignKey(
        Publisher,
        on_delete=models.CASCADE,
        related_name="followers",
        verbose_name=_("Publisher"),
    )
    created_at = models.DateTimeField(_("Created at"), auto_now_add=True)

    class Meta:
        db_table = "follow_publishers"
        unique_together = ("user", "publisher")
        verbose_name = _("Follow Publisher")
        verbose_name_plural = _("Follow Publishers")

    def __str__(self):
        return f"{self.user} follows {self.publisher}"


class BookComment(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="book_comments",
        verbose_name=_("User"),
    )
    book = models.ForeignKey(
        Book,
        on_delete=models.CASCADE,
        related_name="comments",
        verbose_name=_("Book"),
    )
    content = models.TextField(_("Content"))
    is_deleted = models.BooleanField(_("Is deleted"), default=False)
    created_at = models.DateTimeField(_("Created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated at"), auto_now=True)

    class Meta:
        db_table = "book_comments"
        verbose_name = _("Book Comment")
        verbose_name_plural = _("Book Comments")

    def __str__(self):
        return f"Comment by {self.user} on {self.book}"


class BookRating(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="book_ratings",
        verbose_name=_("User"),
    )
    book = models.ForeignKey(
        Book,
        on_delete=models.CASCADE,
        related_name="ratings",
        verbose_name=_("Book"),
    )
    rating = models.PositiveSmallIntegerField(
        _("Rating"),
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    review = models.TextField(_("Review"), blank=True, null=True)
    created_at = models.DateTimeField(_("Created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated at"), auto_now=True)

    class Meta:
        db_table = "book_ratings"
        verbose_name = _("Book Rating")
        verbose_name_plural = _("Book Ratings")
        constraints = [
            models.UniqueConstraint(
                fields=["user", "book"],
                name="uq_user_book_rating",
            )
        ]

    def __str__(self):
        return f"{self.user} rated {self.book} = {self.rating}"


# =========================
#  BORROW REQUESTS & LOANS
# =========================


class BorrowRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", _("Pending")
        APPROVED = "APPROVED", _("Approved")
        REJECTED = "REJECTED", _("Rejected")
        RETURNED = "RETURNED", _("Returned")
        LOST = "LOST", _("Lost")
        OVERDUE = "OVERDUE", _("Overdue")

    class Duration(models.IntegerChoices):
        ONE_WEEK = 7, _("1 Week")
        TWO_WEEKS = 14, _("2 Weeks")
        ONE_MONTH = 30, _("1 Month")
        THREE_MONTHS = 90, _("3 Months")
        SIX_MONTHS = 180, _("6 Months")

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="borrow_requests",
        verbose_name=_("User"),
    )
    book_item = models.ForeignKey(
        BookItem,
        on_delete=models.CASCADE,
        related_name="borrow_requests",
        null=True,
        blank=True,
        verbose_name=_("Book item"),
    )
    requested_from = models.DateField(_("Requested from"), default=timezone.now)
    duration = models.IntegerField(_("Duration"), choices=Duration.choices, default=Duration.ONE_WEEK)
    requested_to = models.DateField(_("Requested to"), blank=True, null=True)
    status = models.CharField(
        _("Status"),
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    admin = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="processed_requests",
        verbose_name=_("Admin"),
    )
    decision_at = models.DateTimeField(_("Decision at"), blank=True, null=True)
    created_at = models.DateTimeField(_("Created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated at"), auto_now=True)

    class Meta:
        db_table = "borrow_requests"
        verbose_name = _("Borrow Request")
        verbose_name_plural = _("Borrow Requests")

    def __str__(self):
        return _("Request #%(id)s by %(user)s") % {"id": self.id, "user": self.user}

    def clean(self):
        # For new records
        if not self.pk:
            if self.status not in [
                self.Status.PENDING,
                self.Status.APPROVED,
                self.Status.REJECTED,
            ]:
                raise ValidationError(
                    _("New requests can only be Pending, Approved, or Rejected.")
                )
            # Validate book_item availability for new approved requests
            if self.status == self.Status.APPROVED:
                if not self.book_item:
                    raise ValidationError(_("Book item is required for approval."))
                if self.book_item.status != BookItem.Status.AVAILABLE:
                    raise ValidationError(
                        _("Book item %(barcode)s is not available (Status: %(status)s).") % {
                            "barcode": self.book_item.barcode,
                            "status": self.book_item.get_status_display()
                        }
                    )
            return

        # For existing records - fetch old_instance once
        old_instance = BorrowRequest.objects.get(pk=self.pk)
        old_status = old_instance.status

        # Prevent editing if already returned
        if old_status == self.Status.RETURNED:
            raise ValidationError(
                _("Cannot edit a request that has already been returned.")
            )

        # If status was APPROVED, only allow transition to
        # RETURNED, LOST, or OVERDUE
        if old_status == self.Status.APPROVED:
            if self.status not in [
                self.Status.APPROVED,
                self.Status.RETURNED,
                self.Status.LOST,
                self.Status.OVERDUE,
            ]:
                raise ValidationError(
                    _("Approved requests can only be changed to Returned, Lost, or Overdue.")
                )

        # Validate approval requirements
        if self.status == self.Status.APPROVED:
            if not self.book_item:
                raise ValidationError(_("Book item is required for approval."))
            # Only check availability if transitioning to APPROVED
            if old_status != self.Status.APPROVED:
                if self.book_item.status != BookItem.Status.AVAILABLE:
                    raise ValidationError(
                        _("Book item %(barcode)s is not available (Status: %(status)s).") % {
                            "barcode": self.book_item.barcode,
                            "status": self.book_item.get_status_display()
                        }
                    )

        # Validate return requirements
        if self.status == self.Status.RETURNED:
            if old_status not in [
                self.Status.APPROVED,
                self.Status.OVERDUE,
                self.Status.LOST,
            ]:
                raise ValidationError(
                    _("Only approved, overdue, or lost requests can be returned.")
                )

    def save(self, *args, **kwargs):
        old_status = None
        if self.pk:
            try:
                old_instance = BorrowRequest.objects.get(pk=self.pk)
                old_status = old_instance.status
            except BorrowRequest.DoesNotExist:
                pass

        if not self.requested_from:
            self.requested_from = timezone.now().date()

        if self.duration:
            self.requested_to = self.requested_from + timedelta(days=self.duration)

        if self.status == self.Status.APPROVED and (
            not old_status or old_status != self.Status.APPROVED
        ):
            self.decision_at = timezone.now()

        super().save(*args, **kwargs)

        if self.book_item:
            if (
                self.status == self.Status.APPROVED
                and old_status != self.Status.APPROVED
            ):
                self.book_item.status = BookItem.Status.LOANED
                self.book_item.save()

            elif (
                self.status == self.Status.RETURNED
                and old_status != self.Status.RETURNED
            ):
                self.book_item.status = BookItem.Status.AVAILABLE
                self.book_item.save()

            elif self.status == self.Status.LOST and old_status != self.Status.LOST:
                self.book_item.status = BookItem.Status.LOST
                self.book_item.save()


class BorrowRequestItem(models.Model):
    request = models.ForeignKey(
        BorrowRequest,
        on_delete=models.CASCADE,
        related_name="items",
        verbose_name=_("Request"),
    )
    book = models.ForeignKey(
        Book,
        on_delete=models.CASCADE,
        related_name="requested_items",
        verbose_name=_("Book"),
    )
    quantity = models.SmallIntegerField(_("Quantity"), default=1)

    class Meta:
        db_table = "borrow_request_items"
        verbose_name = _("Borrow Request Item")
        verbose_name_plural = _("Borrow Request Items")

    def __str__(self):
        return f"{self.book} x{self.quantity} (req #{self.request_id})"


class Loan(models.Model):
    class Status(models.TextChoices):
        BORROWED = "BORROWED", _("Borrowed")
        RETURNED = "RETURNED", _("Returned")
        OVERDUE = "OVERDUE", _("Overdue")

    request = models.ForeignKey(
        BorrowRequest,
        on_delete=models.CASCADE,
        related_name="loans",
        verbose_name=_("Request"),
    )
    request_item = models.ForeignKey(
        BorrowRequestItem,
        on_delete=models.CASCADE,
        related_name="loans",
        verbose_name=_("Request item"),
    )
    book_item = models.ForeignKey(
        BookItem,
        on_delete=models.PROTECT,
        related_name="loans",
        verbose_name=_("Book item"),
    )
    approved_from = models.DateField(_("Approved from"))
    due_date = models.DateField(_("Due date"))
    returned_at = models.DateField(_("Returned at"), blank=True, null=True)
    status = models.CharField(
        _("Status"),
        max_length=20,
        choices=Status.choices,
        default=Status.BORROWED,
    )
    created_at = models.DateTimeField(_("Created at"), auto_now_add=True)

    class Meta:
        db_table = "loans"
        verbose_name = _("Loan")
        verbose_name_plural = _("Loans")

    def __str__(self):
        return f"Loan #{self.id} - {self.book_item}"


# =========================
#  MAIL QUEUE
# =========================


class MailQueue(models.Model):
    class MailType(models.TextChoices):
        BORROW_ACCEPTED = "BORROW_ACCEPTED", _("Borrow accepted")
        BORROW_REJECTED = "BORROW_REJECTED", _("Borrow rejected")
        ACCOUNT_ACTIVATION = "ACCOUNT_ACTIVATION", _("Account activation")
        RETURN_REMINDER_ADMIN = "RETURN_REMINDER_ADMIN", _("Return reminder admin")

    class MailStatus(models.TextChoices):
        QUEUED = "QUEUED", _("Queued")
        SENT = "SENT", _("Sent")
        FAILED = "FAILED", _("Failed")
        CANCELLED = "CANCELLED", _("Cancelled")

    type = models.CharField(
        _("Type"),
        max_length=50,
        choices=MailType.choices,
    )
    to_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="mail_user_targets",
        verbose_name=_("To user"),
    )
    to_admin = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="mail_admin_targets",
        verbose_name=_("To admin"),
    )
    to_email = models.CharField(_("To email"), max_length=255, blank=True, null=True)
    subject = models.CharField(_("Subject"), max_length=255)
    body = models.TextField(_("Body"))
    reference_type = models.CharField(_("Reference type"), max_length=50, blank=True, null=True)
    reference_id = models.BigIntegerField(_("Reference ID"), blank=True, null=True)
    scheduled_at = models.DateTimeField(_("Scheduled at"), auto_now_add=True)
    sent_at = models.DateTimeField(_("Sent at"), blank=True, null=True)
    status = models.CharField(
        _("Status"),
        max_length=20,
        choices=MailStatus.choices,
        default=MailStatus.QUEUED,
    )
    error = models.TextField(_("Error"), blank=True, null=True)

    class Meta:
        db_table = "mail_queue"
        verbose_name = _("Mail Queue")
        verbose_name_plural = _("Mail Queue")

    def __str__(self):
        return f"[{self.type}] {self.subject}"
