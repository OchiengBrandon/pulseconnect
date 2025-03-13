from django.db import models
from django.utils.translation import gettext_lazy as _
from django.conf import settings
from django.urls import reverse
from django.utils.text import slugify
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from taggit.managers import TaggableManager
import uuid

class Discussion(models.Model):
    """Discussion forums for community engagement"""
    title = models.CharField(max_length=255, verbose_name=_('Title'))
    slug = models.SlugField(unique=True, blank=True, verbose_name=_('Slug'))
    content = models.TextField(verbose_name=_('Content'))
    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='discussions',
        verbose_name=_('Creator')
    )
    
    # Optional related poll
    related_poll = models.ForeignKey(
        'polls.Poll',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='discussions',
        verbose_name=_('Related Poll')
    )
    
    # Visibility and access control
    is_pinned = models.BooleanField(default=False, verbose_name=_('Pinned'))
    is_closed = models.BooleanField(default=False, verbose_name=_('Closed'))
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Tagging
    tags = TaggableManager(blank=True)
    
    class Meta:
        verbose_name = _('Discussion')
        verbose_name_plural = _('Discussions')
        ordering = ['-is_pinned', '-created_at']
    
    def __str__(self):
        return self.title
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
            # Ensure uniqueness
            if Discussion.objects.filter(slug=self.slug).exists():
                self.slug = f"{self.slug}-{uuid.uuid4().hex[:8]}"
        super().save(*args, **kwargs)
    
    def get_absolute_url(self):
        return reverse('community:discussion_detail', kwargs={'slug': self.slug})
    
    @property
    def comment_count(self):
        return Comment.objects.filter(
            content_type=ContentType.objects.get_for_model(self),
            object_id=self.id
        ).count()


class Comment(models.Model):
    """Comments for discussions, polls, etc."""
    # Generic foreign key for commenting on different types of content
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')
    
    content = models.TextField(verbose_name=_('Content'))
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='comments',
        verbose_name=_('User')
    )
    
    # For threaded comments
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='replies',
        verbose_name=_('Parent Comment')
    )
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = _('Comment')
        verbose_name_plural = _('Comments')
        ordering = ['created_at']
    
    def __str__(self):
        return f"Comment by {self.user.username} on {self.content_object}"
    
    @property
    def is_reply(self):
        return self.parent is not None
    
    @property
    def reply_count(self):
        return self.replies.count()


class Event(models.Model):
    """Community events calendar"""
    title = models.CharField(max_length=255, verbose_name=_('Title'))
    slug = models.SlugField(unique=True, blank=True, verbose_name=_('Slug'))
    description = models.TextField(verbose_name=_('Description'))
    location = models.CharField(max_length=255, blank=True, verbose_name=_('Location'))
    is_virtual = models.BooleanField(default=False, verbose_name=_('Virtual Event'))
    virtual_link = models.URLField(blank=True, verbose_name=_('Virtual Link'))
    
    start_datetime = models.DateTimeField(verbose_name=_('Start Date/Time'))
    end_datetime = models.DateTimeField(verbose_name=_('End Date/Time'))
    
    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='created_events',
        verbose_name=_('Creator')
    )
    
    # Optional related poll
    related_poll = models.ForeignKey(
        'polls.Poll',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='events',
        verbose_name=_('Related Poll')
    )
    
    # Attendees
    attendees = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='attending_events',
        blank=True,
        verbose_name=_('Attendees')
    )
    
    # Visibility and access control
    is_featured = models.BooleanField(default=False, verbose_name=_('Featured'))
    is_public = models.BooleanField(default=True, verbose_name=_('Public'))
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = _('Event')
        verbose_name_plural = _('Events')
        ordering = ['start_datetime']
    
    def __str__(self):
        return self.title
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
            # Ensure uniqueness
            if Event.objects.filter(slug=self.slug).exists():
                self.slug = f"{self.slug}-{uuid.uuid4().hex[:8]}"
        super().save(*args, **kwargs)
    
    def get_absolute_url(self):
        return reverse('community:event_detail', kwargs={'slug': self.slug})
    
    @property
    def is_past(self):
        from django.utils import timezone
        return self.end_datetime < timezone.now()
    
    @property
    def attendee_count(self):
        return self.attendees.count()


class VolunteerOpportunity(models.Model):
    """Volunteer opportunities based on poll topics"""
    title = models.CharField(max_length=255, verbose_name=_('Title'))
    slug = models.SlugField(unique=True, blank=True, verbose_name=_('Slug'))
    description = models.TextField(verbose_name=_('Description'))
    organization = models.CharField(max_length=255, verbose_name=_('Organization'))
    location = models.CharField(max_length=255, blank=True, verbose_name=_('Location'))
    
    # Contact information
    contact_email = models.EmailField(verbose_name=_('Contact Email'))
    contact_phone = models.CharField(max_length=20, blank=True, verbose_name=_('Contact Phone'))
    
    # Dates
    start_date = models.DateField(verbose_name=_('Start Date'))
    end_date = models.DateField(blank=True, null=True, verbose_name=_('End Date'))
    
    # Creator
    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='created_opportunities',
        verbose_name=_('Creator')
    )
    
    # Optional related poll
    related_poll = models.ForeignKey(
        'polls.Poll',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='volunteer_opportunities',
        verbose_name=_('Related Poll')
    )
    
    # Interested volunteers
    interested_users = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='interested_opportunities',
        blank=True,
        verbose_name=_('Interested Users')
    )
    
    # Status
    is_active = models.BooleanField(default=True, verbose_name=_('Active'))
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Tagging
    tags = TaggableManager(blank=True)
    
    class Meta:
        verbose_name = _('Volunteer Opportunity')
        verbose_name_plural = _('Volunteer Opportunities')
        ordering = ['-created_at']
    
    def __str__(self):
        return self.title
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
            # Ensure uniqueness
            if VolunteerOpportunity.objects.filter(slug=self.slug).exists():
                self.slug = f"{self.slug}-{uuid.uuid4().hex[:8]}"
        super().save(*args, **kwargs)
    
    def get_absolute_url(self):
        return reverse('community:opportunity_detail', kwargs={'slug': self.slug})
    
    @property
    def is_past(self):
        from django.utils import timezone
        return self.end_date and self.end_date < timezone.now().date()
    
    @property
    def interested_count(self):
        return self.interested_users.count()


class Impact(models.Model):
    """Track the impact of polls on community decisions"""
    title = models.CharField(max_length=255, verbose_name=_('Title'))
    description = models.TextField(verbose_name=_('Description'))
    
    # Related poll
    poll = models.ForeignKey(
        'polls.Poll',
        on_delete=models.CASCADE,
        related_name='impacts',
        verbose_name=_('Poll')
    )
    
    # Impact details
    impact_type = models.CharField(max_length=100, verbose_name=_('Impact Type'))
    outcome = models.TextField(verbose_name=_('Outcome'))
    
    # Who reported this impact
    reported_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='reported_impacts',
        verbose_name=_('Reported By')
    )
    
    # Evidence
    evidence = models.TextField(blank=True, verbose_name=_('Evidence'))
    evidence_url = models.URLField(blank=True, verbose_name=_('Evidence URL'))
    
    # Verification
    is_verified = models.BooleanField(default=False, verbose_name=_('Verified'))
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='verified_impacts',
        verbose_name=_('Verified By')
    )
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = _('Impact')
        verbose_name_plural = _('Impacts')
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Impact of {self.poll.title}: {self.title}"