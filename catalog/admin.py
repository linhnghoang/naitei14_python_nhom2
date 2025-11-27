from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.db import models
from django.forms import Textarea
from .models import (
    Category,
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
                "description": "Select a parent category to create a subcategory hierarchy.",
            },
        ),
    )

    def books_count(self, obj):
        count = obj.books.count()
        return format_html('<span style="color: #007cba; font-weight: bold;">{} books</span>', count)

    books_count.short_description = "Books"
    books_count.admin_order_field = "books_count"

    def children_count(self, obj):
        count = obj.children.count()
        if count > 0:
            return format_html(
                '<span style="color: blue; font-weight: bold;">{} subcategories</span>', 
                count
            )
        return "No subcategories"

    children_count.short_description = "Subcategories"
    children_count.admin_order_field = "children_count"
    
    def get_queryset(self, request):
        """Optimize queryset with prefetch_related for better performance."""
        queryset = super().get_queryset(request)
        return queryset.select_related('parent').prefetch_related('children', 'books')
    
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
            level='success'
        )
    
    @admin.action(description="Set as subcategories of first selected")
    def make_parent_categories(self, request, queryset):
        """Action to set the first selected category as parent for others."""
        categories = list(queryset)
        if len(categories) < 2:
            self.message_user(
                request,
                "Please select at least 2 categories (first will be parent, others will become subcategories).",
                level='warning'
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
                        f"Cannot set {parent_category.name} as parent for {child.name} - would create circular relationship.",
                        level='error'
                    )
                    return
                temp_parent = temp_parent.parent
        
        # Update the children
        for child in children:
            child.parent = parent_category
            child.save()
        
        self.message_user(
            request,
            f"Successfully set {parent_category.name} as parent for {len(children)} categories.",
            level='success'
        )
