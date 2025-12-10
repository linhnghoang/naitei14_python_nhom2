from django.contrib import admin, messages
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
    BorrowRequest,
)


# Custom Admin Site Configuration
admin.site.site_header = "Library Management System"
admin.site.site_title = "Library Admin"
admin.site.index_title = "Welcome to Library Management"


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "parent", "books_count", "children_count"]
    list_filter = ["parent"]
    search_fields = ["name", "description", "slug"]
    prepopulated_fields = {"slug": ("name",)}
    list_per_page = 25
    ordering = ["name"]

    # Add actions for bulk operations
    actions = ["make_parent_categories", "clear_parent_categories"]

    fieldsets = (
        ("Basic Information", {"fields": ("name", "slug", "description")}),
        (
            "Hierarchy",
            {
                "fields": ("parent",),
                "description": (
                    "Select a parent category to create a "
                    "subcategory hierarchy."
                ),
            },
        ),
    )

    def books_count(self, obj):
        count = obj.books.count()
        return format_html(
            '<span style="color: #007cba; font-weight: bold;">{} books</span>', count
        )

    books_count.short_description = "Books"
    books_count.admin_order_field = "books_count"

    def children_count(self, obj):
        count = obj.children.count()
        if count > 0:
            return format_html(
                '<span style="color: blue; font-weight: bold;">{} subcategories</span>',
                count,
            )
        return "No subcategories"

    children_count.short_description = "Subcategories"
    children_count.admin_order_field = "children_count"

    def get_queryset(self, request):
        """Optimize queryset with prefetch_related for better performance."""
        queryset = super().get_queryset(request)
        return queryset.select_related("parent").prefetch_related("children", "books")

    def save_model(self, request, obj, form, change):
        """Custom save logic to prevent circular parent-child relationships."""
        # Prevent circular relationships
        if obj.parent and obj.pk:
            # Check if the parent is a descendant of this category
            parent = obj.parent
            while parent:
                if parent.pk == obj.pk:
                    from django.core.exceptions import ValidationError

                    raise ValidationError("Cannot set parent to a descendant category.")
                parent = parent.parent
        super().save_model(request, obj, form, change)

    @admin.action(description="Clear parent category (make top-level)")
    def clear_parent_categories(self, request, queryset):
        """Action to make selected categories top-level by clearing their parent."""
        count = queryset.update(parent=None)
        self.message_user(
            request,
            f"Successfully cleared parent for {count} categories.",
            level="success",
        )

    @admin.action(description="Set as subcategories of first selected")
    def make_parent_categories(self, request, queryset):
        """Action to set the first selected category as parent for others."""
        categories = list(queryset)
        if len(categories) < 2:
            self.message_user(
                request,
                (
                    "Please select at least 2 categories (first will be "
                    "parent, others will become subcategories)."
                ),
                level="warning",
            )
            return

        parent_category = categories[0]
        children = categories[1:]

        # Prevent circular relationships
        for child in children:
            temp_parent = parent_category.parent
            while temp_parent:
                if temp_parent.pk == child.pk:
                    self.message_user(
                        request,
                        (
                            f"Cannot set {parent_category.name} as parent "
                            f"for {child.name} - would create circular "
                            f"relationship."
                        ),
                        level="error",
                    )
                    return
                temp_parent = temp_parent.parent

        # Update the children
        for child in children:
            child.parent = parent_category
            child.save()

        self.message_user(
            request,
            (
                f"Successfully set {parent_category.name} as parent for "
                f"{len(children)} categories."
            ),
            level="success",
        )


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


@admin.register(BorrowRequest)
class BorrowRequestAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "book_item",
        "status",
        "requested_from",
        "duration",
        "requested_to",
        "admin",
    )
    list_filter = ("status", "requested_from", "requested_to")
    search_fields = (
        "user__username",
        "user__email",
        "book_item__barcode",
        "book_item__book__title",
    )
    autocomplete_fields = ["book_item"]
    actions = ["return_books", "mark_books_as_lost"]
    exclude = ("decision_at", "requested_to")
    readonly_fields = ("requested_from",)

    def has_delete_permission(self, request, obj=None):
        return False

    def get_readonly_fields(self, request, obj=None):
        if obj:
            if obj.status == BorrowRequest.Status.RETURNED:
                return [f.name for f in self.model._meta.fields]
            if obj.status == BorrowRequest.Status.APPROVED:
                return [f.name for f in self.model._meta.fields if f.name != "status"]
        return list(self.readonly_fields) + ["admin"]

    def save_model(self, request, obj, form, change):
        obj.admin = request.user
        super().save_model(request, obj, form, change)

    @admin.action(description="Return selected books")
    def return_books(self, request, queryset):
        updated_count = 0
        for borrow_request in queryset:
            if borrow_request.status in [
                BorrowRequest.Status.APPROVED,
                BorrowRequest.Status.OVERDUE,
                BorrowRequest.Status.LOST,
            ]:
                borrow_request.status = BorrowRequest.Status.RETURNED
                borrow_request.save()
                updated_count += 1
        self.message_user(
            request, f"{updated_count} books returned successfully.", messages.SUCCESS
        )

    @admin.action(description="Mark selected books as Lost")
    def mark_books_as_lost(self, request, queryset):
        updated_count = 0
        for borrow_request in queryset:
            if borrow_request.status in [
                BorrowRequest.Status.APPROVED,
                BorrowRequest.Status.OVERDUE,
            ]:
                borrow_request.status = BorrowRequest.Status.LOST
                borrow_request.save()
                updated_count += 1
        self.message_user(
            request, f"{updated_count} books marked as lost.", messages.SUCCESS
        )

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if not obj:  # Creating a new object
            field = form.base_fields["status"]
            allowed_statuses = [
                BorrowRequest.Status.PENDING,
                BorrowRequest.Status.APPROVED,
                BorrowRequest.Status.REJECTED,
            ]
            field.choices = [
                (k, v) for k, v in BorrowRequest.Status.choices if k in allowed_statuses
            ]
        return form
