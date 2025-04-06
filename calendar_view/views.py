from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.http import JsonResponse
from django.views.generic import TemplateView, UpdateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db.models import Q

from .models import CalendarPreference
from .forms import CalendarPreferenceForm
from community.models import Event, VolunteerOpportunity
from polls.models import Poll

import datetime
import json


class CalendarView(LoginRequiredMixin, TemplateView):
    """Main calendar view showing events, opportunities, polls"""
    template_name = 'calendar_view/calendar.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # Get or create user's calendar preferences
        preferences, created = CalendarPreference.objects.get_or_create(user=user)
        context['preferences'] = preferences
        
        # Get default view based on URL parameter or default to month
        view_type = self.request.GET.get('view', 'month')
        context['view_type'] = view_type
        
        # Get current date for calendar focus
        today = timezone.now().date()
        year = self.request.GET.get('year')
        month = self.request.GET.get('month')
        
        if year and month:
            try:
                focus_date = datetime.date(int(year), int(month), 1)
            except (ValueError, TypeError):
                focus_date = today
        else:
            focus_date = today
            
        context['focus_date'] = focus_date
        context['today'] = today
        
        return context


@login_required
def get_calendar_events(request):
    """API endpoint to get events for the calendar in JSON format"""
    # Get date range from request
    start_str = request.GET.get('start')
    end_str = request.GET.get('end')
    
    # Parse dates
    try:
        start_date = datetime.datetime.fromisoformat(start_str.replace('Z', '+00:00'))
        end_date = datetime.datetime.fromisoformat(end_str.replace('Z', '+00:00'))
    except (ValueError, AttributeError):
        # Default to current month if parsing fails
        today = timezone.now()
        start_date = datetime.datetime(today.year, today.month, 1)
        end_date = (datetime.datetime(today.year, today.month + 1, 1) 
                   if today.month < 12 
                   else datetime.datetime(today.year + 1, 1, 1))
    
    # Get user preferences
    user = request.user
    preferences, _ = CalendarPreference.objects.get_or_create(user=user)
    
    calendar_events = []
    
    # Community Events
    if preferences.show_community_events:
        events = Event.objects.filter(
            Q(end_datetime__gte=start_date) & Q(start_datetime__lte=end_date),
            Q(is_public=True) | Q(creator=user) | Q(attendees=user)
        ).distinct()
        
        for event in events:
            attending = event.attendees.filter(id=user.id).exists()
            calendar_events.append({
                'id': f'event_{event.id}',
                'title': event.title,
                'start': event.start_datetime.isoformat(),
                'end': event.end_datetime.isoformat(),
                'url': reverse('community:event_detail', kwargs={'slug': event.slug}),
                'backgroundColor': preferences.event_color,
                'borderColor': preferences.event_color,
                'textColor': '#ffffff',
                'extendedProps': {
                    'type': 'event',
                    'attending': attending,
                    'location': event.location if not event.is_virtual else 'Virtual',
                    'isVirtual': event.is_virtual,
                    'description': event.description[:100] + '...' if len(event.description) > 100 else event.description
                }
            })
    
    # Volunteer Opportunities
    if preferences.show_volunteer_opportunities:
        opportunities = VolunteerOpportunity.objects.filter(
            Q(is_active=True),
            Q(start_date__lte=end_date.date()) & 
            (Q(end_date__isnull=True) | Q(end_date__gte=start_date.date()))
        )
        
        for opportunity in opportunities:
            interested = opportunity.interested_users.filter(id=user.id).exists()
            # Create all-day event for the start date
            calendar_events.append({
                'id': f'opportunity_{opportunity.id}',
                'title': opportunity.title,
                'start': opportunity.start_date.isoformat(),
                'end': opportunity.end_date.isoformat() if opportunity.end_date else None,
                'allDay': True,
                'url': reverse('community:opportunity_detail', kwargs={'slug': opportunity.slug}),
                'backgroundColor': preferences.opportunity_color,
                'borderColor': preferences.opportunity_color,
                'textColor': '#ffffff',
                'extendedProps': {
                    'type': 'opportunity',
                    'interested': interested,
                    'location': opportunity.location,
                    'organization': opportunity.organization,
                    'description': opportunity.description[:100] + '...' if len(opportunity.description) > 100 else opportunity.description
                }
            })
    
    # Polls
    if preferences.show_polls:
        polls = Poll.objects.filter(
            Q(status='active'),
            Q(end_date__gte=start_date.date()) & Q(start_date__lte=end_date.date())
        )
        
        for poll in polls:
            has_voted = poll.votes.filter(user=user).exists()
            # Create deadline event for the poll
            calendar_events.append({
                'id': f'poll_{poll.id}',
                'title': f"Poll: {poll.title}",
                'start': poll.end_date.isoformat(),
                'allDay': True,
                'url': reverse('polls:poll_detail', kwargs={'slug': poll.slug}),
                'backgroundColor': preferences.poll_color,
                'borderColor': preferences.poll_color,
                'textColor': '#ffffff',
                'extendedProps': {
                    'type': 'poll',
                    'hasVoted': has_voted,
                    'startDate': poll.start_date.isoformat(),
                    'description': poll.description[:100] + '...' if len(poll.description) > 100 else poll.description
                }
            })
    
    return JsonResponse(calendar_events, safe=False)


class CalendarPreferenceView(LoginRequiredMixin, UpdateView):
    """View to update calendar preferences"""
    model = CalendarPreference
    form_class = CalendarPreferenceForm
    template_name = 'calendar_view/preferences.html'
    
    def get_object(self):
        # Get or create preferences for the current user
        preferences, created = CalendarPreference.objects.get_or_create(user=self.request.user)
        return preferences
    
    def get_success_url(self):
        return reverse('calendar_view:calendar')


@login_required
def add_event_to_calendar(request, event_id):
    """Quick toggle to attend an event from calendar view"""
    event = get_object_or_404(Event, id=event_id)
    user = request.user
    
    # Toggle attendance
    if event.attendees.filter(id=user.id).exists():
        event.attendees.remove(user)
        attending = False
    else:
        event.attendees.add(user)
        attending = True
    
    # Return JSON response for AJAX handling
    return JsonResponse({
        'success': True,
        'attending': attending,
        'attendee_count': event.attendee_count
    })