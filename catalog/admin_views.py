from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.models import User
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from django.db.models import Count, Q, Min, Max
from django.db.models.functions import ExtractMonth, ExtractDay
from datetime import date, timedelta
import calendar
import json
import io

from .models import Book, Category, Author, Publisher
from .utils.exports import (
    build_category_queryset,
    render_categories_workbook,
    build_book_queryset,
    render_books_workbook,
    build_publisher_queryset,
    render_publishers_workbook,
)


@staff_member_required
def admin_stats_api(request):
    """General admin statistics API."""
    data = {
        "basic": {
            "total_books": Book.objects.count(),
            "total_categories": Category.objects.count(),
            "total_authors": Author.objects.count(),
            "total_publishers": Publisher.objects.count(),
            "total_users": User.objects.filter(is_active=True).count(),
        },
        "categories": {
            "top_level": Category.objects.filter(parent=None).count(),
            "with_subcategories": Category.objects.filter(children__isnull=False)
            .distinct()
            .count(),
            "empty_categories": Category.objects.filter(books=None).count(),
        },
        "publishers": {
            "with_books": Publisher.objects.filter(books__isnull=False)
            .distinct()
            .count(),
            "without_books": Publisher.objects.filter(books__isnull=True).count(),
            "with_website": Publisher.objects.exclude(
                Q(website="") | Q(website__isnull=True)
            ).count(),
        },
    }
    return JsonResponse(data)


@staff_member_required
def publisher_stats_api(request):
    """Publisher-specific statistics API."""

    # Publishers with most books
    popular_publishers = (
        Publisher.objects.annotate(books_count=Count("books", distinct=True))
        .filter(books_count__gt=0)
        .order_by("-books_count")[:10]
    )

    # Publishers by founded year
    publishers_by_year = (
        Publisher.objects.values("founded_year")
        .annotate(count=Count("id"))
        .exclude(founded_year__isnull=True)
        .order_by("founded_year")
    )

    # Publishers without books
    empty_publishers = Publisher.objects.filter(books__isnull=True).order_by("name")

    # Publishers with/without websites
    publishers_with_website = Publisher.objects.exclude(
        Q(website="") | Q(website__isnull=True)
    ).order_by("name")

    publishers_without_website = Publisher.objects.filter(
        Q(website="") | Q(website__isnull=True)
    ).order_by("name")

    # Recent publishers
    recent_publishers = Publisher.objects.order_by("-created_at")[:10]

    data = {
        "popular_publishers": [
            {
                "id": pub.id,
                "name": pub.name,
                "books_count": pub.books_count,
                "founded_year": pub.founded_year,
                "website": pub.website,
            }
            for pub in popular_publishers
        ],
        "publishers_by_year": [
            {"year": item["founded_year"], "count": item["count"]}
            for item in publishers_by_year
        ],
        "empty_publishers": [
            {
                "id": pub.id,
                "name": pub.name,
                "founded_year": pub.founded_year,
                "created_at": pub.created_at.isoformat(),
            }
            for pub in empty_publishers
        ],
        "website_stats": {
            "with_website": [
                {
                    "id": pub.id,
                    "name": pub.name,
                    "website": pub.website,
                    "books_count": pub.books.count(),
                }
                for pub in publishers_with_website
            ],
            "without_website": [
                {
                    "id": pub.id,
                    "name": pub.name,
                    "books_count": pub.books.count(),
                    "founded_year": pub.founded_year,
                }
                for pub in publishers_without_website
            ],
        },
        "recent_publishers": [
            {
                "id": pub.id,
                "name": pub.name,
                "founded_year": pub.founded_year,
                "website": pub.website,
                "created_at": pub.created_at.isoformat(),
                "books_count": pub.books.count(),
            }
            for pub in recent_publishers
        ],
        "summary": {
            "total_publishers": Publisher.objects.count(),
            "with_books": Publisher.objects.filter(books__isnull=False)
            .distinct()
            .count(),
            "without_books": Publisher.objects.filter(books__isnull=True).count(),
            "with_website": publishers_with_website.count(),
            "without_website": publishers_without_website.count(),
            "avg_books_per_publisher": Publisher.objects.aggregate(
                avg_books=Count("books", distinct=True)
            )["avg_books"]
            or 0,
            "oldest_year": Publisher.objects.aggregate(oldest=Min("founded_year"))[
                "oldest"
            ],
            "newest_year": Publisher.objects.aggregate(newest=Max("founded_year"))[
                "newest"
            ],
        },
    }
    return JsonResponse(data)


@staff_member_required
def publisher_books_api(request, publisher_id):
    """API to get books for a specific publisher."""
    try:
        publisher = Publisher.objects.get(id=publisher_id)
    except Publisher.DoesNotExist:
        return JsonResponse({"error": "Publisher not found"}, status=404)

    books = (
        publisher.books.all()
        .select_related("publisher")
        .prefetch_related("authors", "categories")
    )

    # Pagination
    page = int(request.GET.get("page", 1))
    page_size = int(request.GET.get("page_size", 20))
    start = (page - 1) * page_size
    end = start + page_size

    total_books = books.count()
    books_page = books[start:end]

    books_data = []
    for book in books_page:
        books_data.append(
            {
                "id": book.id,
                "title": book.title,
                "isbn13": book.isbn13,
                "publish_year": book.publish_year,
                "pages": book.pages,
                "language_code": book.language_code,
                "authors": [author.name for author in book.authors.all()],
                "categories": [cat.name for cat in book.categories.all()],
                "created_at": book.created_at.isoformat(),
                "updated_at": book.updated_at.isoformat(),
            }
        )

    data = {
        "publisher": {
            "id": publisher.id,
            "name": publisher.name,
            "description": publisher.description,
            "founded_year": publisher.founded_year,
            "website": publisher.website,
            "created_at": publisher.created_at.isoformat(),
        },
        "books": books_data,
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total": total_books,
            "has_next": end < total_books,
            "has_prev": page > 1,
        },
    }
    return JsonResponse(data)


@staff_member_required
def publishers_export_api(request):
    """Export publishers data as JSON or CSV."""
    format_type = request.GET.get("format", "json")
    include_books = request.GET.get("include_books", "false").lower() == "true"

    publishers = Publisher.objects.all().order_by("name")

    if include_books:
        publishers = publishers.prefetch_related("books")

    export_data = []
    for publisher in publishers:
        pub_data = {
            "id": publisher.id,
            "name": publisher.name,
            "description": publisher.description,
            "founded_year": publisher.founded_year,
            "website": publisher.website,
            "created_at": publisher.created_at.isoformat(),
        }

        if include_books:
            pub_data["books"] = [
                {
                    "id": book.id,
                    "title": book.title,
                    "isbn13": book.isbn13,
                    "publish_year": book.publish_year,
                }
                for book in publisher.books.all()
            ]
            pub_data["books_count"] = len(pub_data["books"])
        else:
            pub_data["books_count"] = publisher.books.count()

        export_data.append(pub_data)

    if format_type == "csv":
        import csv
        import io

        output = io.StringIO()
        fieldnames = [
            "id",
            "name",
            "description",
            "founded_year",
            "website",
            "created_at",
            "books_count",
        ]

        if include_books:
            # Flatten books data for CSV
            flattened_data = []
            for pub_data in export_data:
                base_row = {k: v for k, v in pub_data.items() if k != "books"}
                if pub_data.get("books"):
                    for book in pub_data["books"]:
                        row = base_row.copy()
                        row.update({f"book_{k}": v for k, v in book.items()})
                        flattened_data.append(row)
                else:
                    flattened_data.append(base_row)

            # Update fieldnames for books
            if flattened_data and any("book_id" in row for row in flattened_data):
                fieldnames.extend(
                    ["book_id", "book_title", "book_isbn13", "book_publish_year"]
                )

            export_data = flattened_data

        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(export_data)

        response = HttpResponse(output.getvalue(), content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="publishers_export.csv"'
        return response

    else:
        # JSON format (default)
        data = {
            "export_date": timezone.now().isoformat(),
            "total_publishers": len(export_data),
            "include_books": include_books,
            "publishers": export_data,
        }
        return JsonResponse(data, json_dumps_params={"indent": 2})


@staff_member_required
def category_stats_api(request):
    """Category-specific statistics API."""

    # Get category hierarchy stats
    top_level_categories = (
        Category.objects.filter(parent=None)
        .annotate(
            books_count=Count("books", distinct=True),
            children_count=Count("children", distinct=True),
        )
        .order_by("-books_count")
    )

    # Categories with most books
    popular_categories = (
        Category.objects.annotate(books_count=Count("books", distinct=True))
        .filter(books_count__gt=0)
        .order_by("-books_count")[:10]
    )

    # Categories with most subcategories
    parent_categories = (
        Category.objects.annotate(children_count=Count("children", distinct=True))
        .filter(children_count__gt=0)
        .order_by("-children_count")[:10]
    )

    # Empty categories (no books assigned)
    empty_categories = Category.objects.filter(books=None).order_by("name")

    # Category depth analysis
    category_depth_stats = []
    for category in Category.objects.all():
        depth = 0
        parent = category.parent
        while parent:
            depth += 1
            parent = parent.parent
        category_depth_stats.append(
            {"id": category.id, "name": category.name, "depth": depth}
        )

    # Group by depth
    depth_distribution = {}
    for cat_data in category_depth_stats:
        depth = cat_data["depth"]
        if depth not in depth_distribution:
            depth_distribution[depth] = 0
        depth_distribution[depth] += 1

    data = {
        "hierarchy": {
            "top_level_categories": [
                {
                    "id": cat.id,
                    "name": cat.name,
                    "slug": cat.slug,
                    "books_count": cat.books_count,
                    "children_count": cat.children_count,
                }
                for cat in top_level_categories
            ],
            "depth_distribution": depth_distribution,
        },
        "popular_categories": [
            {
                "id": cat.id,
                "name": cat.name,
                "slug": cat.slug,
                "books_count": cat.books_count,
            }
            for cat in popular_categories
        ],
        "parent_categories": [
            {
                "id": cat.id,
                "name": cat.name,
                "slug": cat.slug,
                "children_count": cat.children_count,
            }
            for cat in parent_categories
        ],
        "empty_categories": [
            {"id": cat.id, "name": cat.name, "slug": cat.slug}
            for cat in empty_categories
        ],
        "summary": {
            "total_categories": Category.objects.count(),
            "top_level_count": len(
                [cat for cat in category_depth_stats if cat["depth"] == 0]
            ),
            "max_depth": max([cat["depth"] for cat in category_depth_stats], default=0),
            "avg_books_per_category": Category.objects.aggregate(
                avg_books=Count("books", distinct=True)
            )["avg_books"]
            or 0,
        },
    }
    return JsonResponse(data)


@staff_member_required
def category_tree_api(request):
    """API to get complete category tree structure."""

    def build_category_tree(parent=None):
        """Recursively build category tree."""
        categories = (
            Category.objects.filter(parent=parent)
            .annotate(
                books_count=Count("books", distinct=True),
                children_count=Count("children", distinct=True),
            )
            .order_by("name")
        )

        tree = []
        for category in categories:
            node = {
                "id": category.id,
                "name": category.name,
                "slug": category.slug,
                "description": category.description,
                "books_count": category.books_count,
                "children_count": category.children_count,
                "children": build_category_tree(category),
            }
            tree.append(node)
        return tree

    tree = build_category_tree()
    return JsonResponse({"category_tree": tree})


@staff_member_required
def category_books_api(request, category_id):
    """API to get books for a specific category."""
    try:
        category = Category.objects.get(id=category_id)
    except Category.DoesNotExist:
        return JsonResponse({"error": "Category not found"}, status=404)

    # Get all books in this category and its subcategories
    def get_all_subcategory_ids(cat):
        """Recursively get all subcategory IDs."""
        ids = [cat.id]
        for child in cat.children.all():
            ids.extend(get_all_subcategory_ids(child))
        return ids

    all_category_ids = get_all_subcategory_ids(category)
    books = (
        Book.objects.filter(categories__id__in=all_category_ids)
        .distinct()
        .select_related("publisher")
        .prefetch_related("authors")
    )

    # Pagination
    page = int(request.GET.get("page", 1))
    page_size = int(request.GET.get("page_size", 20))
    start = (page - 1) * page_size
    end = start + page_size

    total_books = books.count()
    books_page = books[start:end]

    books_data = []
    for book in books_page:
        books_data.append(
            {
                "id": book.id,
                "title": book.title,
                "isbn13": book.isbn13,
                "publish_year": book.publish_year,
                "publisher": book.publisher.name if book.publisher else None,
                "authors": [author.name for author in book.authors.all()],
                "created_at": book.created_at.isoformat(),
            }
        )

    data = {
        "category": {
            "id": category.id,
            "name": category.name,
            "slug": category.slug,
            "description": category.description,
        },
        "books": books_data,
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total": total_books,
            "has_next": end < total_books,
            "has_prev": page > 1,
        },
    }
    return JsonResponse(data)


@staff_member_required
def category_export_api(request):
    """Export categories data as JSON or CSV."""
    format_type = request.GET.get("format", "json")
    include_books = request.GET.get("include_books", "false").lower() == "true"

    categories = Category.objects.all().order_by("name")

    if include_books:
        categories = categories.prefetch_related("books", "children")
    else:
        categories = categories.prefetch_related("children")

    export_data = []
    for category in categories:
        cat_data = {
            "id": category.id,
            "name": category.name,
            "slug": category.slug,
            "description": category.description,
            "parent_id": category.parent_id,
            "parent_name": category.parent.name if category.parent else None,
            "children_count": category.children.count(),
        }

        if include_books:
            cat_data["books"] = [
                {
                    "id": book.id,
                    "title": book.title,
                    "isbn13": book.isbn13,
                }
                for book in category.books.all()
            ]
            cat_data["books_count"] = len(cat_data["books"])
        else:
            cat_data["books_count"] = category.books.count()

        export_data.append(cat_data)

    if format_type == "csv":
        import csv
        import io

        output = io.StringIO()
        fieldnames = [
            "id",
            "name",
            "slug",
            "description",
            "parent_id",
            "parent_name",
            "children_count",
            "books_count",
        ]

        if include_books:
            # Flatten books data for CSV
            flattened_data = []
            for cat_data in export_data:
                base_row = {k: v for k, v in cat_data.items() if k != "books"}
                if cat_data.get("books"):
                    for book in cat_data["books"]:
                        row = base_row.copy()
                        row.update({f"book_{k}": v for k, v in book.items()})
                        flattened_data.append(row)
                else:
                    flattened_data.append(base_row)

            # Update fieldnames for books
            if flattened_data and any("book_id" in row for row in flattened_data):
                fieldnames.extend(["book_id", "book_title", "book_isbn13"])

            export_data = flattened_data

        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(export_data)

        response = HttpResponse(output.getvalue(), content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="categories_export.csv"'
        return response

    else:
        # JSON format (default)
        data = {
            "export_date": timezone.now().isoformat(),
            "total_categories": len(export_data),
            "include_books": include_books,
            "categories": export_data,
        }
        return JsonResponse(data, json_dumps_params={"indent": 2})


def _ago(dt):
    """Return a human-readable relative time like '5m ago'.

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
        return f"{seconds}s ago"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m ago"
    hours = minutes // 60
    if hours < 24:
        return f"{hours}h ago"
    days = hours // 24
    return f"{days}d ago"


@staff_member_required
def admin_activity_api(request):
    """Recent admin activity API."""
    activities = []

    # Recent categories
    recent_categories = Category.objects.order_by("-id")[:3]
    for cat in recent_categories:
        activities.append(
            {
                # Categories don't have created_at in base model
                "timestamp": timezone.now(),
                "message": f"Category: {cat.name}",
                "details": (
                    f"Slug: {cat.slug} • Books: {cat.books.count()} • "
                    f"Children: {cat.children.count()}"
                ),
                "ago": "Recently",
                "type": "category",
            }
        )

    # Recent publishers
    recent_publishers = Publisher.objects.order_by("-created_at")[:3]
    for pub in recent_publishers:
        activities.append(
            {
                "timestamp": pub.created_at,
                "message": f"Publisher: {pub.name}",
                "details": (
                    f"Founded: {pub.founded_year or 'Unknown'} • "
                    f"Books: {pub.books.count()} • "
                    f"Website: {'Yes' if pub.website else 'No'}"
                ),
                "ago": _ago(pub.created_at),
                "type": "publisher",
            }
        )

    # Recent authors
    recent_authors = Author.objects.order_by("-created_at")[:3]
    for author in recent_authors:
        activities.append(
            {
                "timestamp": author.created_at,
                "message": f"Author: {author.name}",
                "details": (
                    f"Born: {author.birth_date or 'Unknown'} • "
                    f"Books: {author.books.count()}"
                ),
                "ago": _ago(author.created_at),
                "type": "author",
            }
        )

    # Recent books
    recent_books = Book.objects.order_by("-created_at")[:4]
    for book in recent_books:
        activities.append(
            {
                "timestamp": book.created_at,
                "message": f"New book: {book.title}",
                "details": (
                    f"Publisher: {book.publisher or '-'} • "
                    f"Year: {book.publish_year or '-'}"
                ),
                "ago": _ago(book.created_at),
                "type": "book",
            }
        )

    # Sort mixed activities by timestamp desc and cap to 10
    activities.sort(
        key=lambda x: x.get("timestamp") or timezone.now(), reverse=True
    )
    activities = activities[:10]

    return JsonResponse({"activities": activities})


@staff_member_required
def export_categories_excel(request):
    """Export Excel file with categories data.

    Query parameters:
    - q: search term for name/description
    - parent_id: filter by parent category (0 for top-level)
    - min_books: minimum number of books
    - empty_only: true/false for categories without books
    - has_children: true/false for categories with/without subcategories
    - sort: sorting field (name, books_count, children_count)
    - columns: comma-separated list of columns to include
    - include_books: true/false to include books sheet
    - filename: custom filename (without extension)
    """
    include_books = (request.GET.get("include_books") or "").lower() in {
        "1",
        "true",
        "yes",
    }
    columns_param = (request.GET.get("columns") or "").strip()
    columns = (
        [c.strip() for c in columns_param.split(",") if c.strip()]
        if columns_param
        else None
    )

    # Build queryset & workbook
    qs = build_category_queryset(request.GET, include_books=include_books)
    wb = render_categories_workbook(
        qs, columns=columns, include_books=include_books
    )

    # Serialize
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    ts = timezone.now().strftime("%Y%m%d_%H%M%S")
    base = (
        request.GET.get("filename") or f"categories_export_{ts}"
    ).strip() or f"categories_export_{ts}"
    resp = HttpResponse(
        buf.getvalue(),
        content_type=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        ),
    )
    resp["Content-Disposition"] = f'attachment; filename="{base}.xlsx"'
    return resp


@staff_member_required
def export_books_excel(request):
    """Export Excel file with books data - compatible with base-project structure.

    Query parameters:
    - q: search term
    - category_id: filter by category
    - author_id: filter by author
    - publisher_id: filter by publisher
    - language: filter by language
    - created_from: date filter (YYYY-MM-DD)
    - created_to: date filter (YYYY-MM-DD)
    - columns: comma-separated list of columns
    - include_items: true/false to include items sheet
    - filename: custom filename (without extension)
    """
    include_items = (request.GET.get("include_items") or "").lower() in {
        "1",
        "true",
        "yes",
    }
    columns_param = (request.GET.get("columns") or "").strip()
    columns = (
        [c.strip() for c in columns_param.split(",") if c.strip()]
        if columns_param
        else None
    )

    # Build queryset & workbook
    qs = build_book_queryset(request.GET, include_items=include_items)
    wb = render_books_workbook(
        qs, columns=columns, include_items=include_items
    )

    # Serialize
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    ts = timezone.now().strftime("%Y%m%d_%H%M%S")
    base = (
        request.GET.get("filename") or f"books_export_{ts}"
    ).strip() or f"books_export_{ts}"
    resp = HttpResponse(
        buf.getvalue(),
        content_type=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        ),
    )
    resp["Content-Disposition"] = f'attachment; filename="{base}.xlsx"'
    return resp


@staff_member_required
def export_publishers_excel(request):
    """Export Excel file with publishers data.

    Query parameters:
    - q: search term for name/description/website
    - founded_year_from: minimum founded year
    - founded_year_to: maximum founded year
    - min_books: minimum number of books
    - empty_only: true/false for publishers without books
    - has_website: true/false for publishers with/without website
    - created_from: date filter (YYYY-MM-DD)
    - created_to: date filter (YYYY-MM-DD)
    - sort: sorting field (name, founded_year, books_count, created_at)
    - columns: comma-separated list of columns to include
    - include_books: true/false to include books sheet
    - filename: custom filename (without extension)
    """
    include_books = (request.GET.get("include_books") or "").lower() in {
        "1",
        "true",
        "yes",
    }
    columns_param = (request.GET.get("columns") or "").strip()
    columns = (
        [c.strip() for c in columns_param.split(",") if c.strip()]
        if columns_param
        else None
    )

    # Build queryset & workbook
    qs = build_publisher_queryset(request.GET, include_books=include_books)
    wb = render_publishers_workbook(
        qs, columns=columns, include_books=include_books
    )

    # Serialize
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    ts = timezone.now().strftime("%Y%m%d_%H%M%S")
    base = (
        request.GET.get("filename") or f"publishers_export_{ts}"
    ).strip() or f"publishers_export_{ts}"
    resp = HttpResponse(
        buf.getvalue(),
        content_type=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        ),
    )
    resp["Content-Disposition"] = f'attachment; filename="{base}.xlsx"'
    return resp
