from django.contrib import admin
from .models import Badge

class BadgeAdmin(admin.ModelAdmin):
    list_display = ('name', 'level', 'requirement_type', 'requirement_count', 'created_at')
    search_fields = ('name', 'description')
    list_filter = ('level', 'requirement_type')
    ordering = ('-created_at',)

    def has_change_permission(self, request, obj=None):
        # Disable editing of existing badges
        return True

    def has_delete_permission(self, request, obj=None):
        # Optionally disable deletion
        return False

    def has_view_permission(self, request, obj=None):
        # Optionally disable viewing existing badges
        return True

# Register the Badge model with the customized admin
admin.site.register(Badge, BadgeAdmin)