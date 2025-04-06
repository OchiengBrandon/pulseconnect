from django.contrib.contenttypes.models import ContentType
from django.utils.translation import gettext as _
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from django.urls import reverse

from .models import Notification, NotificationType, NotificationPreference


def create_notification(recipient, notification_type, content_object, actor=None, title=None, message=None):
    """
    Create a notification for a recipient
    
    Args:
        recipient: User to receive the notification
        notification_type: Type of notification (from NotificationType)
        content_object: The object the notification is about (Discussion, Comment, etc.)
        actor: User who triggered the notification (optional)
        title: Custom title (optional)
        message: Custom message (optional)
    
    Returns:
        Notification object
    """
    if not title or not message:
        # Generate default title and message based on notification type
        title, message = generate_notification_content(
            notification_type, content_object, actor, recipient
        )
    
    content_type = ContentType.objects.get_for_model(content_object)
    
    # Check user preferences before creating notification
    preferences = NotificationPreference.get_or_create_for_user(recipient)
    
    # Check if in-app notification is enabled for this type
    app_pref_field = f"app_{notification_type}"
    if hasattr(preferences, app_pref_field) and getattr(preferences, app_pref_field):
        # Create the notification
        notification = Notification.objects.create(
            recipient=recipient,
            notification_type=notification_type,
            content_type=content_type,
            object_id=content_object.id,
            actor=actor,
            title=title,
            message=message
        )
    else:
        notification = None
    
    # Check if email notification is enabled for this type
    email_pref_field = f"email_{notification_type}"
    if hasattr(preferences, email_pref_field) and getattr(preferences, email_pref_field):
        # Send email notification
        send_notification_email(recipient, title, message, content_object)
    
    return notification


def generate_notification_content(notification_type, content_object, actor, recipient):
    """Generate title and message for notification based on its type"""
    
    if notification_type == NotificationType.COMMENT:
        title = _("New comment")
        # Determine the commented object type (Discussion, Event, etc.)
        object_type = content_object.content_object.__class__.__name__.lower()
        
        if actor:
            message = _("{username} commented on {object_type}: {title}").format(
                username=actor.username,
                object_type=object_type,
                title=content_object.content_object.title
            )
        else:
            message = _("New comment on {object_type}: {title}").format(
                object_type=object_type,
                title=content_object.content_object.title
            )
    
    elif notification_type == NotificationType.EVENT_REMINDER:
        title = _("Event Reminder")
        message = _("Reminder: The event '{title}' is starting soon on {date}").format(
            title=content_object.title,
            date=content_object.start_datetime.strftime("%b %d at %H:%M")
        )
    
    elif notification_type == NotificationType.EVENT_ATTENDANCE:
        title = _("New Event Attendee")
        if actor:
            message = _("{username} is now attending your event: {title}").format(
                username=actor.username,
                title=content_object.title
            )
        else:
            message = _("Someone new is attending your event: {title}").format(
                title=content_object.title
            )
    
    elif notification_type == NotificationType.OPPORTUNITY_INTEREST:
        title = _("Interest in Volunteer Opportunity")
        if actor:
            message = _("{username} is interested in your volunteer opportunity: {title}").format(
                username=actor.username,
                title=content_object.title
            )
        else:
            message = _("Someone is interested in your volunteer opportunity: {title}").format(
                title=content_object.title
            )
    
    elif notification_type == NotificationType.IMPACT_VERIFIED:
        title = _("Impact Report Verified")
        message = _("Your impact report '{title}' has been verified!").format(
            title=content_object.title
        )
    
    elif notification_type == NotificationType.MENTION:
        title = _("You were mentioned")
        if actor:
            message = _("{username} mentioned you in {object_type}: {title}").format(
                username=actor.username,
                object_type=content_object.__class__.__name__.lower(),
                title=content_object.title
            )
        else:
            message = _("You were mentioned in {object_type}: {title}").format(
                object_type=content_object.__class__.__name__.lower(),
                title=content_object.title
            )
    
    elif notification_type == NotificationType.DISCUSSION_REPLY:
        title = _("Reply to Your Discussion")
        if actor:
            message = _("{username} replied to your discussion: {title}").format(
                username=actor.username,
                title=content_object.title
            )
        else:
            message = _("Someone replied to your discussion: {title}").format(
                title=content_object.title
            )
    
    elif notification_type == NotificationType.SYSTEM:
        title = _("System Notification")
        message = str(content_object)
    
    else:
        title = _("Notification")
        message = _("You have a new notification")
    
    return title, message


def send_notification_email(recipient, title, message, content_object):
    """Send an email notification"""
    subject = title
    from_email = settings.DEFAULT_FROM_EMAIL
    recipient_email = recipient.email
    
    # Get content object URL if available
    url = None
    if hasattr(content_object, 'get_absolute_url'):
        url = content_object.get_absolute_url()
    
    # Prepare context for email template
    context = {
        'recipient': recipient,
        'title': title,
        'message': message,
        'content_object': content_object,
        'url': url,
        'site_name': settings.SITE_NAME if hasattr(settings, 'SITE_NAME') else 'Your Community'
    }
    
    # Render email content from template
    html_content = render_to_string('notifications/email/notification.html', context)
    text_content = render_to_string('notifications/email/notification_text.txt', context)
    
    # Send the email
    send_mail(
        subject=subject,
        message=text_content,
        from_email=from_email,
        recipient_list=[recipient_email],
        html_message=html_content,
    )


def mark_all_as_read(user):
    """Mark all notifications for a user as read"""
    return Notification.objects.filter(recipient=user, is_read=False).update(is_read=True)


def get_unread_count(user):
    """Get count of unread notifications for a user"""
    return Notification.objects.filter(recipient=user, is_read=False).count()