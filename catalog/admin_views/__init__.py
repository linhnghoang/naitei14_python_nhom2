"""
Admin views package for catalog app.

This package provides admin API views for statistics, exports, and data management.
"""
from .helpers import get_pagination_params, time_ago

from .stats import (
    admin_stats_api,
    admin_activity_api,
    publisher_stats_api,
    category_stats_api,
    category_tree_api,
    author_stats_api,
)

from .exports import (
    publisher_books_api,
    publishers_export_api,
    category_books_api,
    category_export_api,
    author_books_api,
    authors_export_api,
    admin_export_books,
    admin_export_categories,
    admin_export_publishers,
    admin_export_authors,
)

# Backwards compatibility aliases for URL configuration
export_books_excel = admin_export_books
export_categories_excel = admin_export_categories
export_publishers_excel = admin_export_publishers
export_authors_excel = admin_export_authors

__all__ = [
    # Helpers
    "get_pagination_params",
    "time_ago",
    # Stats APIs
    "admin_stats_api",
    "admin_activity_api",
    "publisher_stats_api",
    "category_stats_api",
    "category_tree_api",
    "author_stats_api",
    # Export APIs
    "publisher_books_api",
    "publishers_export_api",
    "category_books_api",
    "category_export_api",
    "author_books_api",
    "authors_export_api",
    "admin_export_books",
    "admin_export_categories",
    "admin_export_publishers",
    "admin_export_authors",
    # Backwards compatibility
    "export_books_excel",
    "export_categories_excel",
    "export_publishers_excel",
    "export_authors_excel",
]
