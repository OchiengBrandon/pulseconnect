from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse, reverse_lazy
from django.http import HttpResponseForbidden, JsonResponse
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import (
    ListView, DetailView, CreateView, UpdateView, DeleteView, TemplateView
)
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.db.models import Q, Count
from django.contrib.contenttypes.models import ContentType
from django.views.decorators.http import require_POST
from django.utils.decorators import method_decorator

from .models import Discussion, Comment, Event, VolunteerOpportunity, Impact
from .forms import (
    DiscussionForm, CommentForm, EventForm, 
    VolunteerOpportunityForm, ImpactForm, ImpactVerificationForm
)
from polls.models import Poll

class DiscussionListView(ListView):
    model = Discussion
    template_name = 'community/discussion_list.html'
    context_object_name = 'discussions'
    paginate_by = 10
    
    def get_queryset(self):
        queryset = Discussion.objects.all()
        
        # Filter by search query if provided
        search_query = self.request.GET.get('q', '')
        if search_query:
            queryset = queryset.filter(
                Q(title__icontains=search_query) | 
                Q(content__icontains=search_query) |
                Q(tags__name__icontains=search_query)
            ).distinct()
        
        # Filter by related poll if provided
        poll_id = self.request.GET.get('poll', '')
        if poll_id and poll_id.isdigit():
            queryset = queryset.filter(related_poll_id=int(poll_id))
        
        # Filter by tag if provided
        tag = self.request.GET.get('tag', '')
        if tag:
            queryset = queryset.filter(tags__name=tag)
        
        # Sort options
        sort_by = self.request.GET.get('sort', 'recent')
        if sort_by == 'popular':
            # Sort by comment count
            discussion_type = ContentType.objects.get_for_model(Discussion)
            queryset = queryset.annotate(
                comment_count=Count('id', filter=Q(
                    id__in=Comment.objects.filter(
                        content_type=discussion_type
                    ).values_list('object_id', flat=True)
                ))
            ).order_by('-is_pinned', '-comment_count')
        else:  # Default to recent
            queryset = queryset.order_by('-is_pinned', '-created_at')
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Add filter parameters to context
        context['search_query'] = self.request.GET.get('q', '')
        context['current_poll'] = self.request.GET.get('poll', '')
        context['current_tag'] = self.request.GET.get('tag', '')
        context['sort_by'] = self.request.GET.get('sort', 'recent')
            
        # Add related polls for filter dropdown
        context['polls'] = Poll.objects.filter(status='active')
        
        # Add pinned discussions separately
        context['pinned_discussions'] = Discussion.objects.filter(is_pinned=True)
        
        return context


class DiscussionDetailView(DetailView):
    model = Discussion
    template_name = 'community/discussion_detail.html'
    context_object_name = 'discussion'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        discussion = self.get_object()
        
        # Get comments for this discussion
        discussion_type = ContentType.objects.get_for_model(Discussion)
        context['comments'] = Comment.objects.filter(
            content_type=discussion_type,
            object_id=discussion.id,
            parent=None  # Only top-level comments
        ).order_by('created_at')
        
        # Add comment form
        context['comment_form'] = CommentForm()
        
        # Add content type to the context
        context['content_type'] = discussion_type  # Add this line
        
        # Add related discussions
        if discussion.tags.exists():
            tags = discussion.tags.all()
            context['related_discussions'] = Discussion.objects.filter(
                tags__in=tags
            ).exclude(id=discussion.id).distinct()[:5]
        
        return context


@method_decorator(login_required, name='dispatch')
class DiscussionCreateView(CreateView):
    model = Discussion
    form_class = DiscussionForm
    template_name = 'community/discussion_form.html'
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        
        # Pre-fill related poll if provided in URL
        poll_id = self.request.GET.get('poll', '')
        if poll_id and poll_id.isdigit():
            try:
                poll = Poll.objects.get(id=int(poll_id))
                if self.request.method == 'GET':
                    kwargs['initial'] = kwargs.get('initial', {})
                    kwargs['initial']['related_poll'] = poll
            except Poll.DoesNotExist:
                pass
        
        return kwargs
    
    def form_valid(self, form):
        form.instance.creator = self.request.user
        messages.success(self.request, _('Discussion created successfully!'))
        
        # Award points for creating a discussion
        from gamification.models import award_points
        award_points(self.request.user, 'discussion_creation')
        
        return super().form_valid(form)


@method_decorator(login_required, name='dispatch')
class DiscussionUpdateView(UserPassesTestMixin, UpdateView):
    model = Discussion
    form_class = DiscussionForm
    template_name = 'community/discussion_form.html'
    
    def test_func(self):
        discussion = self.get_object()
        return self.request.user == discussion.creator
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def form_valid(self, form):
        messages.success(self.request, _('Discussion updated successfully!'))
        return super().form_valid(form)


@method_decorator(login_required, name='dispatch')
class DiscussionDeleteView(UserPassesTestMixin, DeleteView):
    model = Discussion
    template_name = 'community/discussion_confirm_delete.html'
    success_url = reverse_lazy('community:discussion_list')
    
    def test_func(self):
        discussion = self.get_object()
        return self.request.user == discussion.creator
    
    def delete(self, request, *args, **kwargs):
        messages.success(request, _('Discussion deleted successfully!'))
        return super().delete(request, *args, **kwargs)


@login_required
@require_POST
def add_comment(request, content_type_id, object_id):
    """Add a comment to a discussion, poll, etc."""
    content_type = get_object_or_404(ContentType, id=content_type_id)
    content_object = get_object_or_404(content_type.model_class(), id=object_id)
    
    # Check if commenting is allowed (for polls)
    if content_type.model == 'poll':
        if not content_object.allow_comments:
            messages.error(request, _('Comments are not allowed for this poll.'))
            return redirect(content_object.get_absolute_url())
    
    form = CommentForm(request.POST)
    if form.is_valid():
        comment = form.save(commit=False)
        comment.content_type = content_type
        comment.object_id = object_id
        comment.user = request.user
        
        # Handle reply to another comment
        parent_id = request.POST.get('parent_id')
        if parent_id:
            try:
                parent_comment = Comment.objects.get(id=int(parent_id))
                comment.parent = parent_comment
            except Comment.DoesNotExist:
                pass
        
        comment.save()
        
        # Award points for commenting
        from gamification.models import award_points
        award_points(request.user, 'comment')
        
        messages.success(request, _('Comment added successfully!'))
    else:
        messages.error(request, _('Error adding comment.'))
    
    # Redirect back to the content object
    return redirect(content_object.get_absolute_url())


@login_required
@require_POST
def delete_comment(request, comment_id):
    """Delete a comment"""
    comment = get_object_or_404(Comment, id=comment_id)
    
    # Check if user is the comment author
    if request.user != comment.user:
        return HttpResponseForbidden()
    
    # Get the content object for redirection
    content_object = comment.content_object
    
    comment.delete()
    messages.success(request, _('Comment deleted successfully!'))
    
    # Redirect back to the content object
    return redirect(content_object.get_absolute_url())


class EventListView(ListView):
    model = Event
    template_name = 'community/event_list.html'
    context_object_name = 'events'
    paginate_by = 10
    
    def get_queryset(self):
        queryset = Event.objects.filter(
            Q(is_public=True) | Q(creator=self.request.user)
        ).distinct()
        
        # Filter by search query if provided
        search_query = self.request.GET.get('q', '')
        if search_query:
            queryset = queryset.filter(
                Q(title__icontains=search_query) | 
                Q(description__icontains=search_query) |
                Q(location__icontains=search_query)
            ).distinct()
        
        # Filter by related poll if provided
        poll_id = self.request.GET.get('poll', '')
        if poll_id and poll_id.isdigit():
            queryset = queryset.filter(related_poll_id=int(poll_id))
        
        # Filter by time period
        time_filter = self.request.GET.get('time', 'upcoming')
        if time_filter == 'past':
            queryset = queryset.filter(end_datetime__lt=timezone.now())
        elif time_filter == 'today':
            today = timezone.now().date()
            queryset = queryset.filter(
                start_datetime__date=today
            )
        else:  # Default to upcoming
            queryset = queryset.filter(end_datetime__gte=timezone.now())
        
        # Sort by date
        queryset = queryset.order_by('start_datetime')
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Add filter parameters to context
        context['search_query'] = self.request.GET.get('q', '')
        context['current_poll'] = self.request.GET.get('poll', '')
        context['time_filter'] = self.request.GET.get('time', 'upcoming')
        
        # Add related polls for filter dropdown
        context['polls'] = Poll.objects.filter(status='active')
        
        # Add featured events separately
        context['featured_events'] = Event.objects.filter(
            is_featured=True,
            end_datetime__gte=timezone.now()
        )
        
        return context


from django.utils import timezone
from django.views.generic import DetailView
from django.contrib.contenttypes.models import ContentType

class EventDetailView(DetailView):
    model = Event
    template_name = 'community/event_detail.html'
    context_object_name = 'event'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        event = self.get_object()
        
        # Check if user is attending
        user_attending = False
        if self.request.user.is_authenticated:
            user_attending = event.attendees.filter(id=self.request.user.id).exists()
        
        context['user_attending'] = user_attending
        context['attendees'] = event.attendees.all()
        
        # Calculate delays for attendees
        context['attendee_delays'] = [i * 50 for i in range(len(context['attendees']))]
        
        # Get comments for this event
        event_type = ContentType.objects.get_for_model(Event)
        context['comments'] = Comment.objects.filter(
            content_type=event_type,
            object_id=event.id
        ).order_by('created_at')
        
        # Add the content_type_id to the context
        context['content_type_id'] = event_type.id
        
        # Add comment form
        context['comment_form'] = CommentForm()
        
        # Determine if the event is upcoming
        context['is_upcoming'] = event.end_datetime > timezone.now()
        
        return context
@method_decorator(login_required, name='dispatch')
class EventCreateView(CreateView):
    model = Event
    form_class = EventForm
    template_name = 'community/event_form.html'
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        
        # Pre-fill related poll if provided in URL
        poll_id = self.request.GET.get('poll', '')
        if poll_id and poll_id.isdigit():
            try:
                poll = Poll.objects.get(id=int(poll_id))
                if self.request.method == 'GET':
                    kwargs['initial'] = kwargs.get('initial', {})
                    kwargs['initial']['related_poll'] = poll
            except Poll.DoesNotExist:
                pass
        
        return kwargs
    
    def form_valid(self, form):
        form.instance.creator = self.request.user
        messages.success(self.request, _('Event created successfully!'))
        return super().form_valid(form)


@method_decorator(login_required, name='dispatch')
class EventUpdateView(UserPassesTestMixin, UpdateView):
    model = Event
    form_class = EventForm
    template_name = 'community/event_form.html'
    
    def test_func(self):
        event = self.get_object()
        return self.request.user == event.creator
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def form_valid(self, form):
        messages.success(self.request, _('Event updated successfully!'))
        return super().form_valid(form)


@method_decorator(login_required, name='dispatch')
class EventDeleteView(UserPassesTestMixin, DeleteView):
    model = Event
    template_name = 'community/event_confirm_delete.html'
    success_url = reverse_lazy('community:event_list')
    
    def test_func(self):
        event = self.get_object()
        return self.request.user == event.creator
    
    def delete(self, request, *args, **kwargs):
        messages.success(request, _('Event deleted successfully!'))
        return super().delete(request, *args, **kwargs)


@login_required
@require_POST
def toggle_event_attendance(request, pk):
    """Toggle attendance for an event"""
    event = get_object_or_404(Event, pk=pk)
    
    # Check if the event is past
    if event.is_past:
        messages.error(request, _('Cannot change attendance for past events.'))
        return redirect('community:event_detail', slug=event.slug)
    
    user = request.user
    
    # Toggle attendance
    if event.attendees.filter(id=user.id).exists():
        event.attendees.remove(user)
        messages.success(request, _('You are no longer attending this event.'))
    else:
        event.attendees.add(user)
        messages.success(request, _('You are now attending this event.'))
    
    return redirect('community:event_detail', slug=event.slug)


class VolunteerOpportunityListView(ListView):
    model = VolunteerOpportunity
    template_name = 'community/opportunity_list.html'
    context_object_name = 'opportunities'
    paginate_by = 10
    
    def get_queryset(self):
        queryset = VolunteerOpportunity.objects.filter(is_active=True)
        
        # Filter by search query if provided
        search_query = self.request.GET.get('q', '')
        if search_query:
            queryset = queryset.filter(
                Q(title__icontains=search_query) | 
                Q(description__icontains=search_query) |
                Q(organization__icontains=search_query) |
                Q(location__icontains=search_query) |
                Q(tags__name__icontains=search_query)
            ).distinct()
        
        # Filter by related poll if provided
        poll_id = self.request.GET.get('poll', '')
        if poll_id and poll_id.isdigit():
            queryset = queryset.filter(related_poll_id=int(poll_id))
        
        # Filter by tag if provided
        tag = self.request.GET.get('tag', '')
        if tag:
            queryset = queryset.filter(tags__name=tag)
        
        # Filter by time period
        time_filter = self.request.GET.get('time', 'current')
        if time_filter == 'past':
            queryset = queryset.filter(end_date__lt=timezone.now().date())
        elif time_filter == 'upcoming':
            queryset = queryset.filter(start_date__gt=timezone.now().date())
        else:  # Default to current
            today = timezone.now().date()
            queryset = queryset.filter(
                Q(end_date__isnull=True) | Q(end_date__gte=today),
                start_date__lte=today
            )
        
        # Sort by date
        queryset = queryset.order_by('start_date')
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Add filter parameters to context
        context['search_query'] = self.request.GET.get('q', '')
        context['current_poll'] = self.request.GET.get('poll', '')
        context['current_tag'] = self.request.GET.get('tag', '')
        context['time_filter'] = self.request.GET.get('time', 'current')
        
        # Add related polls for filter dropdown
        context['polls'] = Poll.objects.filter(status='active')
        
        return context
from django.contrib.contenttypes.models import ContentType

class VolunteerOpportunityDetailView(DetailView):
    model = VolunteerOpportunity
    template_name = 'community/opportunity_detail.html'
    context_object_name = 'opportunity'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        opportunity = self.get_object()
        
        # Check if user is interested
        user_interested = False
        if self.request.user.is_authenticated:
            user_interested = opportunity.interested_users.filter(id=self.request.user.id).exists()
        
        context['user_interested'] = user_interested
        
        # Get interested users
        context['interested_users'] = opportunity.interested_users.all()
        
        # Get comments for this opportunity
        opportunity_type = ContentType.objects.get_for_model(VolunteerOpportunity)
        context['comments'] = Comment.objects.filter(
            content_type=opportunity_type,
            object_id=opportunity.id
        ).order_by('created_at')
        
        # Add the content_type_id to the context
        context['content_type_id'] = opportunity_type.id  # Add this line
        
        # Add comment form
        context['comment_form'] = CommentForm()
        
        # Get similar opportunities
        if opportunity.tags.exists():
            tags = opportunity.tags.all()
            context['similar_opportunities'] = VolunteerOpportunity.objects.filter(
                tags__in=tags,
                is_active=True
            ).exclude(id=opportunity.id).distinct()[:5]
        
        return context

@method_decorator(login_required, name='dispatch')
class VolunteerOpportunityCreateView(CreateView):
    model = VolunteerOpportunity
    form_class = VolunteerOpportunityForm
    template_name = 'community/opportunity_form.html'
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        
        # Pre-fill related poll if provided in URL
        poll_id = self.request.GET.get('poll', '')
        if poll_id and poll_id.isdigit():
            try:
                poll = Poll.objects.get(id=int(poll_id))
                if self.request.method == 'GET':
                    kwargs['initial'] = kwargs.get('initial', {})
                    kwargs['initial']['related_poll'] = poll
            except Poll.DoesNotExist:
                pass
        
        return kwargs
    
    def form_valid(self, form):
        form.instance.creator = self.request.user
        messages.success(self.request, _('Volunteer opportunity created successfully!'))
        return super().form_valid(form)


@method_decorator(login_required, name='dispatch')
class VolunteerOpportunityUpdateView(UserPassesTestMixin, UpdateView):
    model = VolunteerOpportunity
    form_class = VolunteerOpportunityForm
    template_name = 'community/opportunity_form.html'
    
    def test_func(self):
        opportunity = self.get_object()
        return self.request.user == opportunity.creator
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def form_valid(self, form):
        messages.success(self.request, _('Volunteer opportunity updated successfully!'))
        return super().form_valid(form)


@method_decorator(login_required, name='dispatch')
class VolunteerOpportunityDeleteView(UserPassesTestMixin, DeleteView):
    model = VolunteerOpportunity
    template_name = 'community/opportunity_confirm_delete.html'
    success_url = reverse_lazy('community:opportunity_list')
    
    def test_func(self):
        opportunity = self.get_object()
        return self.request.user == opportunity.creator
    
    def delete(self, request, *args, **kwargs):
        messages.success(request, _('Volunteer opportunity deleted successfully!'))
        return super().delete(request, *args, **kwargs)


@login_required
@require_POST
def toggle_opportunity_interest(request, pk):
    """Toggle interest in a volunteer opportunity"""
    opportunity = get_object_or_404(VolunteerOpportunity, pk=pk)
    
    # Check if the opportunity is active
    if not opportunity.is_active:
        messages.error(request, _('This volunteer opportunity is no longer active.'))
        return redirect('community:opportunity_detail', slug=opportunity.slug)
    
    user = request.user
    
    # Toggle interest
    if opportunity.interested_users.filter(id=user.id).exists():
        opportunity.interested_users.remove(user)
        messages.success(request, _('You are no longer interested in this opportunity.'))
    else:
        opportunity.interested_users.add(user)
        messages.success(request, _('You have expressed interest in this opportunity.'))
    
    return redirect('community:opportunity_detail', slug=opportunity.slug)


class ImpactListView(ListView):
    model = Impact
    template_name = 'community/impact_list.html'
    context_object_name = 'impacts'
    paginate_by = 10
    
    def get_queryset(self):
        queryset = Impact.objects.all()
        
        # Filter by verified status
        verified = self.request.GET.get('verified', '')
        if verified == 'yes':
            queryset = queryset.filter(is_verified=True)
        elif verified == 'no':
            queryset = queryset.filter(is_verified=False)
        
        # Filter by related poll if provided
        poll_id = self.request.GET.get('poll', '')
        if poll_id and poll_id.isdigit():
            queryset = queryset.filter(poll_id=int(poll_id))
        
        # Filter by impact type if provided
        impact_type = self.request.GET.get('type', '')
        if impact_type:
            queryset = queryset.filter(impact_type=impact_type)
        
        # Search
        search_query = self.request.GET.get('q', '')
        if search_query:
            queryset = queryset.filter(
                Q(title__icontains=search_query) | 
                Q(description__icontains=search_query) |
                Q(outcome__icontains=search_query)
            ).distinct()
        
        return queryset.order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Add filter parameters to context
        context['verified_filter'] = self.request.GET.get('verified', '')
        context['current_poll'] = self.request.GET.get('poll', '')
        context['impact_type'] = self.request.GET.get('type', '')
        context['search_query'] = self.request.GET.get('q', '')
        
        # Add related polls for filter dropdown
        context['polls'] = Poll.objects.filter(status='active')
        
        # Get distinct impact types for filter
        context['impact_types'] = Impact.objects.values_list('impact_type', flat=True).distinct()
        
        return context


class ImpactDetailView(DetailView):
    model = Impact
    template_name = 'community/impact_detail.html'
    context_object_name = 'impact'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        impact = self.get_object()
        
        # Add verification form for staff users
        if self.request.user.is_staff:
            context['verification_form'] = ImpactVerificationForm(initial={
                'verify': impact.is_verified
            })
        
        # Add related impacts
        context['related_impacts'] = Impact.objects.filter(
            poll=impact.poll
        ).exclude(id=impact.id)[:5]
        
        return context


@method_decorator(login_required, name='dispatch')
class ImpactCreateView(CreateView):
    model = Impact
    form_class = ImpactForm
    template_name = 'community/impact_form.html'
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        
        # Pre-fill poll if provided in URL
        poll_id = self.request.GET.get('poll', '')
        if poll_id and poll_id.isdigit():
            try:
                poll = Poll.objects.get(id=int(poll_id))
                if self.request.method == 'GET':
                    kwargs['initial'] = kwargs.get('initial', {})
                    kwargs['initial']['poll'] = poll
            except Poll.DoesNotExist:
                pass
        
        return kwargs
    
    def form_valid(self, form):
        form.instance.reported_by = self.request.user
        messages.success(self.request, _('Impact report submitted successfully! It will be reviewed by our team.'))
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse('community:impact_detail', kwargs={'pk': self.object.pk})


@login_required
@require_POST
def verify_impact(request, pk):
    """Verify or unverify an impact report (staff only)"""
    if not request.user.is_staff:
        return HttpResponseForbidden()
    
    impact = get_object_or_404(Impact, pk=pk)
    form = ImpactVerificationForm(request.POST)
    
    if form.is_valid():
        verify = form.cleaned_data['verify']
        notes = form.cleaned_data['notes']
        
        impact.is_verified = verify
        impact.verified_by = request.user if verify else None
        impact.save()
        
        if verify:
            messages.success(request, _('Impact report verified successfully!'))
        else:
            messages.success(request, _('Impact report unverified.'))
    
    return redirect('community:impact_detail', pk=impact.pk)


class CommunityDashboardView(TemplateView):
    template_name = 'community/dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Recent discussions
        context['recent_discussions'] = Discussion.objects.order_by('-created_at')[:5]
        
        # Upcoming events
        context['upcoming_events'] = Event.objects.filter(
            end_datetime__gte=timezone.now(),
            is_public=True
        ).order_by('start_datetime')[:5]
        
        # Recent volunteer opportunities
        context['recent_opportunities'] = VolunteerOpportunity.objects.filter(
            is_active=True
        ).order_by('-created_at')[:5]
        
        # Verified impacts
        context['verified_impacts'] = Impact.objects.filter(
            is_verified=True
        ).order_by('-created_at')[:5]
        
        # Active polls
        context['active_polls'] = Poll.objects.filter(
            status='active'
        ).order_by('-created_at')[:5]
        
        return context