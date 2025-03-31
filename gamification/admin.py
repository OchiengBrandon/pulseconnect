from django.contrib import admin
from .models import Badge, Leaderboard

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



@admin.register(Leaderboard)
class LeaderboardAdmin(admin.ModelAdmin):
    list_display = ('title', 'leaderboard_type', 'time_period', 'max_entries', 'is_active', 'created_at')
    list_filter = ('leaderboard_type', 'time_period', 'is_active')
    search_fields = ('title',)
    ordering = ('-created_at',)

    # Optional: Add additional configurations if needed
    def has_add_permission(self, request):
        # Add custom logic if you want to restrict adding new leaderboards
        return super().has_add_permission(request)

    def has_change_permission(self, request, obj=None):
        # Add custom logic if you want to restrict changing existing leaderboards
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        # Add custom logic if you want to restrict deleting leaderboards
        return super().has_delete_permission(request, obj)