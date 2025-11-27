from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.models import User
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from django.db.models import Count, Q
from django.db.models.functions import ExtractMonth, ExtractDay
from datetime import date, timedelta
import calendar
import json
import io

from .models import Book, Category, Author, Publisher
from .utils.exports import build_category_queryset, render_categories_workbook, build_book_queryset, render_books_workbook


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
            "with_subcategories": Category.objects.filter(children__isnull=False).distinct().count(),
            "empty_categories": Category.objects.filter(books=None).count(),
        },
    }
    return JsonResponse(data)


@staff_member_required
def category_stats_api(request):
    """Category-specific statistics API."""
    
    # Get category hierarchy stats
    top_level_categories = Category.objects.filter(parent=None).annotate(
        books_count=Count('books', distinct=True),
        children_count=Count('children', distinct=True)
    ).order_by('-books_count')
    
    # Categories with most books
    popular_categories = Category.objects.annotate(
        books_count=Count('books', distinct=True)
    ).filter(books_count__gt=0).order_by('-books_count')[:10]
    
    # Categories with most subcategories
    parent_categories = Category.objects.annotate(
        children_count=Count('children', distinct=True)
    ).filter(children_count__gt=0).order_by('-children_count')[:10]
    
    # Empty categories (no books assigned)
    empty_categories = Category.objects.filter(books=None).order_by('name')
    
    # Category depth analysis
    category_depth_stats = []
    for category in Category.objects.all():
        depth = 0
        parent = category.parent
        while parent:
            depth += 1
            parent = parent.parent
        category_depth_stats.append({
            'id': category.id,
            'name': category.name,
            'depth': depth
        })
    
    # Group by depth
    depth_distribution = {}
    for cat_data in category_depth_stats:
        depth = cat_data['depth']
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
                    "children_count": cat.children_count
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
                "books_count": cat.books_count
            }
            for cat in popular_categories
        ],
        "parent_categories": [
            {
                "id": cat.id,
                "name": cat.name,
                "slug": cat.slug,
                "children_count": cat.children_count
            }
            for cat in parent_categories
        ],
        "empty_categories": [
            {
                "id": cat.id,
                "name": cat.name,
                "slug": cat.slug
            }
            for cat in empty_categories
        ],
        "summary": {
            "total_categories": Category.objects.count(),
            "top_level_count": len([cat for cat in category_depth_stats if cat['depth'] == 0]),
            "max_depth": max([cat['depth'] for cat in category_depth_stats], default=0),
            "avg_books_per_category": Category.objects.aggregate(
                avg_books=Count('books', distinct=True)
            )['avg_books'] or 0,
        }
    }
    return JsonResponse(data)


@staff_member_required
def category_tree_api(request):
    """API to get complete category tree structure."""
    
    def build_category_tree(parent=None):
        """Recursively build category tree."""
        categories = Category.objects.filter(parent=parent).annotate(
            books_count=Count('books', distinct=True),
            children_count=Count('children', distinct=True)
        ).order_by('name')
        
        tree = []
        for category in categories:
            node = {
                "id": category.id,
                "name": category.name,
                "slug": category.slug,
                "description": category.description,
                "books_count": category.books_count,
                "children_count": category.children_count,
                "children": build_category_tree(category)
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
    books = Book.objects.filter(
        categories__id__in=all_category_ids
    ).distinct().select_related('publisher').prefetch_related('authors')
    
    # Pagination
    page = int(request.GET.get('page', 1))
    page_size = int(request.GET.get('page_size', 20))
    start = (page - 1) * page_size
    end = start + page_size
    
    total_books = books.count()
    books_page = books[start:end]
    
    books_data = []
    for book in books_page:
        books_data.append({
            "id": book.id,
            "title": book.title,
            "isbn13": book.isbn13,
            "publish_year": book.publish_year,
            "publisher": book.publisher.name if book.publisher else None,
            "authors": [author.name for author in book.authors.all()],
            "created_at": book.created_at.isoformat(),
        })
    
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
        }
    }
    return JsonResponse(data)


@staff_member_required
def category_export_api(request):
    """Export categories data as JSON or CSV."""
    format_type = request.GET.get('format', 'json')
    include_books = request.GET.get('include_books', 'false').lower() == 'true'
    
    categories = Category.objects.all().order_by('name')
    
    if include_books:
        categories = categories.prefetch_related('books', 'children')
    else:
        categories = categories.prefetch_related('children')
    
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
    
    if format_type == 'csv':
        import csv
        import io
        
        output = io.StringIO()
        fieldnames = ['id', 'name', 'slug', 'description', 'parent_id', 'parent_name', 'children_count', 'books_count']
        
        if include_books:
            # Flatten books data for CSV
            flattened_data = []
            for cat_data in export_data:
                base_row = {k: v for k, v in cat_data.items() if k != 'books'}
                if cat_data.get('books'):
                    for book in cat_data['books']:
                        row = base_row.copy()
                        row.update({f'book_{k}': v for k, v in book.items()})
                        flattened_data.append(row)
                else:
                    flattened_data.append(base_row)
            
            # Update fieldnames for books
            if flattened_data and any('book_id' in row for row in flattened_data):
                fieldnames.extend(['book_id', 'book_title', 'book_isbn13'])
            
            export_data = flattened_data
        
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(export_data)
        
        response = HttpResponse(output.getvalue(), content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="categories_export.csv"'
        return response
    
    else:
        # JSON format (default)
        data = {
            "export_date": timezone.now().isoformat(),
            "total_categories": len(export_data),
            "include_books": include_books,
            "categories": export_data
        }
        return JsonResponse(data, json_dumps_params={'indent': 2})


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
    recent_categories = Category.objects.order_by('-id')[:5]
    for cat in recent_categories:
        activities.append({
            "timestamp": timezone.now(),  # Categories don't have created_at in base model
            "message": f"Category: {cat.name}",
            "details": f"Slug: {cat.slug} • Books: {cat.books.count()} • Children: {cat.children.count()}",
            "ago": "Recently",
            "type": "category"
        })

    # Recent books
    recent_books = Book.objects.order_by("-created_at")[:5]
    for book in recent_books:
        activities.append({
            "timestamp": book.created_at,
            "message": f"New book: {book.title}",
            "details": f"Publisher: {book.publisher or '-'} • Year: {book.publish_year or '-'}",
            "ago": _ago(book.created_at),
            "type": "book"
        })

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
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
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
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    resp["Content-Disposition"] = f'attachment; filename="{base}.xlsx"'
    return resp