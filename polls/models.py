from django.db import models
from django.utils.translation import gettext_lazy as _
from django.urls import reverse
from django.conf import settings
from django.utils.text import slugify
from taggit.managers import TaggableManager
import uuid
import json

from accounts.models import InstitutionProfile

class PollCategory(models.Model):
    name = models.CharField(max_length=100, verbose_name=_('Name'))
    slug = models.SlugField(unique=True, verbose_name=_('Slug'))
    description = models.TextField(blank=True, verbose_name=_('Description'))
    icon = models.CharField(max_length=50, blank=True, verbose_name=_('Icon'))

    class Meta:
        verbose_name = _('Poll Category')
        verbose_name_plural = _('Poll Categories')
        ordering = ['name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('polls:category', kwargs={'slug': self.slug})


class Poll(models.Model):
    POLL_TYPE_CHOICES = (
        ('public', _('Public')),
        ('anonymous', _('Anonymous')),
        ('institution', _('Institution-specific')),
    )

    POLL_STATUS_CHOICES = (
        ('draft', _('Draft')),
        ('active', _('Active')),
        ('closed', _('Closed')),
        ('archived', _('Archived')),
    )

    title = models.CharField(max_length=255, verbose_name=_('Title'))
    slug = models.SlugField(unique=True, blank=True, verbose_name=_('Slug'))
    description = models.TextField(verbose_name=_('Description'))
    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='created_polls',
        verbose_name=_('Creator')
    )
    category = models.ForeignKey(
        PollCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='polls',
        verbose_name=_('Category')
    )
    poll_type = models.CharField(
        max_length=15,
        choices=POLL_TYPE_CHOICES,
        default='public',
        verbose_name=_('Poll Type')
    )
    status = models.CharField(
        max_length=10,
        choices=POLL_STATUS_CHOICES,
        default='active',
        verbose_name=_('Status')
    )
    start_date = models.DateTimeField(verbose_name=_('Start Date'))
    end_date = models.DateTimeField(blank=True, null=True, verbose_name=_('End Date'))

    # Visibility and access control
    is_featured = models.BooleanField(default=False, verbose_name=_('Featured'))
    allow_comments = models.BooleanField(default=True, verbose_name=_('Allow Comments'))
    allow_sharing = models.BooleanField(default=True, verbose_name=_('Allow Sharing'))
    restricted_to_institution = models.ForeignKey(
        InstitutionProfile,  # Reference to the InstitutionProfile model
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_('Restricted to Institution')
    )

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Tagging
    tags = TaggableManager(blank=True)

    class Meta:
        verbose_name = _('Poll')
        verbose_name_plural = _('Polls')
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
            # Ensure uniqueness
            if Poll.objects.filter(slug=self.slug).exists():
                self.slug = f"{self.slug}-{uuid.uuid4().hex[:8]}"
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('polls:detail', kwargs={'slug': self.slug})

    @property
    def total_responses(self):
        return PollResponse.objects.filter(question__poll=self).count()

    @property
    def total_participants(self):
        return PollResponse.objects.filter(question__poll=self).values('user').distinct().count()

    @property
    def is_active(self):
        return self.status == 'active'


class PollComment(models.Model):
    poll = models.ForeignKey(
        Poll,
        on_delete=models.CASCADE,
        related_name='comments',
        verbose_name=_('Poll')
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='poll_comments',
        verbose_name=_('User')
    )
    content = models.TextField(verbose_name=_('Comment Content'))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_('Created At'))

    class Meta:
        ordering = ['-created_at']  # Optional: to order comments by creation date by default

    def __str__(self):
        return f"{self.user} - {self.content[:20]}..."  # Customize as needed


class QuestionType(models.Model):
    name = models.CharField(max_length=100, verbose_name=_('Name'))
    slug = models.SlugField(unique=True, verbose_name=_('Slug'))
    description = models.TextField(blank=True, verbose_name=_('Description'))
    requires_choices = models.BooleanField(default=False, verbose_name=_('Requires Choices'))  # New field

    class Meta:
        verbose_name = _('Question Type')
        verbose_name_plural = _('Question Types')
    
    def __str__(self):
        return self.name

class Question(models.Model):
    poll = models.ForeignKey(
        Poll,
        on_delete=models.CASCADE,
        related_name='questions',
        verbose_name=_('Poll')
    )
    text = models.TextField(verbose_name=_('Question Text'))
    question_type = models.ForeignKey(
        QuestionType,
        on_delete=models.CASCADE,
        related_name='questions',
        verbose_name=_('Question Type')
    )
    is_required = models.BooleanField(default=True, verbose_name=_('Required'))
    order = models.PositiveIntegerField(default=0, verbose_name=_('Order'))
    
    # For specific question types
    min_value = models.IntegerField(blank=True, null=True, verbose_name=_('Minimum Value'))
    max_value = models.IntegerField(blank=True, null=True, verbose_name=_('Maximum Value'))
    step_value = models.FloatField(blank=True, null=True, verbose_name=_('Step Value'))
    
    # Additional settings as JSON
    settings = models.JSONField(blank=True, null=True, verbose_name=_('Settings'))
    
    class Meta:
        verbose_name = _('Question')
        verbose_name_plural = _('Questions')
        ordering = ['poll', 'order']
    
    def __str__(self):
        return f"{self.poll.title} - {self.text[:50]}"
    
    @property
    def total_responses(self):
        return self.responses.count()
    
    @property
    def response_data(self):
        """Returns aggregated response data for analytics"""
        question_type = self.question_type.slug
        responses = self.responses.all()
        
        if question_type in ['multiple_choice', 'single_choice']:
            choices = Choice.objects.filter(question=self)
            result = {choice.text: 0 for choice in choices}
            
            for response in responses:
                if question_type == 'multiple_choice':
                    selected_choices = json.loads(response.response_data)
                    for choice_id in selected_choices:
                        choice = Choice.objects.get(id=choice_id)
                        result[choice.text] += 1
                else:
                    choice = Choice.objects.get(id=int(response.response_data))
                    result[choice.text] += 1
            
            return result
        
        elif question_type == 'rating':
            result = {i: 0 for i in range(self.min_value, self.max_value + 1)}
            for response in responses:
                value = int(response.response_data)
                result[value] += 1
            return result
        
        elif question_type == 'likert':
            options = ['strongly_disagree', 'disagree', 'neutral', 'agree', 'strongly_agree']
            result = {option: 0 for option in options}
            for response in responses:
                value = response.response_data
                result[value] += 1
            return result
        
        elif question_type == 'open_ended':
            return [response.response_data for response in responses]
        
        return None


class Choice(models.Model):
    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name='choices',
        verbose_name=_('Question')
    )
    text = models.CharField(max_length=255, verbose_name=_('Choice Text'))
    order = models.PositiveIntegerField(default=0, verbose_name=_('Order'))
    
    class Meta:
        verbose_name = _('Choice')
        verbose_name_plural = _('Choices')
        ordering = ['question', 'order']
    
    def __str__(self):
        return f"{self.question.text[:30]} - {self.text}"


class PollResponse(models.Model):
    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name='responses',
        verbose_name=_('Question')
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='poll_responses',
        verbose_name=_('User')
    )
    response_data = models.TextField(verbose_name=_('Response Data'))
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = _('Poll Response')
        verbose_name_plural = _('Poll Responses')
        unique_together = ('question', 'user')
    
    def __str__(self):
        return f"{self.user.username} - {self.question.text[:30]}"


class PollTemplate(models.Model):
    title = models.CharField(max_length=255, verbose_name=_('Title'))
    description = models.TextField(verbose_name=_('Description'))
    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='created_templates',
        verbose_name=_('Creator')
    )
    category = models.ForeignKey(
        PollCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='templates',
        verbose_name=_('Category')
    )
    is_public = models.BooleanField(default=False, verbose_name=_('Public Template'))
    template_data = models.JSONField(verbose_name=_('Template Data'))
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = _('Poll Template')
        verbose_name_plural = _('Poll Templates')
    
    def __str__(self):
        return self.title