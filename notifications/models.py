from django.db import models
from django.conf import settings
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType


class NotificationType(models.TextChoices):
    COMMENT = 'comment', _('New Comment')
    EVENT_REMINDER = 'event_reminder', _('Event Reminder')
    EVENT_ATTENDANCE = 'event_attendance', _('New Event Attendee')
    OPPORTUNITY_INTEREST = 'opportunity_interest', _('New Opportunity Interest')
    IMPACT_VERIFIED = 'impact_verified', _('Impact Report Verified')
    MENTION = 'mention', _('User Mention')
    DISCUSSION_REPLY = 'discussion_reply', _('Reply to Your Discussion')
    SYSTEM = 'system', _('System Notification')


class Notification(models.Model):
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications',
        verbose_name=_('Recipient')
    )
    notification_type = models.CharField(
        max_length=50,
        choices=NotificationType.choices,
        verbose_name=_('Notification Type')
    )
    # Generic relation to the object that triggered the notification
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        verbose_name=_('Content Type')
    )
    object_id = models.PositiveIntegerField(verbose_name=_('Object ID'))
    content_object = GenericForeignKey('content_type', 'object_id')
    
    # Actor who triggered the notification (can be null for system notifications)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='triggered_notifications',
        null=True,
        blank=True,
        verbose_name=_('Actor')
    )
    
    title = models.CharField(max_length=255, verbose_name=_('Title'))
    message = models.TextField(verbose_name=_('Message'))
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_('Created At'))
    is_read = models.BooleanField(default=False, verbose_name=_('Read Status'))
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = _('Notification')
        verbose_name_plural = _('Notifications')
        indexes = [
            models.Index(fields=['recipient', 'is_read', 'created_at']),
            models.Index(fields=['content_type', 'object_id'])
        ]
    
    def __str__(self):
        return f"Notification for {self.recipient.username}: {self.title}"
    
    def mark_as_read(self):
        if not self.is_read:
            self.is_read = True
            self.save(update_fields=['is_read'])
    
    def get_absolute_url(self):
        """Return the URL of the content object"""
        if hasattr(self.content_object, 'get_absolute_url'):
            return self.content_object.get_absolute_url()
        return None


class NotificationPreference(models.Model):
    """User preferences for notifications"""
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notification_preferences',
        verbose_name=_('User')
    )
    
    # Email notification preferences
    email_comment = models.BooleanField(default=True, verbose_name=_('Email for comments'))
    email_event_reminder = models.BooleanField(default=True, verbose_name=_('Email for event reminders'))
    email_event_attendance = models.BooleanField(default=True, verbose_name=_('Email for event attendance'))
    email_opportunity_interest = models.BooleanField(default=True, verbose_name=_('Email for opportunity interest'))
    email_impact_verified = models.BooleanField(default=True, verbose_name=_('Email for impact verification'))
    email_mention = models.BooleanField(default=True, verbose_name=_('Email for mentions'))
    email_discussion_reply = models.BooleanField(default=True, verbose_name=_('Email for discussion replies'))
    email_system = models.BooleanField(default=True, verbose_name=_('Email for system notifications'))
    
    # In-app notification preferences
    app_comment = models.BooleanField(default=True, verbose_name=_('In-app for comments'))
    app_event_reminder = models.BooleanField(default=True, verbose_name=_('In-app for event reminders'))
    app_event_attendance = models.BooleanField(default=True, verbose_name=_('In-app for event attendance'))
    app_opportunity_interest = models.BooleanField(default=True, verbose_name=_('In-app for opportunity interest'))
    app_impact_verified = models.BooleanField(default=True, verbose_name=_('In-app for impact verification'))
    app_mention = models.BooleanField(default=True, verbose_name=_('In-app for mentions'))
    app_discussion_reply = models.BooleanField(default=True, verbose_name=_('In-app for discussion replies'))
    app_system = models.BooleanField(default=True, verbose_name=_('In-app for system notifications'))
    
    class Meta:
        verbose_name = _('Notification Preference')
        verbose_name_plural = _('Notification Preferences')
    
    def __str__(self):
        return f"Notification preferences for {self.user.username}"
    
    @classmethod
    def get_or_create_for_user(cls, user):
        """Get or create notification preferences for a user"""
        preferences, created = cls.objects.get_or_create(user=user)
        return preferences