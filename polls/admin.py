from django.contrib import admin
from .models import PollCategory, QuestionType

class PollCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'description', 'icon')
    prepopulated_fields = {'slug': ('name',)}  # Automatically populate the slug field
    search_fields = ('name', 'description')  # Add a search bar for name and description

# Register the PollCategory model with the admin site
admin.site.register(PollCategory, PollCategoryAdmin)

class QuestionTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'description')
    prepopulated_fields = {'slug': ('name',)}  # Automatically populate the slug field
    search_fields = ('name', 'description')  # Add a search bar for name and description

# Register the QuestionType model with the admin site
admin.site.register(QuestionType, QuestionTypeAdmin)