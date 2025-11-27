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
