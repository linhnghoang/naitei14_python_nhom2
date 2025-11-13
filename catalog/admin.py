from django.contrib import admin, messages
from django.utils.html import format_html
from django.urls import reverse
from django.db import models
from django.forms import Textarea
from .models import (
    Author,
    Category,
    Publisher,
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


# Inline classes for better relationship management
class BookAuthorInline(admin.TabularInline):
    model = BookAuthor
    extra = 1
    autocomplete_fields = ["author"]
    verbose_name = "Author"
    verbose_name_plural = "Authors"
    fields = ("author", "author_order")

    def get_extra(self, request, obj=None, **kwargs):
        """Only show extra forms when creating new books."""
        if obj:  # If editing existing book
            return 0
        return 1


class BookCategoryInline(admin.TabularInline):
    model = BookCategory
    extra = 1
    autocomplete_fields = ["category"]
    verbose_name = "Category"
    verbose_name_plural = "Categories"

    def get_extra(self, request, obj=None, **kwargs):
        """Only show extra forms when creating new books."""
        if obj:  # If editing existing book
            return 0
        return 1


class BookItemInline(admin.TabularInline):
    model = BookItem
    extra = 1
    readonly_fields = ["created_at"]
    verbose_name = "Book Item"
    verbose_name_plural = "Book Items"
    fields = ("barcode", "status", "location_code", "created_at")

    def get_extra(self, request, obj=None, **kwargs):
        """Only show extra forms when creating new books."""
        if obj:  # If editing existing book
            return 0
        return 1


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = [
        "title",
        "get_authors",
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
        "authors",
    ]
    search_fields = ["title", "description", "isbn13", "authors__name"]
    readonly_fields = ["created_at", "updated_at"]
    date_hierarchy = "created_at"
    list_per_page = 25
    autocomplete_fields = ["publisher"]
    inlines = [BookAuthorInline, BookCategoryInline, BookItemInline]
    ordering = ["-created_at"]

    # Add actions for bulk operations
    actions = [
        "clear_publisher",
        "clear_cover_url",
        "set_language_english",
        "duplicate_selected_books",
    ]

    fieldsets = (
        (
            "Basic Information",
            {
                "fields": ("title", "description", "isbn13"),
                "description": "Enter the book's basic information.",
            },
        ),
        (
            "Publication Details",
            {
                "fields": (
                    "publisher",
                    "publish_year",
                    "pages",
                    "language_code",
                ),
                "description": "Details about the book's publication.",
            },
        ),
        (
            "Media",
            {
                "fields": ("cover_url",),
                "classes": ("collapse",),
                "description": "Optional cover image URL.",
            },
        ),
        (
            "Timestamps",
            {
                "fields": ("created_at", "updated_at"),
                "classes": ("collapse",),
                "description": "System-generated timestamps.",
            },
        ),
    )

    formfield_overrides = {
        models.TextField: {"widget": Textarea(attrs={"rows": 4, "cols": 80})},
    }

    def get_authors(self, obj):
        """Display authors with their order."""
        authors = obj.bookauthor_set.select_related("author").order_by("author_order")
        if not authors.exists():
            return format_html('<span style="color: #666;">No authors</span>')

        author_list = []
        for book_author in authors:
            author_name = book_author.author.name
            if len(authors) > 1:  # Show order number if multiple authors
                author_list.append(f"{book_author.author_order}. {author_name}")
            else:
                author_list.append(author_name)

        return format_html(
            '<span style="color: #007cba;">{}</span>', ", ".join(author_list)
        )

    get_authors.short_description = "Authors"
    get_authors.admin_order_field = "authors__name"

    def items_count(self, obj):
        """Display count of book items."""
        count = obj.items.count()
        if count > 0:
            return format_html(
                '<span style="color: #007cba; font-weight: bold;">{} items</span>',
                count,
            )
        return format_html('<span style="color: #666;">No items</span>')

    items_count.short_description = "Items"
    items_count.admin_order_field = "items__count"

    def get_queryset(self, request):
        """Optimize queryset with select_related and prefetch_related."""
        queryset = super().get_queryset(request)
        return queryset.select_related("publisher").prefetch_related(
            "authors", "categories", "items", "bookauthor_set__author"
        )

    def save_model(self, request, obj, form, change):
        """Custom save logic with validation."""
        # Validate ISBN-13 format if provided
        if obj.isbn13:
            isbn = obj.isbn13.replace("-", "").replace(" ", "")
            if len(isbn) != 13 or not isbn.isdigit():
                from django.contrib import messages

                messages.warning(
                    request, "ISBN-13 should be 13 digits. Please verify the format."
                )

        # Validate publish year
        from django.utils import timezone

        current_year = timezone.now().year
        if obj.publish_year and obj.publish_year > current_year + 1:
            from django.contrib import messages

            messages.warning(
                request,
                f"Publish year {obj.publish_year} is in the future. "
                f"Please verify this is correct.",
            )

        # Validate pages count
        if obj.pages and obj.pages <= 0:
            from django.contrib import messages

            messages.error(request, "Number of pages must be positive.")
            return

        super().save_model(request, obj, form, change)

        # Show success message with additional info
        if not change:  # New book
            from django.contrib import messages

            messages.success(
                request,
                f"Book '{obj.title}' has been created successfully. "
                f"You can now add authors and categories using the "
                f"sections below.",
            )

    @admin.action(description="Clear publisher for selected books")
    def clear_publisher(self, request, queryset):
        """Action to clear publisher for selected books."""
        count = queryset.update(publisher=None)
        self.message_user(
            request,
            f"Successfully cleared publisher for {count} books.",
            level="success",
        )

    @admin.action(description="Clear cover URL for selected books")
    def clear_cover_url(self, request, queryset):
        """Action to clear cover URL for selected books."""
        count = queryset.update(cover_url="")
        self.message_user(
            request,
            f"Successfully cleared cover URL for {count} books.",
            level="success",
        )

    @admin.action(description="Set language to English for selected books")
    def set_language_english(self, request, queryset):
        """Action to set language to English for selected books."""
        count = queryset.update(language_code="en")
        self.message_user(
            request,
            f"Successfully set language to English for {count} books.",
            level="success",
        )

    @admin.action(description="Duplicate selected books")
    def duplicate_selected_books(self, request, queryset):
        """Action to duplicate selected books."""
        from django.utils import timezone

        duplicated_count = 0

        for book in queryset:
            # Create new book instance
            new_book = Book.objects.create(
                title=f"{book.title} (Copy)",
                description=book.description,
                isbn13=None,  # Clear ISBN to avoid uniqueness conflict
                publish_year=book.publish_year,
                pages=book.pages,
                cover_url=book.cover_url,
                language_code=book.language_code,
                publisher=book.publisher,
            )

            # Copy authors
            for book_author in book.bookauthor_set.all():
                BookAuthor.objects.create(
                    book=new_book,
                    author=book_author.author,
                    author_order=book_author.author_order,
                )

            # Copy categories
            for book_category in book.bookcategory_set.all():
                BookCategory.objects.create(
                    book=new_book, category=book_category.category
                )

            duplicated_count += 1

        self.message_user(
            request,
            f"Successfully duplicated {duplicated_count} books.",
            level="success",
        )


@admin.register(BookAuthor)
class BookAuthorAdmin(admin.ModelAdmin):
    list_display = ["book", "author", "author_order"]
    list_filter = ["author_order", "author"]
    search_fields = ["book__title", "author__name"]
    autocomplete_fields = ["book", "author"]
    list_per_page = 25
    ordering = ["book__title", "author_order"]

    fieldsets = (
        (
            "Relationship",
            {
                "fields": ("book", "author"),
                "description": "Select the book and author for this relationship.",
            },
        ),
        (
            "Order",
            {
                "fields": ("author_order",),
                "description": "Specify the order of this author for the "
                "book (for multiple authors).",
            },
        ),
    )

    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        return super().get_queryset(request).select_related("book", "author")


@admin.register(BookCategory)
class BookCategoryAdmin(admin.ModelAdmin):
    list_display = ["book", "category"]
    list_filter = ["category"]
    search_fields = ["book__title", "category__name"]
    autocomplete_fields = ["book", "category"]
    list_per_page = 25
    ordering = ["book__title", "category__name"]

    fieldsets = (
        (
            "Relationship",
            {
                "fields": ("book", "category"),
                "description": "Select the book and category for this relationship.",
            },
        ),
    )

    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        return super().get_queryset(request).select_related("book", "category")


@admin.register(BookItem)
class BookItemAdmin(admin.ModelAdmin):
    list_display = [
        "book_title",
        "barcode",
        "status_colored",
        "location_code",
        "created_at",
    ]
    list_filter = ["status", "location_code", "created_at", "book"]
    search_fields = ["book__title", "barcode", "book__isbn13"]
    readonly_fields = ["created_at"]
    autocomplete_fields = ["book"]
    list_per_page = 25
    ordering = ["-created_at"]

    # Add actions for bulk operations
    actions = [
        "mark_as_available",
        "mark_as_lost",
        "mark_as_damaged",
        "clear_location",
        "generate_barcodes",
    ]

    fieldsets = (
        (
            "Book Information",
            {
                "fields": ("book",),
                "description": "Select the book this item belongs to.",
            },
        ),
        (
            "Item Details",
            {
                "fields": ("barcode", "status", "location_code"),
                "description": "Details specific to this physical book item.",
            },
        ),
        (
            "Timestamps",
            {
                "fields": ("created_at",),
                "classes": ("collapse",),
                "description": "System-generated timestamps.",
            },
        ),
    )

    def book_title(self, obj):
        """Display the book title with a link to the book."""
        return format_html(
            '<a href="{}" style="color: #007cba;">{}</a>',
            reverse("admin:catalog_book_change", args=[obj.book.pk]),
            obj.book.title,
        )

    book_title.short_description = "Book"
    book_title.admin_order_field = "book__title"

    def status_colored(self, obj):
        """Display status with color coding."""
        colors = {
            "AVAILABLE": "green",
            "RESERVED": "orange",
            "LOANED": "blue",
            "LOST": "red",
            "DAMAGED": "purple",
        }
        color = colors.get(obj.status, "black")
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_status_display(),
        )

    status_colored.short_description = "Status"
    status_colored.admin_order_field = "status"

    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        return super().get_queryset(request).select_related("book")

    def save_model(self, request, obj, form, change):
        """Custom save logic with validation."""
        # Auto-generate barcode if not provided
        if not obj.barcode and not change:  # Only for new items
            import uuid

            obj.barcode = f"BK{uuid.uuid4().hex[:8].upper()}"

        # Validate barcode uniqueness
        if obj.barcode:
            existing = BookItem.objects.filter(barcode=obj.barcode).exclude(pk=obj.pk)
            if existing.exists():
                from django.contrib import messages

                messages.error(
                    request,
                    f"Barcode '{obj.barcode}' already exists. "
                    f"Please use a unique barcode.",
                )
                return

        super().save_model(request, obj, form, change)

        if not change:  # New item
            from django.contrib import messages

            messages.success(
                request,
                f"Book item with barcode '{obj.barcode}' has been "
                f"created successfully.",
            )

    @admin.action(description="Mark selected items as Available")
    def mark_as_available(self, request, queryset):
        """Action to mark selected items as available."""
        count = queryset.update(status=BookItem.Status.AVAILABLE)
        self.message_user(
            request, f"Successfully marked {count} items as available.", level="success"
        )

    @admin.action(description="Mark selected items as Lost")
    def mark_as_lost(self, request, queryset):
        """Action to mark selected items as lost."""
        count = queryset.update(status=BookItem.Status.LOST)
        self.message_user(
            request, f"Successfully marked {count} items as lost.", level="warning"
        )

    @admin.action(description="Mark selected items as Damaged")
    def mark_as_damaged(self, request, queryset):
        """Action to mark selected items as damaged."""
        count = queryset.update(status=BookItem.Status.DAMAGED)
        self.message_user(
            request, f"Successfully marked {count} items as damaged.", level="warning"
        )

    @admin.action(description="Clear location code")
    def clear_location(self, request, queryset):
        """Action to clear location code for selected items."""
        count = queryset.update(location_code="")
        self.message_user(
            request,
            f"Successfully cleared location for {count} items.",
            level="success",
        )

    @admin.action(description="Generate new barcodes for items without barcodes")
    def generate_barcodes(self, request, queryset):
        """Action to generate barcodes for items that don't have them."""
        import uuid

        updated_count = 0

        for item in queryset.filter(barcode__isnull=True):
            item.barcode = f"BK{uuid.uuid4().hex[:8].upper()}"
            item.save()
            updated_count += 1

        self.message_user(
            request,
            f"Successfully generated barcodes for {updated_count} items.",
            level="success",
        )


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
    ordering = ["name"]

    # Add actions for bulk operations
    actions = ["clear_death_date", "clear_birth_date"]

    fieldsets = (
        (
            "Basic Information",
            {
                "fields": ("name", "biography"),
                "description": "Enter the author's basic information.",
            },
        ),
        (
            "Dates",
            {
                "fields": ("birth_date", "death_date", "created_at"),
                "classes": ("collapse",),
                "description": "Important dates related to the author.",
            },
        ),
    )

    def books_count(self, obj):
        count = obj.books.count()
        if count > 0:
            url = (
                reverse("admin:catalog_book_changelist")
                + f"?authors__id__exact={obj.id}"
            )
            return format_html(
                '<a href="{}" style="color: #007cba; font-weight: bold;">{} books</a>',
                url,
                count,
            )
        return format_html('<span style="color: #666;">No books</span>')

    books_count.short_description = "Books"

    def get_queryset(self, request):
        """Optimize queryset with prefetch_related for better performance."""
        queryset = super().get_queryset(request)
        return queryset.prefetch_related("books")

    def save_model(self, request, obj, form, change):
        """Custom save logic with validation."""
        # Validate dates
        if obj.birth_date and obj.death_date:
            if obj.birth_date > obj.death_date:
                from django.contrib import messages

                messages.error(
                    request,
                    "Birth date cannot be later than death date. "
                    "Please correct the dates.",
                )
                return

        # Validate birth date is not in the future
        from django.utils import timezone

        if obj.birth_date and obj.birth_date > timezone.now().date():
            from django.contrib import messages

            messages.warning(
                request, "Birth date is in the future. Please verify this is correct."
            )

        super().save_model(request, obj, form, change)

    @admin.action(description="Clear death date for selected authors")
    def clear_death_date(self, request, queryset):
        """Action to clear death date for selected authors."""
        count = queryset.update(death_date=None)
        self.message_user(
            request,
            f"Successfully cleared death date for {count} authors.",
            level="success",
        )

    @admin.action(description="Clear birth date for selected authors")
    def clear_birth_date(self, request, queryset):
        """Action to clear birth date for selected authors."""
        count = queryset.update(birth_date=None)
        self.message_user(
            request,
            f"Successfully cleared birth date for {count} authors.",
            level="success",
        )


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
    search_fields = ["name", "description", "website"]
    readonly_fields = ["created_at"]
    date_hierarchy = "created_at"
    list_per_page = 25
    ordering = ["name"]

    # Add actions for bulk operations
    actions = ["clear_website", "set_current_year_founded"]

    fieldsets = (
        (
            "Basic Information",
            {
                "fields": ("name", "description"),
                "description": "Enter the publisher's basic information.",
            },
        ),
        (
            "Additional Info",
            {
                "fields": ("founded_year", "website", "created_at"),
                "classes": ("collapse",),
                "description": "Optional details about the publisher.",
            },
        ),
    )

    def website_link(self, obj):
        if obj.website:
            # Ensure the URL has a protocol
            url = obj.website
            if not url.startswith(("http://", "https://")):
                url = f"https://{url}"
            return format_html(
                '<a href="{}" target="_blank" style="color: #007cba;">{}</a>',
                url,
                obj.website,
            )
        return format_html('<span style="color: #666;">No website</span>')

    website_link.short_description = "Website"
    website_link.admin_order_field = "website"

    def books_count(self, obj):
        count = obj.books.count()
        if count > 0:
            url = (
                reverse("admin:catalog_book_changelist")
                + f"?publisher__id__exact={obj.id}"
            )
            return format_html(
                '<a href="{}" style="color: #007cba; font-weight: bold;">{} books</a>',
                url,
                count,
            )
        return format_html('<span style="color: #666;">No books</span>')

    books_count.short_description = "Published Books"
    books_count.admin_order_field = "books_count"

    def get_queryset(self, request):
        """Optimize queryset with prefetch_related for better performance."""
        queryset = super().get_queryset(request)
        return queryset.prefetch_related("books")

    def save_model(self, request, obj, form, change):
        """Custom save logic with validation."""
        # Validate founded year if provided
        if obj.founded_year and obj.founded_year > 2024:
            from django.contrib import messages

            messages.warning(
                request,
                f"Founded year {obj.founded_year} is in the future. "
                f"Please verify this is correct.",
            )
        super().save_model(request, obj, form, change)

    @admin.action(description="Clear website field for selected publishers")
    def clear_website(self, request, queryset):
        """Action to clear website field for selected publishers."""
        count = queryset.update(website="")
        self.message_user(
            request,
            f"Successfully cleared website for {count} publishers.",
            level="success",
        )

    @admin.action(description="Set founded year to current year (2024)")
    def set_current_year_founded(self, request, queryset):
        """Action to set founded year to current year for selected publishers."""
        count = queryset.update(founded_year=2024)
        self.message_user(
            request,
            f"Successfully set founded year to 2024 for {count} publishers.",
            level="success",
        )


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
                "description": "Select a parent category to create a "
                "subcategory hierarchy.",
            },
        ),
    )

    def books_count(self, obj):
        count = obj.books.count()
        if count > 0:
            url = (
                reverse("admin:catalog_book_changelist")
                + f"?categories__id__exact={obj.id}"
            )
            return format_html(
                '<a href="{}" style="color: #007cba; font-weight: bold;">{} books</a>',
                url,
                count,
            )
        return format_html('<span style="color: #666;">No books</span>')

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
                "Please select at least 2 categories (first will be parent, "
                "others will become subcategories).",
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
                        f"Cannot set {parent_category.name} as parent for "
                        f"{child.name} - would create circular relationship.",
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
            f"Successfully set {parent_category.name} as parent for "
            f"{len(children)} categories.",
            level="success",
        )


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
