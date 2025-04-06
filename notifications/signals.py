from django.db.models.signals import post_save, m2m_changed
from django.dispatch import receiver
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from django.db.models import Q

from community.models import Discussion, Comment, Event, VolunteerOpportunity, Impact
from polls.models import Poll
from .models import NotificationType
from .services import create_notification


@receiver(post_save, sender=Comment)
def handle_new_comment(sender, instance, created, **kwargs):
    """Create notifications for new comments"""
    if not created:
        return
    
    # Get the commented object
    content_object = instance.content_object
    content_author = None
    
    # Determine content type and author
    if hasattr(content_object, 'creator'):
        content_author = content_object.creator
    elif hasattr(content_object, 'reported_by'):
        content_author = content_object.reported_by
    
    # Don't notify the author of the comment
    if content_author and content_author != instance.user:
        # Notify the author of the content
        create_notification(
            recipient=content_author,
            notification_type=NotificationType.COMMENT,
            content_object=instance,
            actor=instance.user
        )
    
    # If this is a reply to another comment, notify that comment's author
    if instance.parent and instance.parent.user != instance.user:
        create_notification(
            recipient=instance.parent.user,
            notification_type=NotificationType.COMMENT,
            content_object=instance,
            actor=instance.user
        )


@receiver(m2m_changed, sender=Event.attendees.through)
def handle_event_attendance(sender, instance, action, pk_set, **kwargs):
    """Create notifications when a user joins or leaves an event"""
    if action != 'post_add':
        return
    
    # Notify the event creator
    for user_id in pk_set:
        # Get the user who joined
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        try:
            attendee = User.objects.get(pk=user_id)
            
            # Don't notify if the creator joined their own event
            if instance.creator != attendee:
                create_notification(
                    recipient=instance.creator,
                    notification_type=NotificationType.EVENT_ATTENDANCE,
                    content_object=instance,
                    actor=attendee
                )
        except User.DoesNotExist:
            pass


@receiver(m2m_changed, sender=VolunteerOpportunity.interested_users.through)
def handle_opportunity_interest(sender, instance, action, pk_set, **kwargs):
    """Create notifications when a user expresses interest in a volunteer opportunity"""
    if action != 'post_add':
        return
    
    # Notify the opportunity creator
    for user_id in pk_set:
        # Get the user who expressed interest
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        try:
            interested_user = User.objects.get(pk=user_id)
            
            # Don't notify if the creator expressed interest in their own opportunity
            if instance.creator != interested_user:
                create_notification(
                    recipient=instance.creator,
                    notification_type=NotificationType.OPPORTUNITY_INTEREST,
                    content_object=instance,
                    actor=interested_user
                )
        except User.DoesNotExist:
            pass


@receiver(post_save, sender=Impact)
def handle_impact_verification(sender, instance, created, **kwargs):
    """Create notifications when an impact report is verified"""
    # Check if this is an update and verification status changed
    if not created and instance.is_verified:
        # Notify the user who reported the impact
        create_notification(
            recipient=instance.reported_by,
            notification_type=NotificationType.IMPACT_VERIFIED,
            content_object=instance,
            actor=instance.verified_by
        )


# Function to be called by a scheduled task (e.g., Celery)
def send_event_reminders():
    """Send reminders for upcoming events"""
    # Get events starting in the next 24 hours
    from datetime import timedelta
    now = timezone.now()
    tomorrow = now + timedelta(hours=24)
    
    upcoming_events = Event.objects.filter(
        start_datetime__gt=now,
        start_datetime__lte=tomorrow
    )
    
    for event in upcoming_events:
        # Send reminders to all attendees
        for attendee in event.attendees.all():
            create_notification(
                recipient=attendee,
                notification_type=NotificationType.EVENT_REMINDER,
                content_object=event
            )