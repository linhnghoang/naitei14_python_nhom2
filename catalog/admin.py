from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.db import models
from django.forms import Textarea
from .models import (
    Author,
    Publisher,
    Category,
    Book,
    BookAuthor,
    BookCategory,
    BookItem,
)


# Custom Admin Site Configuration
admin.site.site_header = "Library Management System"
admin.site.site_title = "Library Admin"
admin.site.index_title = "Welcome to Library Management"


# Inline classes for better relationship management
class BookAuthorInline(admin.TabularInline):
    model = BookAuthor
    extra = 1
    autocomplete_fields = ["author"]


class BookCategoryInline(admin.TabularInline):
    model = BookCategory
    extra = 1
    autocomplete_fields = ["category"]


class BookItemInline(admin.TabularInline):
    model = BookItem
    extra = 1
    readonly_fields = ["created_at"]


@admin.register(Author)
class AuthorAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "birth_date",
        "death_date",
        "books_count",
        "created_at",
    ]
    list_filter = ["birth_date", "death_date", "created_at"]
    search_fields = ["name", "biography"]
    readonly_fields = ["created_at"]
    date_hierarchy = "created_at"
    list_per_page = 25

    fieldsets = (
        ("Basic Information", {"fields": ("name", "biography")}),
        (
            "Dates",
            {
                "fields": ("birth_date", "death_date", "created_at"),
                "classes": ("collapse",),
            },
        ),
    )

    def books_count(self, obj):
        count = obj.books.count()
        url = reverse("admin:catalog_book_changelist") + f"?authors__id__exact={obj.id}"
        return format_html('<a href="{}">{} books</a>', url, count)

    books_count.short_description = "Books"


@admin.register(Publisher)
class PublisherAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "founded_year",
        "website_link",
        "books_count",
        "created_at",
    ]
    list_filter = ["founded_year", "created_at"]
    search_fields = ["name", "description"]
    readonly_fields = ["created_at"]
    date_hierarchy = "created_at"
    list_per_page = 25
    fieldsets = (
        ("Basic Information", {"fields": ("name", "description")}),
        (
            "Additional Info",
            {
                "fields": ("founded_year", "website", "created_at"),
                "classes": ("collapse",),
            },
        ),
    )

    def website_link(self, obj):
        if obj.website:
            return format_html(
                '<a href="{}" target="_blank">{}</a>', obj.website, obj.website
            )
        return "-"

    website_link.short_description = "Website"

    def books_count(self, obj):
        count = obj.books.count()
        url = (
            reverse("admin:catalog_book_changelist") + f"?publisher__id__exact={obj.id}"
        )
        return format_html('<a href="{}">{} books</a>', url, count)

    books_count.short_description = "Books"


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "parent", "books_count", "children_count"]
    list_filter = ["parent"]
    search_fields = ["name", "description", "slug"]
    prepopulated_fields = {"slug": ("name",)}
    list_per_page = 25

    fieldsets = (
        ("Basic Information", {"fields": ("name", "slug", "description")}),
        (
            "Hierarchy",
            {
                "fields": ("parent",),
            },
        ),
    )

    def books_count(self, obj):
        count = obj.books.count()
        url = (
            reverse("admin:catalog_book_changelist")
            + f"?categories__id__exact={obj.id}"
        )
        return format_html('<a href="{}">{} books</a>', url, count)

    books_count.short_description = "Books"

    def children_count(self, obj):
        count = obj.children.count()
        return f"{count} subcategories"

    children_count.short_description = "Subcategories"


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = [
        "title",
        "publisher",
        "publish_year",
        "pages",
        "isbn13",
        "language_code",
        "items_count",
        "created_at",
    ]
    list_filter = [
        "publisher",
        "publish_year",
        "language_code",
        "created_at",
        "categories",
    ]
    search_fields = ["title", "description", "isbn13"]
    readonly_fields = ["created_at", "updated_at"]
    date_hierarchy = "created_at"
    list_per_page = 25
    autocomplete_fields = ["publisher"]
    inlines = [BookAuthorInline, BookCategoryInline, BookItemInline]

    fieldsets = (
        ("Basic Information", {"fields": ("title", "description", "isbn13")}),
        (
            "Publication Details",
            {
                "fields": (
                    "publisher",
                    "publish_year",
                    "pages",
                    "language_code",
                )
            },
        ),
        ("Media", {"fields": ("cover_url",), "classes": ("collapse",)}),
        (
            "Timestamps",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    formfield_overrides = {
        models.TextField: {"widget": Textarea(attrs={"rows": 4, "cols": 80})},
    }

    def items_count(self, obj):
        return obj.items.count()

    items_count.short_description = "Items"


@admin.register(BookItem)
class BookItemAdmin(admin.ModelAdmin):
    list_display = [
        "book_title",
        "barcode",
        "status_colored",
        "location_code",
        "created_at",
    ]
    list_filter = ["status", "location_code", "created_at"]
    search_fields = ["book__title", "barcode"]
    readonly_fields = ["created_at"]
    autocomplete_fields = ["book"]
    list_per_page = 25

    fieldsets = (
        ("Book Information", {"fields": ("book",)}),
        ("Item Details", {"fields": ("barcode", "status", "location_code")}),
        ("Timestamps", {"fields": ("created_at",), "classes": ("collapse",)}),
    )

    def book_title(self, obj):
        return obj.book.title

    book_title.short_description = "Book"

    def status_colored(self, obj):
        colors = {
            "AVAILABLE": "green",
            "RESERVED": "orange",
            "LOANED": "blue",
            "LOST": "red",
            "DAMAGED": "purple",
        }
        color = colors.get(obj.status, "black")
        return format_html(
            '<span style="color: {};">{}</span>',
            color,
            obj.get_status_display(),
        )

    status_colored.short_description = "Status"


# Register the through models for direct management if needed
@admin.register(BookAuthor)
class BookAuthorAdmin(admin.ModelAdmin):
    list_display = ["book", "author", "author_order"]
    list_filter = ["author_order"]
    search_fields = ["book__title", "author__name"]
    autocomplete_fields = ["book", "author"]
    list_per_page = 25


@admin.register(BookCategory)
class BookCategoryAdmin(admin.ModelAdmin):
    list_display = ["book", "category"]
    search_fields = ["book__title", "category__name"]
    autocomplete_fields = ["book", "category"]
    list_per_page = 25
