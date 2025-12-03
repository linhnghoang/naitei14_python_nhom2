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

from .models import Book, Category, Author, Publisher, BookItem
from .utils.exports import build_category_queryset, render_categories_workbook, build_book_queryset, render_books_workbook, build_publisher_queryset, render_publishers_workbook, build_author_queryset, render_authors_workbook


@staff_member_required
def admin_stats_api(request):
    """General admin statistics API."""
    from .models import BorrowRequest, Loan
    
    # Count overdue loans - check both Loan model and BorrowRequest model
    overdue_loans_count = Loan.objects.filter(status=Loan.Status.OVERDUE).count()
    # Also count overdue borrow requests if they exist
    overdue_requests_count = BorrowRequest.objects.filter(status=BorrowRequest.Status.OVERDUE).count() if hasattr(BorrowRequest.Status, 'OVERDUE') else 0
    
    data = {
        "basic": {
            "total_books": Book.objects.count(),
            "total_users": User.objects.filter(is_active=True).count(),
        },
        "requests": {
            "pending": BorrowRequest.objects.filter(
                status=BorrowRequest.Status.PENDING
            ).count(),
        },
        "loans": {
            "overdue": max(overdue_loans_count, overdue_requests_count),
        },
    }
    return JsonResponse(data)


@staff_member_required
def publisher_stats_api(request):
    """Publisher-specific statistics API."""
    
    # Publishers with most books
    popular_publishers = Publisher.objects.annotate(
        books_count=Count('books', distinct=True)
    ).filter(books_count__gt=0).order_by('-books_count')[:10]
    
    # Publishers by founded year
    publishers_by_year = Publisher.objects.values('founded_year').annotate(
        count=Count('id')
    ).exclude(founded_year__isnull=True).order_by('founded_year')
    
    # Publishers without books
    empty_publishers = Publisher.objects.filter(books__isnull=True).order_by('name')
    
    # Publishers with/without websites
    publishers_with_website = Publisher.objects.exclude(
        Q(website='') | Q(website__isnull=True)
    ).order_by('name')
    
    publishers_without_website = Publisher.objects.filter(
        Q(website='') | Q(website__isnull=True)
    ).order_by('name')
    
    # Recent publishers
    recent_publishers = Publisher.objects.order_by('-created_at')[:10]
    
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
            {
                "year": item['founded_year'],
                "count": item['count']
            }
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
            ]
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
            "with_books": Publisher.objects.filter(books__isnull=False).distinct().count(),
            "without_books": Publisher.objects.filter(books__isnull=True).count(),
            "with_website": publishers_with_website.count(),
            "without_website": publishers_without_website.count(),
            "avg_books_per_publisher": Publisher.objects.aggregate(
                avg_books=Count('books', distinct=True)
            )['avg_books'] or 0,
            "oldest_year": Publisher.objects.aggregate(
                oldest=Min('founded_year')
            )['oldest'],
            "newest_year": Publisher.objects.aggregate(
                newest=Max('founded_year')
            )['newest'],
        }
    }
    return JsonResponse(data)


@staff_member_required
def publisher_books_api(request, publisher_id):
    """API to get books for a specific publisher."""
    try:
        publisher = Publisher.objects.get(id=publisher_id)
    except Publisher.DoesNotExist:
        return JsonResponse({"error": "Publisher not found"}, status=404)
    
    books = publisher.books.all().select_related('publisher').prefetch_related('authors', 'categories')
    
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
            "pages": book.pages,
            "language_code": book.language_code,
            "authors": [author.name for author in book.authors.all()],
            "categories": [cat.name for cat in book.categories.all()],
            "created_at": book.created_at.isoformat(),
            "updated_at": book.updated_at.isoformat(),
        })
    
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
        }
    }
    return JsonResponse(data)


@staff_member_required
def publishers_export_api(request):
    """Export publishers data as JSON or CSV."""
    format_type = request.GET.get('format', 'json')
    include_books = request.GET.get('include_books', 'false').lower() == 'true'
    
    publishers = Publisher.objects.all().order_by('name')
    
    if include_books:
        publishers = publishers.prefetch_related('books')
    
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
    
    if format_type == 'csv':
        import csv
        import io
        
        output = io.StringIO()
        fieldnames = ['id', 'name', 'description', 'founded_year', 'website', 'created_at', 'books_count']
        
        if include_books:
            # Flatten books data for CSV
            flattened_data = []
            for pub_data in export_data:
                base_row = {k: v for k, v in pub_data.items() if k != 'books'}
                if pub_data.get('books'):
                    for book in pub_data['books']:
                        row = base_row.copy()
                        row.update({f'book_{k}': v for k, v in book.items()})
                        flattened_data.append(row)
                else:
                    flattened_data.append(base_row)
            
            # Update fieldnames for books
            if flattened_data and any('book_id' in row for row in flattened_data):
                fieldnames.extend(['book_id', 'book_title', 'book_isbn13', 'book_publish_year'])
            
            export_data = flattened_data
        
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(export_data)
        
        response = HttpResponse(output.getvalue(), content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="publishers_export.csv"'
        return response
    
    else:
        # JSON format (default)
        data = {
            "export_date": timezone.now().isoformat(),
            "total_publishers": len(export_data),
            "include_books": include_books,
            "publishers": export_data
        }
        return JsonResponse(data, json_dumps_params={'indent': 2})


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
    from .models import BorrowRequest, Loan
    
    activities = []

    recent_requests = BorrowRequest.objects.select_related("user").order_by(
        "-created_at"
    )[:5]
    for r in recent_requests:
        activities.append(
            {
                "timestamp": r.created_at,
                "message": f"Borrow request #{r.id} by {r.user}",
                "details": f"{r.items.count()} item(s) • Status: {r.status}",
                "ago": _ago(r.created_at),
            }
        )

    recent_books = Book.objects.order_by("-created_at")[:5]
    for b in recent_books:
        activities.append(
            {
                "timestamp": b.created_at,
                "message": f"New book: {b.title}",
                "details": f"Publisher: {b.publisher or '-'} • Year: {b.publish_year or '-'}",
                "ago": _ago(b.created_at),
            }
        )

    recent_loans = Loan.objects.select_related("book_item").order_by(
        "-created_at"
    )[:5]
    for loan in recent_loans:
        activities.append(
            {
                "timestamp": loan.created_at,
                "message": f"Loan #{loan.id} {loan.status}",
                "details": f"Item: {loan.book_item} • Due: {loan.due_date}",
                "ago": _ago(loan.created_at),
            }
        )

    # Sort mixed activities by timestamp desc and cap to 10
    activities.sort(
        key=lambda x: x.get("timestamp") or timezone.now(), reverse=True
    )
    activities = activities[:10]

    return JsonResponse({"activities": activities})


@staff_member_required
def admin_book_stats_api(request):
    """Return book-related statistics for charts (month/year scope).

    Query params:
    - period: 'month' (default) or 'year'
    - year: integer (defaults to current year)
    - month: 1-12 (required when period=month; defaults to current month)
    """
    from .models import BorrowRequest, Loan, BorrowRequestItem
    
    now = timezone.now()
    period = (request.GET.get("period") or "month").lower()
    try:
        year = int(request.GET.get("year", now.year))
    except ValueError:
        year = now.year
    try:
        month = int(request.GET.get("month", now.month))
    except ValueError:
        month = now.month

    if period == "year":
        start = date(year, 1, 1)
        end = date(year + 1, 1, 1)
    else:
        # default to month
        month = max(1, min(12, month))
        start = date(year, month, 1)
        last_day = calendar.monthrange(year, month)[1]
        end = date(year, month, last_day) + timedelta(days=1)

    # Books per category (overall, not scoped to period)
    category_book_counts_qs = (
        Category.objects.annotate(total_books=Count("books", distinct=True))
        .values("id", "name", "total_books")
        .order_by("-total_books", "name")
    )
    category_book_counts = list(category_book_counts_qs)

    # Try to use Loan model first, fallback to BorrowRequest if no loans exist
    loan_count = Loan.objects.count()
    
    if loan_count > 0:
        # Use Loan-based queries (base_project style)
        # Loans by category in the period
        loans_qs = (
            Loan.objects.filter(approved_from__gte=start, approved_from__lt=end)
            .values(
                "request_item__book__categories__id",
                "request_item__book__categories__name",
            )
            .annotate(total=Count("id"))
            .exclude(request_item__book__categories__id__isnull=True)
            .order_by("-total", "request_item__book__categories__name")
        )
        loans_by_category = [
            {
                "category_id": row["request_item__book__categories__id"],
                "category_name": row["request_item__book__categories__name"],
                "total": row["total"],
            }
            for row in loans_qs
        ]

        # Top books by loans in the period
        top_books_qs = (
            Loan.objects.filter(approved_from__gte=start, approved_from__lt=end)
            .values("request_item__book__id", "request_item__book__title")
            .annotate(total=Count("id"))
            .order_by("-total", "request_item__book__title")[:10]
        )
        top_books = [
            {
                "book_id": row["request_item__book__id"],
                "book_title": row["request_item__book__title"],
                "total": row["total"],
            }
            for row in top_books_qs
        ]

        # Time series: loans over time in selected period
        if period == "year":
            over_time_qs = (
                Loan.objects.filter(
                    approved_from__gte=start, approved_from__lt=end
                )
                .annotate(month=ExtractMonth("approved_from"))
                .values("month")
                .annotate(total=Count("id"))
            )
            by_key = {row["month"]: row["total"] for row in over_time_qs}
            labels = [str(m) for m in range(1, 13)]
            values = [by_key.get(m, 0) for m in range(1, 13)]
            time_series = {
                "type": "by_month",
                "labels": labels,
                "values": values,
            }
        else:
            # month view: by day
            last_day = calendar.monthrange(year, month)[1]
            over_time_qs = (
                Loan.objects.filter(
                    approved_from__gte=start, approved_from__lt=end
                )
                .annotate(day=ExtractDay("approved_from"))
                .values("day")
                .annotate(total=Count("id"))
            )
            by_key = {row["day"]: row["total"] for row in over_time_qs}
            labels = [str(d) for d in range(1, last_day + 1)]
            values = [by_key.get(d, 0) for d in range(1, last_day + 1)]
            time_series = {
                "type": "by_day",
                "labels": labels,
                "values": values,
            }

        # Top authors in the period
        top_authors_qs = (
            Loan.objects.filter(approved_from__gte=start, approved_from__lt=end)
            .values(
                "request_item__book__authors__id",
                "request_item__book__authors__name",
            )
            .annotate(total=Count("id"))
            .exclude(request_item__book__authors__id__isnull=True)
            .order_by("-total", "request_item__book__authors__name")[:10]
        )
        top_authors = [
            {
                "author_id": row["request_item__book__authors__id"],
                "author_name": row["request_item__book__authors__name"],
                "total": row["total"],
            }
            for row in top_authors_qs
        ]

        # Top publishers in the period
        top_publishers_qs = (
            Loan.objects.filter(approved_from__gte=start, approved_from__lt=end)
            .values(
                "request_item__book__publisher__id",
                "request_item__book__publisher__name",
            )
            .annotate(total=Count("id"))
            .exclude(request_item__book__publisher__id__isnull=True)
            .order_by("-total", "request_item__book__publisher__name")[:10]
        )
        top_publishers = [
            {
                "publisher_id": row["request_item__book__publisher__id"],
                "publisher_name": row["request_item__book__publisher__name"],
                "total": row["total"],
            }
            for row in top_publishers_qs
        ]

        # Status distribution from BorrowRequest (all statuses: PENDING, APPROVED, REJECTED, RETURNED, LOST, OVERDUE)
        status_dist_qs = (
            BorrowRequest.objects.all()
            .values("status")
            .annotate(total=Count("id"))
            .order_by("status")
        )
        status_distribution = [
            {"status": row["status"], "total": row["total"]}
            for row in status_dist_qs
        ]

        # Language distribution from all books in library (not just loaned ones)
        language_dist_qs = (
            Book.objects.all()
            .values("language_code")
            .annotate(total=Count("id"))
            .order_by("-total")
        )
        language_distribution = [
            {
                "language": row["language_code"] or "Unknown",
                "total": row["total"],
            }
            for row in language_dist_qs
        ]
    else:
        # Fallback: Use BorrowRequest-based queries if no Loan records exist
        # Borrow requests by category (via items and book_item)
        approved_requests = BorrowRequest.objects.filter(
            status=BorrowRequest.Status.APPROVED,
            decision_at__gte=start,
            decision_at__lt=end
        ) if hasattr(BorrowRequest, 'decision_at') else BorrowRequest.objects.filter(
            status=BorrowRequest.Status.APPROVED,
            created_at__gte=start,
            created_at__lt=end
        )
        
        # Get books from approved requests via items
        books_in_requests = Book.objects.filter(
            requested_items__request__in=approved_requests
        ).distinct()
        
        # Requests by category
        requests_by_category_qs = (
            books_in_requests
            .values("categories__id", "categories__name")
            .annotate(total=Count("requested_items__id"))
            .exclude(categories__id__isnull=True)
            .order_by("-total", "categories__name")
        )
        loans_by_category = [
            {
                "category_id": row["categories__id"],
                "category_name": row["categories__name"],
                "total": row["total"],
            }
            for row in requests_by_category_qs
        ]

        # Top books
        top_books_qs = (
            books_in_requests
            .annotate(total=Count("requested_items__id"))
            .order_by("-total", "title")[:10]
        )
        top_books = [
            {
                "book_id": book.id,
                "book_title": book.title,
                "total": book.total,
            }
            for book in top_books_qs
        ]

        # Time series
        if period == "year":
            over_time_qs = (
                approved_requests
                .annotate(month=ExtractMonth("created_at"))
                .values("month")
                .annotate(total=Count("id"))
            )
            by_key = {row["month"]: row["total"] for row in over_time_qs}
            labels = [str(m) for m in range(1, 13)]
            values = [by_key.get(m, 0) for m in range(1, 13)]
            time_series = {"type": "by_month", "labels": labels, "values": values}
        else:
            last_day = calendar.monthrange(year, month)[1]
            over_time_qs = (
                approved_requests
                .annotate(day=ExtractDay("created_at"))
                .values("day")
                .annotate(total=Count("id"))
            )
            by_key = {row["day"]: row["total"] for row in over_time_qs}
            labels = [str(d) for d in range(1, last_day + 1)]
            values = [by_key.get(d, 0) for d in range(1, last_day + 1)]
            time_series = {"type": "by_day", "labels": labels, "values": values}

        # Top authors
        top_authors_qs = (
            books_in_requests
            .values("authors__id", "authors__name")
            .annotate(total=Count("requested_items__id"))
            .exclude(authors__id__isnull=True)
            .order_by("-total", "authors__name")[:10]
        )
        top_authors = [
            {
                "author_id": row["authors__id"],
                "author_name": row["authors__name"],
                "total": row["total"],
            }
            for row in top_authors_qs
        ]

        # Top publishers
        top_publishers_qs = (
            books_in_requests
            .values("publisher__id", "publisher__name")
            .annotate(total=Count("requested_items__id"))
            .exclude(publisher__id__isnull=True)
            .order_by("-total", "publisher__name")[:10]
        )
        top_publishers = [
            {
                "publisher_id": row["publisher__id"],
                "publisher_name": row["publisher__name"],
                "total": row["total"],
            }
            for row in top_publishers_qs
        ]

        # Status distribution from BorrowRequest (all statuses: PENDING, APPROVED, REJECTED, RETURNED, LOST, OVERDUE)
        status_dist_qs = (
            BorrowRequest.objects.all()
            .values("status")
            .annotate(total=Count("id"))
            .order_by("status")
        )
        status_distribution = [
            {"status": row["status"], "total": row["total"]}
            for row in status_dist_qs
        ]

        # Language distribution from all books in library (not just loaned ones)
        language_dist_qs = (
            Book.objects.all()
            .values("language_code")
            .annotate(total=Count("id"))
            .order_by("-total")
        )
        language_distribution = [
            {
                "language": row["language_code"] or "Unknown",
                "total": row["total"],
            }
            for row in language_dist_qs
        ]

    top_category = loans_by_category[0] if loans_by_category else None

    data = {
        "period": {
            "type": "year" if period == "year" else "month",
            "year": year,
            "month": month if period != "year" else None,
            "start": start.isoformat(),
            "end_exclusive": end.isoformat(),
        },
        "category_book_counts": category_book_counts,
        "loans_by_category": loans_by_category,
        "top_category": top_category,
        "top_books": top_books,
        "time_series": time_series,
        "top_authors": top_authors,
        "top_publishers": top_publishers,
        "status_distribution": status_distribution,
        "language_distribution": language_distribution,
    }
    return JsonResponse(data)


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
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    resp["Content-Disposition"] = f'attachment; filename="{base}.xlsx"'
    return resp


@staff_member_required
def author_stats_api(request):
    """Author-specific statistics API."""
    
    # Authors with most books
    popular_authors = Author.objects.annotate(
        books_count=Count('books', distinct=True)
    ).filter(books_count__gt=0).order_by('-books_count')[:10]
    
    # Authors by birth year
    authors_by_birth_year = Author.objects.values('birth_date__year').annotate(
        count=Count('id')
    ).exclude(birth_date__isnull=True).order_by('birth_date__year')
    
    # Authors without books
    empty_authors = Author.objects.filter(books__isnull=True).order_by('name')
    
    # Authors with/without biography
    authors_with_biography = Author.objects.exclude(
        Q(biography='') | Q(biography__isnull=True)
    ).order_by('name')
    
    authors_without_biography = Author.objects.filter(
        Q(biography='') | Q(biography__isnull=True)
    ).order_by('name')
    
    # Living vs deceased authors
    living_authors = Author.objects.filter(death_date__isnull=True).order_by('name')
    deceased_authors = Author.objects.filter(death_date__isnull=False).order_by('death_date')
    
    # Recent authors
    recent_authors = Author.objects.order_by('-created_at')[:10]
    
    # Age analysis for deceased authors
    deceased_with_age = []
    for author in deceased_authors:
        if author.birth_date and author.death_date:
            age = author.death_date.year - author.birth_date.year
            deceased_with_age.append({
                "id": author.id,
                "name": author.name,
                "birth_date": author.birth_date,
                "death_date": author.death_date,
                "age": age,
                "books_count": author.books.count(),
            })
    
    data = {
        "popular_authors": [
            {
                "id": author.id,
                "name": author.name,
                "books_count": author.books_count,
                "birth_date": author.birth_date.isoformat() if author.birth_date else None,
                "death_date": author.death_date.isoformat() if author.death_date else None,
                "has_biography": bool(author.biography and author.biography.strip()),
            }
            for author in popular_authors
        ],
        "authors_by_birth_year": [
            {
                "year": item['birth_date__year'],
                "count": item['count']
            }
            for item in authors_by_birth_year
        ],
        "empty_authors": [
            {
                "id": author.id,
                "name": author.name,
                "birth_date": author.birth_date.isoformat() if author.birth_date else None,
                "death_date": author.death_date.isoformat() if author.death_date else None,
                "created_at": author.created_at.isoformat(),
                "has_biography": bool(author.biography and author.biography.strip()),
            }
            for author in empty_authors
        ],
        "biography_stats": {
            "with_biography": [
                {
                    "id": author.id,
                    "name": author.name,
                    "biography_length": len(author.biography or ""),
                    "books_count": author.books.count(),
                    "birth_date": author.birth_date.isoformat() if author.birth_date else None,
                }
                for author in authors_with_biography[:20]  # Limit for performance
            ],
            "without_biography": [
                {
                    "id": author.id,
                    "name": author.name,
                    "books_count": author.books.count(),
                    "birth_date": author.birth_date.isoformat() if author.birth_date else None,
                }
                for author in authors_without_biography[:20]  # Limit for performance
            ]
        },
        "mortality_stats": {
            "living_authors": [
                {
                    "id": author.id,
                    "name": author.name,
                    "birth_date": author.birth_date.isoformat() if author.birth_date else None,
                    "books_count": author.books.count(),
                }
                for author in living_authors[:20]  # Limit for performance
            ],
            "deceased_authors": deceased_with_age
        },
        "recent_authors": [
            {
                "id": author.id,
                "name": author.name,
                "birth_date": author.birth_date.isoformat() if author.birth_date else None,
                "death_date": author.death_date.isoformat() if author.death_date else None,
                "created_at": author.created_at.isoformat(),
                "books_count": author.books.count(),
                "has_biography": bool(author.biography and author.biography.strip()),
            }
            for author in recent_authors
        ],
        "summary": {
            "total_authors": Author.objects.count(),
            "with_books": Author.objects.filter(books__isnull=False).distinct().count(),
            "without_books": Author.objects.filter(books__isnull=True).count(),
            "with_biography": authors_with_biography.count(),
            "without_biography": authors_without_biography.count(),
            "living": living_authors.count(),
            "deceased": deceased_authors.count(),
            "avg_books_per_author": Author.objects.aggregate(
                avg_books=Count('books', distinct=True)
            )['avg_books'] or 0,
            "oldest_birth_year": Author.objects.aggregate(
                oldest=Min('birth_date')
            )['oldest'],
            "newest_birth_year": Author.objects.aggregate(
                newest=Max('birth_date')
            )['newest'],
        }
    }
    return JsonResponse(data)


@staff_member_required
def author_books_api(request, author_id):
    """API to get books for a specific author."""
    try:
        author = Author.objects.get(id=author_id)
    except Author.DoesNotExist:
        return JsonResponse({"error": "Author not found"}, status=404)
    
    books = author.books.all().select_related('publisher').prefetch_related('authors', 'categories')
    
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
            "pages": book.pages,
            "language_code": book.language_code,
            "publisher": book.publisher.name if book.publisher else None,
            "authors": [auth.name for auth in book.authors.all()],
            "categories": [cat.name for cat in book.categories.all()],
            "created_at": book.created_at.isoformat(),
            "updated_at": book.updated_at.isoformat(),
        })
    
    data = {
        "author": {
            "id": author.id,
            "name": author.name,
            "biography": author.biography,
            "birth_date": author.birth_date.isoformat() if author.birth_date else None,
            "death_date": author.death_date.isoformat() if author.death_date else None,
            "created_at": author.created_at.isoformat(),
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
def authors_export_api(request):
    """Export authors data as JSON or CSV."""
    format_type = request.GET.get('format', 'json')
    include_books = request.GET.get('include_books', 'false').lower() == 'true'
    
    authors = Author.objects.all().order_by('name')
    
    if include_books:
        authors = authors.prefetch_related('books')
    
    export_data = []
    for author in authors:
        author_data = {
            "id": author.id,
            "name": author.name,
            "biography": author.biography,
            "birth_date": author.birth_date.isoformat() if author.birth_date else None,
            "death_date": author.death_date.isoformat() if author.death_date else None,
            "created_at": author.created_at.isoformat(),
        }
        
        if include_books:
            author_data["books"] = [
                {
                    "id": book.id,
                    "title": book.title,
                    "isbn13": book.isbn13,
                    "publish_year": book.publish_year,
                }
                for book in author.books.all()
            ]
            author_data["books_count"] = len(author_data["books"])
        else:
            author_data["books_count"] = author.books.count()
        
        export_data.append(author_data)
    
    if format_type == 'csv':
        import csv
        import io
        
        output = io.StringIO()
        fieldnames = ['id', 'name', 'biography', 'birth_date', 'death_date', 'created_at', 'books_count']
        
        if include_books:
            # Flatten books data for CSV
            flattened_data = []
            for author_data in export_data:
                base_row = {k: v for k, v in author_data.items() if k != 'books'}
                if author_data.get('books'):
                    for book in author_data['books']:
                        row = base_row.copy()
                        row.update({f'book_{k}': v for k, v in book.items()})
                        flattened_data.append(row)
                else:
                    flattened_data.append(base_row)
            
            # Update fieldnames for books
            if flattened_data and any('book_id' in row for row in flattened_data):
                fieldnames.extend(['book_id', 'book_title', 'book_isbn13', 'book_publish_year'])
            
            export_data = flattened_data
        
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(export_data)
        
        response = HttpResponse(output.getvalue(), content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="authors_export.csv"'
        return response
    
    else:
        # JSON format (default)
        data = {
            "export_date": timezone.now().isoformat(),
            "total_authors": len(export_data),
            "include_books": include_books,
            "authors": export_data
        }
        return JsonResponse(data, json_dumps_params={'indent': 2})


@staff_member_required
def export_authors_excel(request):
    """Export Excel file with authors data.

    Query parameters:
    - q: search term for name/biography
    - birth_year_from: minimum birth year
    - birth_year_to: maximum birth year
    - death_year_from: minimum death year
    - death_year_to: maximum death year
    - min_books: minimum number of books
    - empty_only: true/false for authors without books
    - has_biography: true/false for authors with/without biography
    - living_only: true/false for living authors only
    - deceased_only: true/false for deceased authors only
    - created_from: date filter (YYYY-MM-DD)
    - created_to: date filter (YYYY-MM-DD)
    - sort: sorting field (name, birth_date, death_date, books_count, created_at)
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
    qs = build_author_queryset(request.GET, include_books=include_books)
    wb = render_authors_workbook(
        qs, columns=columns, include_books=include_books
    )

    # Serialize
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    ts = timezone.now().strftime("%Y%m%d_%H%M%S")
    base = (
        request.GET.get("filename") or f"authors_export_{ts}"
    ).strip() or f"authors_export_{ts}"
    resp = HttpResponse(
        buf.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    resp["Content-Disposition"] = f'attachment; filename="{base}.xlsx"'
    return resp
