from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse, reverse_lazy
from django.http import JsonResponse, HttpResponseRedirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, TemplateView, View
from django.views.decorators.http import require_POST
from django.utils.decorators import method_decorator
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from django.db.models import Q

from .models import Notification, NotificationPreference
from .services import mark_all_as_read, get_unread_count


class NotificationListView(LoginRequiredMixin, ListView):
    """View for listing all notifications for the current user"""
    model = Notification
    template_name = 'notifications/notification_list.html'
    context_object_name = 'notifications'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = Notification.objects.filter(recipient=self.request.user)
        
        # Filter by read status if provided
        read_status = self.request.GET.get('status', '')
        if read_status == 'read':
            queryset = queryset.filter(is_read=True)
        elif read_status == 'unread':
            queryset = queryset.filter(is_read=False)
        
        # Filter by notification type if provided
        notification_type = self.request.GET.get('type', '')
        if notification_type:
            queryset = queryset.filter(notification_type=notification_type)
        
        return queryset.order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['unread_count'] = get_unread_count(self.request.user)
        context['read_status'] = self.request.GET.get('status', '')
        context['notification_type'] = self.request.GET.get('type', '')
        return context


@login_required
def notification_detail(request, pk):
    """View a single notification and mark it as read"""
    notification = get_object_or_404(Notification, pk=pk, recipient=request.user)
    
    # Mark the notification as read
    notification.mark_as_read()
    
    # Redirect to the content object or notifications list
    url = notification.get_absolute_url()
    if url:
        return redirect(url)
    return redirect('notifications:list')


@login_required
@require_POST
def mark_notification_read(request, pk):
    """Mark a single notification as read"""
    notification = get_object_or_404(Notification, pk=pk, recipient=request.user)
    notification.mark_as_read()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'unread_count': get_unread_count(request.user)
        })
    
    # Redirect back to the notifications list
    return redirect('notifications:list')


@login_required
@require_POST
def mark_all_notifications_read(request):
    """Mark all notifications for the current user as read"""
    count = mark_all_as_read(request.user)
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'marked_count': count,
            'unread_count': get_unread_count(request.user)
        })
    
    messages.success(request, _('All notifications marked as read.'))
    return redirect('notifications:list')


@login_required
@require_POST
def delete_notification(request, pk):
    """Delete a notification"""
    notification = get_object_or_404(Notification, pk=pk, recipient=request.user)
    notification.delete()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'unread_count': get_unread_count(request.user)
        })
    
    messages.success(request, _('Notification deleted.'))
    return redirect('notifications:list')


class NotificationPreferenceView(LoginRequiredMixin, TemplateView):
    """View for managing notification preferences"""
    template_name = 'notifications/preferences.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        preferences, created = NotificationPreference.objects.get_or_create(user=self.request.user)
        context['preferences'] = preferences
        return context
    
    def post(self, request, *args, **kwargs):
        preferences, created = NotificationPreference.objects.get_or_create(user=request.user)
        
        # Update email preferences
        for field in [f for f in dir(preferences) if f.startswith('email_')]:
            value = request.POST.get(field, '') == 'on'
            setattr(preferences, field, value)
        
        # Update in-app preferences
        for field in [f for f in dir(preferences) if f.startswith('app_')]:
            value = request.POST.get(field, '') == 'on'
            setattr(preferences, field, value)
        
        preferences.save()
        messages.success(request, _('Notification preferences updated successfully.'))
        return redirect('notifications:preferences')


# JSON endpoints for notifications (for Ajax)
@login_required
def get_notifications_json(request):
    """Get recent notifications for the user as JSON"""
    limit = int(request.GET.get('limit', 5))
    notifications = Notification.objects.filter(
        recipient=request.user
    ).order_by('-created_at')[:limit]
    
    result = {
        'unread_count': get_unread_count(request.user),
        'notifications': [{
            'id': n.id,
            'title': n.title,
            'message': n.message,
            'created_at': n.created_at.isoformat(),
            'is_read': n.is_read,
            'url': n.get_absolute_url() or reverse('notifications:detail', args=[n.id]),
            'actor_name': n.actor.username if n.actor else None,
        } for n in notifications]
    }
    
    return JsonResponse(result)