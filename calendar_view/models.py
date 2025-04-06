from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _

class CalendarPreference(models.Model):
    """User preferences for calendar display"""
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='calendar_preferences',
        verbose_name=_('User')
    )
    
    # Display preferences
    show_community_events = models.BooleanField(default=True, verbose_name=_('Show Community Events'))
    show_volunteer_opportunities = models.BooleanField(default=True, verbose_name=_('Show Volunteer Opportunities'))
    show_polls = models.BooleanField(default=True, verbose_name=_('Show Polls'))
    
    # Color settings
    event_color = models.CharField(max_length=20, default='#3788d8', verbose_name=_('Event Color'))
    opportunity_color = models.CharField(max_length=20, default='#38b87c', verbose_name=_('Opportunity Color'))
    poll_color = models.CharField(max_length=20, default='#ff8c00', verbose_name=_('Poll Color'))
    
    # Notification settings
    notify_upcoming_events = models.BooleanField(default=True, verbose_name=_('Notify for Upcoming Events'))
    notify_days_before = models.PositiveIntegerField(default=1, verbose_name=_('Days Before to Notify'))
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = _('Calendar Preference')
        verbose_name_plural = _('Calendar Preferences')
    
    def __str__(self):
        return f"Calendar preferences for {self.user.username}"