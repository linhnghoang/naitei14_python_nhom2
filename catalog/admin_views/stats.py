"""
Admin statistics API views.
"""
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.utils import timezone
from django.utils.translation import gettext as _
from django.db.models import Count, Q, Min, Max
from django.db.models.functions import ExtractMonth, ExtractDay
from datetime import date, timedelta
import calendar

from ..models import Book, Category, Author, Publisher, BorrowRequest, Loan
from .helpers import time_ago


@staff_member_required
def admin_stats_api(request):
    """Dashboard statistics API with all required data for charts."""
    period = request.GET.get("period", "month")
    year = int(request.GET.get("year", timezone.now().year))
    month = int(request.GET.get("month", timezone.now().month))

    # Basic statistics for cards
    total_books = Book.objects.count()
    total_users = User.objects.filter(is_active=True).count()
    pending_requests = BorrowRequest.objects.filter(
        status=BorrowRequest.Status.PENDING
    ).count()
    overdue_loans = Loan.objects.filter(status=Loan.Status.OVERDUE).count()

    # Category book counts
    category_book_counts = list(
        Category.objects.annotate(total_books=Count("books", distinct=True))
        .filter(total_books__gt=0)
        .order_by("-total_books")
        .values("name", "total_books")
    )

    # Time series: borrow requests over time
    time_series = _build_time_series(period, year, month)

    # Status distribution
    status_distribution = list(
        BorrowRequest.objects.values("status")
        .annotate(total=Count("id"))
        .order_by("-total")
    )

    # Language distribution
    language_distribution = list(
        Book.objects.values("language_code")
        .annotate(total=Count("id"))
        .filter(total__gt=0)
        .exclude(language_code__isnull=True)
        .order_by("-total")
    )
    language_distribution = [
        {"language": item["language_code"], "total": item["total"]}
        for item in language_distribution
    ]

    data = {
        "basic": {
            "total_books": total_books,
            "total_users": total_users,
        },
        "requests": {
            "pending": pending_requests,
        },
        "loans": {
            "overdue": overdue_loans,
        },
        "category_book_counts": category_book_counts,
        "time_series": time_series,
        "status_distribution": status_distribution,
        "language_distribution": language_distribution,
    }
    return JsonResponse(data)


def _build_time_series(period, year, month):
    """Build time series data for borrow requests."""
    if period == "month":
        start_date = date(year, month, 1)
        if month == 12:
            end_date = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            end_date = date(year, month + 1, 1) - timedelta(days=1)

        requests_by_day = list(
            BorrowRequest.objects.filter(created_at__year=year, created_at__month=month)
            .annotate(day=ExtractDay("created_at"))
            .values("day")
            .annotate(count=Count("id"))
            .order_by("day")
        )

        ts_labels = []
        ts_values = []
        current = start_date
        while current <= end_date:
            ts_labels.append(current.strftime("%d/%m"))
            day_data = next(
                (x for x in requests_by_day if x["day"] == current.day), None
            )
            ts_values.append(day_data["count"] if day_data else 0)
            current += timedelta(days=1)
    else:
        requests_by_month = list(
            BorrowRequest.objects.filter(created_at__year=year)
            .annotate(month=ExtractMonth("created_at"))
            .values("month")
            .annotate(count=Count("id"))
            .order_by("month")
        )

        ts_labels = []
        ts_values = []
        for m in range(1, 13):
            ts_labels.append(calendar.month_name[m])
            month_data = next((x for x in requests_by_month if x["month"] == m), None)
            ts_values.append(month_data["count"] if month_data else 0)

    return {"labels": ts_labels, "values": ts_values}


@staff_member_required
def admin_activity_api(request):
    """Recent admin activity API."""
    activities = []

    # Recent categories (with counts annotation)
    recent_categories = (
        Category.objects.annotate(
            books_count=Count("books", distinct=True),
            children_count=Count("children", distinct=True),
        )
        .order_by("-id")[:3]
    )
    for cat in recent_categories:
        activities.append(
            {
                "timestamp": timezone.now(),
                "message": _("Category: %(name)s") % {"name": cat.name},
                "details": (
                    _("Slug: %(slug)s") % {"slug": cat.slug} + " • " +
                    _("Books: %(count)s") % {"count": cat.books_count} + " • " +
                    _("Children: %(count)s") % {"count": cat.children_count}
                ),
                "ago": _("Recently"),
                "type": "category",
            }
        )

    # Recent publishers (with books_count annotation)
    recent_publishers = (
        Publisher.objects.annotate(books_count=Count("books", distinct=True))
        .order_by("-created_at")[:3]
    )
    for pub in recent_publishers:
        founded_str = pub.founded_year or _("Unknown")
        website_str = _("Yes") if pub.website else _("No")
        activities.append(
            {
                "timestamp": pub.created_at,
                "message": _("Publisher: %(name)s") % {"name": pub.name},
                "details": (
                    _("Founded: %(year)s") % {"year": founded_str} + " • " +
                    _("Books: %(count)s") % {"count": pub.books_count} + " • " +
                    _("Website: %(status)s") % {"status": website_str}
                ),
                "ago": time_ago(pub.created_at),
                "type": "publisher",
            }
        )

    # Recent authors (with books_count annotation)
    recent_authors = (
        Author.objects.annotate(books_count=Count("books", distinct=True))
        .order_by("-created_at")[:3]
    )
    for author in recent_authors:
        born_str = author.birth_date or _("Unknown")
        activities.append(
            {
                "timestamp": author.created_at,
                "message": _("Author: %(name)s") % {"name": author.name},
                "details": (
                    _("Born: %(date)s") % {"date": born_str} + " • " +
                    _("Books: %(count)s") % {"count": author.books_count}
                ),
                "ago": time_ago(author.created_at),
                "type": "author",
            }
        )

    # Recent books
    recent_books = Book.objects.order_by("-created_at")[:4]
    for book in recent_books:
        publisher_str = book.publisher or "-"
        year_str = book.publish_year or "-"
        activities.append(
            {
                "timestamp": book.created_at,
                "message": _("New book: %(title)s") % {"title": book.title},
                "details": (
                    _("Publisher: %(name)s") % {"name": publisher_str} + " • " +
                    _("Year: %(year)s") % {"year": year_str}
                ),
                "ago": time_ago(book.created_at),
                "type": "book",
            }
        )

    # Sort mixed activities by timestamp desc and cap to 10
    activities.sort(key=lambda x: x.get("timestamp") or timezone.now(), reverse=True)
    activities = activities[:10]

    return JsonResponse({"activities": activities})


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

    # Publishers with/without websites (with books_count annotation)
    publishers_with_website = (
        Publisher.objects.exclude(Q(website="") | Q(website__isnull=True))
        .annotate(books_count=Count("books", distinct=True))
        .order_by("name")
    )

    publishers_without_website = (
        Publisher.objects.filter(Q(website="") | Q(website__isnull=True))
        .annotate(books_count=Count("books", distinct=True))
        .order_by("name")
    )

    # Recent publishers (with books_count annotation)
    recent_publishers = (
        Publisher.objects.annotate(books_count=Count("books", distinct=True))
        .order_by("-created_at")[:10]
    )

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
                    "books_count": pub.books_count,
                }
                for pub in publishers_with_website
            ],
            "without_website": [
                {
                    "id": pub.id,
                    "name": pub.name,
                    "books_count": pub.books_count,
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
                "books_count": pub.books_count,
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
def author_stats_api(request):
    """Author-specific statistics API."""
    # Authors with most books
    popular_authors = (
        Author.objects.annotate(books_count=Count("books", distinct=True))
        .filter(books_count__gt=0)
        .order_by("-books_count")[:10]
    )

    # Authors by birth year
    authors_by_birth_year = (
        Author.objects.values("birth_date__year")
        .annotate(count=Count("id"))
        .exclude(birth_date__isnull=True)
        .order_by("birth_date__year")
    )

    # Authors without books
    empty_authors = Author.objects.filter(books__isnull=True).order_by("name")

    # Authors with/without biography (with books_count annotation)
    authors_with_biography = (
        Author.objects.exclude(Q(biography="") | Q(biography__isnull=True))
        .annotate(books_count=Count("books", distinct=True))
        .order_by("name")
    )

    authors_without_biography = (
        Author.objects.filter(Q(biography="") | Q(biography__isnull=True))
        .annotate(books_count=Count("books", distinct=True))
        .order_by("name")
    )

    # Living vs deceased authors (with books_count annotation)
    living_authors = (
        Author.objects.filter(death_date__isnull=True)
        .annotate(books_count=Count("books", distinct=True))
        .order_by("name")
    )
    deceased_authors = (
        Author.objects.filter(death_date__isnull=False)
        .annotate(books_count=Count("books", distinct=True))
        .order_by("death_date")
    )

    # Recent authors (with books_count annotation)
    recent_authors = (
        Author.objects.annotate(books_count=Count("books", distinct=True))
        .order_by("-created_at")[:10]
    )

    # Age analysis for deceased authors
    deceased_with_age = []
    for author in deceased_authors:
        if author.birth_date and author.death_date:
            age = author.death_date.year - author.birth_date.year
            deceased_with_age.append(
                {
                    "id": author.id,
                    "name": author.name,
                    "birth_date": author.birth_date,
                    "death_date": author.death_date,
                    "age": age,
                    "books_count": author.books_count,
                }
            )

    data = {
        "popular_authors": [
            {
                "id": author.id,
                "name": author.name,
                "books_count": author.books_count,
                "birth_date": (
                    author.birth_date.isoformat() if author.birth_date else None
                ),
                "death_date": (
                    author.death_date.isoformat() if author.death_date else None
                ),
                "has_biography": bool(author.biography and author.biography.strip()),
            }
            for author in popular_authors
        ],
        "authors_by_birth_year": [
            {"year": item["birth_date__year"], "count": item["count"]}
            for item in authors_by_birth_year
        ],
        "empty_authors": [
            {
                "id": author.id,
                "name": author.name,
                "birth_date": (
                    author.birth_date.isoformat() if author.birth_date else None
                ),
                "death_date": (
                    author.death_date.isoformat() if author.death_date else None
                ),
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
                    "books_count": author.books_count,
                    "birth_date": (
                        author.birth_date.isoformat() if author.birth_date else None
                    ),
                }
                for author in authors_with_biography[:20]
            ],
            "without_biography": [
                {
                    "id": author.id,
                    "name": author.name,
                    "books_count": author.books_count,
                    "birth_date": (
                        author.birth_date.isoformat() if author.birth_date else None
                    ),
                }
                for author in authors_without_biography[:20]
            ],
        },
        "mortality_stats": {
            "living_authors": [
                {
                    "id": author.id,
                    "name": author.name,
                    "birth_date": (
                        author.birth_date.isoformat() if author.birth_date else None
                    ),
                    "books_count": author.books_count,
                }
                for author in living_authors[:20]
            ],
            "deceased_authors": deceased_with_age,
        },
        "recent_authors": [
            {
                "id": author.id,
                "name": author.name,
                "birth_date": (
                    author.birth_date.isoformat() if author.birth_date else None
                ),
                "death_date": (
                    author.death_date.isoformat() if author.death_date else None
                ),
                "created_at": author.created_at.isoformat(),
                "books_count": author.books_count,
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
                avg_books=Count("books", distinct=True)
            )["avg_books"]
            or 0,
            "oldest_birth_year": Author.objects.aggregate(oldest=Min("birth_date"))[
                "oldest"
            ],
            "newest_birth_year": Author.objects.aggregate(newest=Max("birth_date"))[
                "newest"
            ],
        },
    }
    return JsonResponse(data)
