"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect
from catalog import admin_views


def home_redirect(request):
    """Redirect root URL to admin interface"""
    return redirect("/admin/")


urlpatterns = [
    # path('superadmin/', admin.site.urls),
    # path('', include('library_management.urls')),
    # path('accounts/', include('accounts.urls')),
    path("", home_redirect, name="home"),
    path("accounts/", include("django.contrib.auth.urls")),
    path("i18n/", include("django.conf.urls.i18n")),
    path("admin/", admin.site.urls),
    # Admin API endpoints for categories
    path("admin/api/stats/", admin_views.admin_stats_api, name="admin_stats_api"),
    path(
        "admin/api/category-stats/",
        admin_views.category_stats_api,
        name="admin_category_stats_api",
    ),
    path(
        "admin/api/category-tree/",
        admin_views.category_tree_api,
        name="admin_category_tree_api",
    ),
    path(
        "admin/api/category/<int:category_id>/books/",
        admin_views.category_books_api,
        name="admin_category_books_api",
    ),
    path(
        "admin/api/category-export/",
        admin_views.category_export_api,
        name="admin_category_export_api",
    ),
    path(
        "admin/api/activity/", admin_views.admin_activity_api, name="admin_activity_api"
    ),
    # Publisher API endpoints
    path(
        "admin/api/publisher-stats/",
        admin_views.publisher_stats_api,
        name="admin_publisher_stats_api",
    ),
    path(
        "admin/api/publisher/<int:publisher_id>/books/",
        admin_views.publisher_books_api,
        name="admin_publisher_books_api",
    ),
    path(
        "admin/api/publishers-export/",
        admin_views.publishers_export_api,
        name="admin_publishers_export_api",
    ),
    # Author API endpoints
    path(
        "admin/api/author-stats/",
        admin_views.author_stats_api,
        name="admin_author_stats_api",
    ),
    path(
        "admin/api/author/<int:author_id>/books/",
        admin_views.author_books_api,
        name="admin_author_books_api",
    ),
    path(
        "admin/api/authors-export/",
        admin_views.authors_export_api,
        name="admin_authors_export_api",
    ),
    # Excel export endpoints
    path(
        "admin/export/categories/",
        admin_views.export_categories_excel,
        name="admin_export_categories_excel",
    ),
    path(
        "admin/export/books/",
        admin_views.export_books_excel,
        name="admin_export_books_excel",
    ),
    path(
        "admin/export/publishers/",
        admin_views.export_publishers_excel,
        name="admin_export_publishers_excel",
    ),
    path(
        "admin/export/authors/",
        admin_views.export_authors_excel,
        name="admin_export_authors_excel",
    ),
]
