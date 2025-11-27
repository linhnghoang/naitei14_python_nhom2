from django.db import models
from django.conf import settings

# =========================
#  AUTHORS / PUBLISHERS / CATEGORIES
# =========================


class Author(models.Model):
    name = models.CharField(max_length=255)
    biography = models.TextField(blank=True, null=True)
    birth_date = models.DateField(blank=True, null=True)
    death_date = models.DateField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "authors"

    def __str__(self):
        return self.name


class Publisher(models.Model):
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True, null=True)
    founded_year = models.SmallIntegerField(blank=True, null=True)
    website = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "publishers"

    def __str__(self):
        return self.name


class Category(models.Model):
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True)
    description = models.TextField(blank=True, null=True)
    parent = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="children",
    )

    class Meta:
        db_table = "categories"

    def __str__(self):
        return self.name


# =========================
#  BOOKS
# =========================


class Book(models.Model):
    title = models.CharField(max_length=500)
    description = models.TextField(blank=True, null=True)
    isbn13 = models.CharField(max_length=13, unique=True, blank=True, null=True)
    publish_year = models.SmallIntegerField(blank=True, null=True)
    pages = models.IntegerField(blank=True, null=True)
    cover_url = models.CharField(max_length=500, blank=True, null=True)
    language_code = models.CharField(max_length=16, blank=True, null=True)
    publisher = models.ForeignKey(
        Publisher,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="books",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    authors = models.ManyToManyField(
        Author,
        through="BookAuthor",
        related_name="books",
    )
    categories = models.ManyToManyField(
        Category,
        through="BookCategory",
        related_name="books",
    )

    class Meta:
        db_table = "books"

    def __str__(self):
        return self.title


class BookAuthor(models.Model):
    book = models.ForeignKey(Book, on_delete=models.CASCADE)
    author = models.ForeignKey(Author, on_delete=models.CASCADE)
    author_order = models.SmallIntegerField(default=1)

    class Meta:
        db_table = "book_authors"
        unique_together = ("book", "author")

    def __str__(self):
        return f"{self.book} - {self.author} (#{self.author_order})"


class BookCategory(models.Model):
    book = models.ForeignKey(Book, on_delete=models.CASCADE)
    category = models.ForeignKey(Category, on_delete=models.CASCADE)

    class Meta:
        db_table = "book_categories"
        unique_together = ("book", "category")

    def __str__(self):
        return f"{self.book} - {self.category}"


class BookItem(models.Model):
    class Status(models.TextChoices):
        AVAILABLE = "AVAILABLE", "Available"
        RESERVED = "RESERVED", "Reserved"
        LOANED = "LOANED", "Loaned"
        LOST = "LOST", "Lost"
        DAMAGED = "DAMAGED", "Damaged"

    book = models.ForeignKey(
        Book,
        on_delete=models.CASCADE,
        related_name="items",
    )
    barcode = models.CharField(max_length=100, unique=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.AVAILABLE,
    )
    location_code = models.CharField(max_length=100, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "book_items"

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
    )
    book = models.ForeignKey(
        Book,
        on_delete=models.CASCADE,
        related_name="favorited_by",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "user_favorites"
        unique_together = ("user", "book")

    def __str__(self):
        return f"{self.user} ❤ {self.book}"


class FollowAuthor(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="followed_authors",
    )
    author = models.ForeignKey(
        Author,
        on_delete=models.CASCADE,
        related_name="followers",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "follow_authors"
        unique_together = ("user", "author")

    def __str__(self):
        return f"{self.user} follows {self.author}"


class FollowPublisher(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="followed_publishers",
    )
    publisher = models.ForeignKey(
        Publisher,
        on_delete=models.CASCADE,
        related_name="followers",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "follow_publishers"
        unique_together = ("user", "publisher")

    def __str__(self):
        return f"{self.user} follows {self.publisher}"


class BookComment(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="book_comments",
    )
    book = models.ForeignKey(
        Book,
        on_delete=models.CASCADE,
        related_name="comments",
    )
    content = models.TextField()
    is_deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "book_comments"

    def __str__(self):
        return f"Comment by {self.user} on {self.book}"


class BookRating(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="book_ratings",
    )
    book = models.ForeignKey(
        Book,
        on_delete=models.CASCADE,
        related_name="ratings",
    )
    rating = models.PositiveSmallIntegerField()  # TINYINT
    review = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "book_ratings"
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
        PENDING = "PENDING", "Pending"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"
        CANCELLED = "CANCELLED", "Cancelled"
        EXPIRED = "EXPIRED", "Expired"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="borrow_requests",
    )
    requested_from = models.DateField()
    requested_to = models.DateField()
    status = models.CharField(
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
    )
    decision_at = models.DateTimeField(blank=True, null=True)
    rejection_reason = models.TextField(blank=True, null=True)
    cancelled_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "borrow_requests"

    def __str__(self):
        return f"Request #{self.id} by {self.user}"


class BorrowRequestItem(models.Model):
    request = models.ForeignKey(
        BorrowRequest,
        on_delete=models.CASCADE,
        related_name="items",
    )
    book = models.ForeignKey(
        Book,
        on_delete=models.CASCADE,
        related_name="requested_items",
    )
    quantity = models.SmallIntegerField(default=1)

    class Meta:
        db_table = "borrow_request_items"

    def __str__(self):
        return f"{self.book} x{self.quantity} (req #{self.request_id})"


class Loan(models.Model):
    class Status(models.TextChoices):
        BORROWED = "BORROWED", "Borrowed"
        RETURNED = "RETURNED", "Returned"
        OVERDUE = "OVERDUE", "Overdue"

    request = models.ForeignKey(
        BorrowRequest,
        on_delete=models.CASCADE,
        related_name="loans",
    )
    request_item = models.ForeignKey(
        BorrowRequestItem,
        on_delete=models.CASCADE,
        related_name="loans",
    )
    book_item = models.ForeignKey(
        BookItem,
        on_delete=models.PROTECT,  # tương đương NO ACTION
        related_name="loans",
    )
    approved_from = models.DateField()
    due_date = models.DateField()
    returned_at = models.DateField(blank=True, null=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.BORROWED,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "loans"

    def __str__(self):
        return f"Loan #{self.id} - {self.book_item}"


# =========================
#  MAIL QUEUE
# =========================


class MailQueue(models.Model):
    class MailType(models.TextChoices):
        BORROW_ACCEPTED = "BORROW_ACCEPTED", "Borrow accepted"
        BORROW_REJECTED = "BORROW_REJECTED", "Borrow rejected"
        ACCOUNT_ACTIVATION = "ACCOUNT_ACTIVATION", "Account activation"
        RETURN_REMINDER_ADMIN = "RETURN_REMINDER_ADMIN", "Return reminder admin"

    class MailStatus(models.TextChoices):
        QUEUED = "QUEUED", "Queued"
        SENT = "SENT", "Sent"
        FAILED = "FAILED", "Failed"
        CANCELLED = "CANCELLED", "Cancelled"

    type = models.CharField(
        max_length=50,
        choices=MailType.choices,
    )
    to_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="mail_user_targets",
    )
    to_admin = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="mail_admin_targets",
    )
    to_email = models.CharField(max_length=255, blank=True, null=True)
    subject = models.CharField(max_length=255)
    body = models.TextField()
    reference_type = models.CharField(max_length=50, blank=True, null=True)
    reference_id = models.BigIntegerField(blank=True, null=True)
    scheduled_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(blank=True, null=True)
    status = models.CharField(
        max_length=20,
        choices=MailStatus.choices,
        default=MailStatus.QUEUED,
    )
    error = models.TextField(blank=True, null=True)

    class Meta:
        db_table = "mail_queue"

    def __str__(self):
        return f"[{self.type}] {self.subject}"
