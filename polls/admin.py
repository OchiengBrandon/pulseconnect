from django.contrib import admin
from .models import (
    PollCategory, Poll, PollComment, QuestionType, Question, Choice,
    PollResponse, PollTemplate
)

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

class PollAdmin(admin.ModelAdmin):
    list_display = ('title', 'creator', 'status', 'created_at', 'is_featured')
    list_filter = ('status', 'poll_type', 'is_featured', 'category')
    prepopulated_fields = {'slug': ('title',)}
    search_fields = ('title', 'description')

# Register the Poll model with the admin site
admin.site.register(Poll, PollAdmin)

class PollCommentAdmin(admin.ModelAdmin):
    list_display = ('poll', 'user', 'created_at')
    list_filter = ('poll', 'user')
    search_fields = ('content',)

# Register the PollComment model with the admin site
admin.site.register(PollComment, PollCommentAdmin)

class QuestionAdmin(admin.ModelAdmin):
    list_display = ('text', 'poll', 'question_type', 'is_required', 'order')
    list_filter = ('poll', 'question_type', 'is_required')
    search_fields = ('text',)

# Register the Question model with the admin site
admin.site.register(Question, QuestionAdmin)

class ChoiceAdmin(admin.ModelAdmin):
    list_display = ('question', 'text', 'order')
    list_filter = ('question',)
    search_fields = ('text',)

# Register the Choice model with the admin site
admin.site.register(Choice, ChoiceAdmin)

class PollResponseAdmin(admin.ModelAdmin):
    list_display = ('question', 'user', 'created_at')
    list_filter = ('question', 'user')
    search_fields = ('response_data',)

# Register the PollResponse model with the admin site
admin.site.register(PollResponse, PollResponseAdmin)

class PollTemplateAdmin(admin.ModelAdmin):
    list_display = ('title', 'creator', 'is_public', 'created_at')
    list_filter = ('is_public', 'creator', 'category')
    search_fields = ('title', 'description')

# Register the PollTemplate model with the admin site
admin.site.register(PollTemplate, PollTemplateAdmin)