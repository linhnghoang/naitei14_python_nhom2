"""
Admin export API views.
"""
from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse, HttpResponse
import io

from ..models import Book, Category, Author, Publisher
from ..utils.exports import (
    build_category_queryset,
    render_categories_workbook,
    build_publisher_queryset,
    render_publishers_workbook,
    build_author_queryset,
    render_authors_workbook,
)
from .helpers import get_pagination_params


@staff_member_required
def publisher_books_api(request, publisher_id):
    """API to get books by publisher with pagination."""
    try:
        publisher = Publisher.objects.get(id=publisher_id)
    except Publisher.DoesNotExist:
        return JsonResponse({"error": "Publisher not found"}, status=404)

    books = (
        publisher.books.all()
        .select_related("publisher")
        .prefetch_related("authors", "categories")
    )

    # Pagination with validation
    page, page_size = get_pagination_params(request)
    start = (page - 1) * page_size
    end = start + page_size

    total_books = books.count()
    books_page = books[start:end]

    books_data = [
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
        for book in books_page
    ]

    data = {
        "publisher": {
            "id": publisher.id,
            "name": publisher.name,
            "founded_year": publisher.founded_year,
            "website": publisher.website,
        },
        "books": books_data,
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total_items": total_books,
            "total_pages": (total_books + page_size - 1) // page_size,
            "has_next": end < total_books,
            "has_previous": page > 1,
        },
    }
    return JsonResponse(data)


@staff_member_required
def publishers_export_api(request):
    """API to export publishers data."""
    export_format = request.GET.get("format", "json")
    params = request.GET.dict()
    include_books = request.GET.get("include_books", "false").lower() in [
        "true",
        "1",
        "yes",
    ]

    queryset = build_publisher_queryset(params, include_books)

    if export_format == "excel":
        columns_param = request.GET.get("columns", "")
        columns = [c.strip() for c in columns_param.split(",") if c.strip()] or None

        wb = render_publishers_workbook(queryset, columns, include_books)
        output = io.BytesIO()
        wb.save(output)
        output.seek(0)

        response = HttpResponse(
            output.read(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = "attachment; filename=publishers_export.xlsx"
        return response

    elif export_format == "csv":
        import csv
        from io import StringIO

        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(
            ["ID", "Name", "Description", "Founded Year", "Website", "Books Count"]
        )

        for publisher in queryset:
            books_count = getattr(publisher, "books_count", publisher.books.count())
            writer.writerow(
                [
                    publisher.id,
                    publisher.name,
                    publisher.description or "",
                    publisher.founded_year or "",
                    publisher.website or "",
                    books_count,
                ]
            )

        response = HttpResponse(output.getvalue(), content_type="text/csv")
        response["Content-Disposition"] = "attachment; filename=publishers_export.csv"
        return response

    else:
        publishers_data = [
            {
                "id": publisher.id,
                "name": publisher.name,
                "description": publisher.description,
                "founded_year": publisher.founded_year,
                "website": publisher.website,
                "books_count": getattr(
                    publisher, "books_count", publisher.books.count()
                ),
                "created_at": publisher.created_at.isoformat()
                if publisher.created_at
                else None,
            }
            for publisher in queryset
        ]
        return JsonResponse(
            {"publishers": publishers_data, "total": queryset.count()}
        )


@staff_member_required
def category_books_api(request, category_id):
    """API to get books by category (including subcategories) with pagination."""
    try:
        category = Category.objects.get(id=category_id)
    except Category.DoesNotExist:
        return JsonResponse({"error": "Category not found"}, status=404)

    def get_all_subcategory_ids(cat):
        """Get all subcategory IDs recursively."""
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

    # Pagination with validation
    page, page_size = get_pagination_params(request)
    start = (page - 1) * page_size
    end = start + page_size

    total_books = books.count()
    books_page = books[start:end]

    books_data = [
        {
            "id": book.id,
            "title": book.title,
            "isbn13": book.isbn13,
            "publish_year": book.publish_year,
            "pages": book.pages,
            "language_code": book.language_code,
            "publisher": book.publisher.name if book.publisher else None,
            "authors": [author.name for author in book.authors.all()],
            "created_at": book.created_at.isoformat(),
            "updated_at": book.updated_at.isoformat(),
        }
        for book in books_page
    ]

    data = {
        "category": {
            "id": category.id,
            "name": category.name,
            "slug": category.slug,
            "description": category.description,
            "parent_id": category.parent_id,
            "subcategory_ids": all_category_ids,
        },
        "books": books_data,
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total_items": total_books,
            "total_pages": (total_books + page_size - 1) // page_size,
            "has_next": end < total_books,
            "has_previous": page > 1,
        },
    }
    return JsonResponse(data)


@staff_member_required
def category_export_api(request):
    """API to export categories data."""
    export_format = request.GET.get("format", "json")
    params = request.GET.dict()
    include_books = request.GET.get("include_books", "false").lower() in [
        "true",
        "1",
        "yes",
    ]

    queryset = build_category_queryset(params, include_books)

    if export_format == "excel":
        columns_param = request.GET.get("columns", "")
        columns = [c.strip() for c in columns_param.split(",") if c.strip()] or None

        wb = render_categories_workbook(queryset, columns, include_books)
        output = io.BytesIO()
        wb.save(output)
        output.seek(0)

        response = HttpResponse(
            output.read(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = "attachment; filename=categories_export.xlsx"
        return response

    elif export_format == "csv":
        import csv
        from io import StringIO

        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
                "ID",
                "Name",
                "Slug",
                "Description",
                "Parent",
                "Books Count",
                "Children Count",
            ]
        )

        for category in queryset:
            books_count = getattr(category, "books_count", category.books.count())
            children_count = getattr(
                category, "children_count", category.children.count()
            )
            writer.writerow(
                [
                    category.id,
                    category.name,
                    category.slug,
                    category.description or "",
                    category.parent.name if category.parent else "",
                    books_count,
                    children_count,
                ]
            )

        response = HttpResponse(output.getvalue(), content_type="text/csv")
        response["Content-Disposition"] = "attachment; filename=categories_export.csv"
        return response

    else:
        categories_data = [
            {
                "id": category.id,
                "name": category.name,
                "slug": category.slug,
                "description": category.description,
                "parent_id": category.parent_id,
                "parent_name": category.parent.name if category.parent else None,
                "books_count": getattr(
                    category, "books_count", category.books.count()
                ),
                "children_count": getattr(
                    category, "children_count", category.children.count()
                ),
            }
            for category in queryset
        ]
        return JsonResponse(
            {"categories": categories_data, "total": queryset.count()}
        )


@staff_member_required
def author_books_api(request, author_id):
    """API to get books by author with pagination."""
    try:
        author = Author.objects.get(id=author_id)
    except Author.DoesNotExist:
        return JsonResponse({"error": "Author not found"}, status=404)

    books = (
        author.books.all()
        .select_related("publisher")
        .prefetch_related("authors", "categories")
    )

    # Pagination with validation
    page, page_size = get_pagination_params(request)
    start = (page - 1) * page_size
    end = start + page_size

    total_books = books.count()
    books_page = books[start:end]

    books_data = [
        {
            "id": book.id,
            "title": book.title,
            "isbn13": book.isbn13,
            "publish_year": book.publish_year,
            "pages": book.pages,
            "language_code": book.language_code,
            "publisher": book.publisher.name if book.publisher else None,
            "authors": [auth.name for auth in book.authors.all()],
            "categories": [cat.name for cat in book.categories.all()],
            "created_at": book.created_at.isoformat(),
            "updated_at": book.updated_at.isoformat(),
        }
        for book in books_page
    ]

    data = {
        "author": {
            "id": author.id,
            "name": author.name,
            "biography": author.biography,
            "birth_date": (
                author.birth_date.isoformat() if author.birth_date else None
            ),
            "death_date": (
                author.death_date.isoformat() if author.death_date else None
            ),
        },
        "books": books_data,
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total_items": total_books,
            "total_pages": (total_books + page_size - 1) // page_size,
            "has_next": end < total_books,
            "has_previous": page > 1,
        },
    }
    return JsonResponse(data)


@staff_member_required
def authors_export_api(request):
    """API to export authors data."""
    export_format = request.GET.get("format", "json")
    params = request.GET.dict()
    include_books = request.GET.get("include_books", "false").lower() in [
        "true",
        "1",
        "yes",
    ]

    queryset = build_author_queryset(params, include_books)

    if export_format == "excel":
        columns_param = request.GET.get("columns", "")
        columns = [c.strip() for c in columns_param.split(",") if c.strip()] or None

        wb = render_authors_workbook(queryset, columns, include_books)
        output = io.BytesIO()
        wb.save(output)
        output.seek(0)

        response = HttpResponse(
            output.read(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = "attachment; filename=authors_export.xlsx"
        return response

    elif export_format == "csv":
        import csv
        from io import StringIO

        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(
            ["ID", "Name", "Birth Date", "Death Date", "Biography", "Books Count"]
        )

        for author in queryset:
            books_count = getattr(author, "books_count", author.books.count())
            writer.writerow(
                [
                    author.id,
                    author.name,
                    author.birth_date.isoformat() if author.birth_date else "",
                    author.death_date.isoformat() if author.death_date else "",
                    author.biography or "",
                    books_count,
                ]
            )

        response = HttpResponse(output.getvalue(), content_type="text/csv")
        response["Content-Disposition"] = "attachment; filename=authors_export.csv"
        return response

    else:
        authors_data = [
            {
                "id": author.id,
                "name": author.name,
                "biography": author.biography,
                "birth_date": (
                    author.birth_date.isoformat() if author.birth_date else None
                ),
                "death_date": (
                    author.death_date.isoformat() if author.death_date else None
                ),
                "books_count": getattr(author, "books_count", author.books.count()),
                "created_at": author.created_at.isoformat()
                if author.created_at
                else None,
            }
            for author in queryset
        ]
        return JsonResponse({"authors": authors_data, "total": queryset.count()})


@staff_member_required
def admin_export_books(request):
    """Export books to Excel file."""
    from ..utils.exports import build_book_queryset, render_books_workbook

    params = request.GET.dict()
    include_items = request.GET.get("include_items", "false").lower() in [
        "true",
        "1",
        "yes",
    ]

    queryset = build_book_queryset(params, include_items)
    wb = render_books_workbook(queryset, include_items=include_items)

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    response = HttpResponse(
        output.read(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = "attachment; filename=books_export.xlsx"
    return response


@staff_member_required
def admin_export_categories(request):
    """Export categories to Excel file."""
    params = request.GET.dict()
    include_books = request.GET.get("include_books", "false").lower() in [
        "true",
        "1",
        "yes",
    ]

    queryset = build_category_queryset(params, include_books)
    wb = render_categories_workbook(queryset, include_books=include_books)

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    response = HttpResponse(
        output.read(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = "attachment; filename=categories_export.xlsx"
    return response


@staff_member_required
def admin_export_publishers(request):
    """Export publishers to Excel file."""
    params = request.GET.dict()
    include_books = request.GET.get("include_books", "false").lower() in [
        "true",
        "1",
        "yes",
    ]

    queryset = build_publisher_queryset(params, include_books)
    wb = render_publishers_workbook(queryset, include_books=include_books)

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    response = HttpResponse(
        output.read(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = "attachment; filename=publishers_export.xlsx"
    return response


@staff_member_required
def admin_export_authors(request):
    """Export authors to Excel file."""
    params = request.GET.dict()
    include_books = request.GET.get("include_books", "false").lower() in [
        "true",
        "1",
        "yes",
    ]

    queryset = build_author_queryset(params, include_books)
    wb = render_authors_workbook(queryset, include_books=include_books)

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    response = HttpResponse(
        output.read(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = "attachment; filename=authors_export.xlsx"
    return response
