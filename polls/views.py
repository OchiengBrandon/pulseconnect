from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse, reverse_lazy
from django.http import HttpResponseForbidden, JsonResponse
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import (
    ListView, DetailView, CreateView, UpdateView, DeleteView, TemplateView
)
from django.contrib import messages
from django.contrib.messages.views import SuccessMessageMixin
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.db.models import Count, Q
from django.core.paginator import Paginator
from django.views.decorators.http import require_POST
from django.utils.decorators import method_decorator
from django.db import transaction

from .models import (
    Poll, PollComment, Question, Choice, PollResponse, 
    PollTemplate, PollCategory, QuestionType
)
from .forms import (
    PollCommentForm, PollForm, QuestionForm, ChoiceForm, 
    QuestionFormSet, ChoiceFormSet, 
    PollResponseForm, PollTemplateForm,
    PollCategoryForm, QuestionTypeForm
)

class PollListView(ListView):
    model = Poll
    template_name = 'polls/poll_list.html'
    context_object_name = 'polls'
    paginate_by = 12
    
    def get_queryset(self):
        queryset = Poll.objects.filter(status='active')
        
        # Filter by category if provided
        category_slug = self.kwargs.get('category_slug')
        if category_slug:
            queryset = queryset.filter(category__slug=category_slug)
        
        # Filter by search query if provided
        search_query = self.request.GET.get('q', '')
        if search_query:
            queryset = queryset.filter(
                Q(title__icontains=search_query) | 
                Q(description__icontains=search_query) |
                Q(tags__name__icontains=search_query)
            ).distinct()
        
        # Filter by poll type
        poll_type = self.request.GET.get('type', '')
        if poll_type and poll_type in dict(Poll.POLL_TYPE_CHOICES).keys():
            queryset = queryset.filter(poll_type=poll_type)
        
        # Filter by institution if applicable
        if self.request.user.is_authenticated and poll_type == 'institution':
            user_institution = self.request.user.institution
            queryset = queryset.filter(restricted_to_institution=user_institution)
        
        # Sort options
        sort_by = self.request.GET.get('sort', 'recent')
        if sort_by == 'popular':
            queryset = queryset.annotate(response_count=Count('questions__responses')).order_by('-response_count')
        elif sort_by == 'ending_soon':
            queryset = queryset.filter(end_date__isnull=False).order_by('end_date')
        else:  # Default to recent
            queryset = queryset.order_by('-created_at')
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['categories'] = PollCategory.objects.all()
        context['featured_polls'] = Poll.objects.filter(is_featured=True, status='active')[:5]
        
        # Add filter parameters to context
        context['current_category'] = self.kwargs.get('category_slug', '')
        context['search_query'] = self.request.GET.get('q', '')
        context['current_type'] = self.request.GET.get('type', '')
        context['sort_by'] = self.request.GET.get('sort', 'recent')
        
        return context


class PollDetailView(DetailView):
    model = Poll
    template_name = 'polls/poll_detail.html'
    context_object_name = 'poll'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        poll = self.get_object()
        
        # Check if user has already responded
        user_responded = False
        if self.request.user.is_authenticated:
            user_responded = PollResponse.objects.filter(
                question__poll=poll,
                user=self.request.user
            ).exists()
        
        context['user_responded'] = user_responded
        
        # If user has not responded and poll is active, show response form
        if not user_responded and poll.status == 'active' and self.request.user.is_authenticated:
            context['response_form'] = PollResponseForm(poll=poll, user=self.request.user)
        
        # Get poll statistics
        context['total_responses'] = poll.total_responses
        context['total_participants'] = poll.total_participants
        
        # Get related polls
        if poll.category:
            context['related_polls'] = Poll.objects.filter(
                category=poll.category,
                status='active'
            ).exclude(id=poll.id)[:4]
        
        # Get comments from community app
        from community.models import Comment
        context['comments'] = Comment.objects.filter(
            content_type__model='poll',
            object_id=poll.id
        ).order_by('-created_at')
        
        return context

# Poll Creation
@method_decorator(login_required, name='dispatch')
class PollCreateView(CreateView):
    model = Poll
    form_class = PollForm
    template_name = 'polls/poll_create.html'
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['creator'] = self.request.user
        return kwargs
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Initialize or process formsets
        if self.request.POST:
            context['question_formset'] = QuestionFormSet(self.request.POST, instance=self.object)
        else:
            context['question_formset'] = QuestionFormSet(instance=self.object)
        
        # Add all question types for the UI
        context['question_types'] = QuestionType.objects.all()
        
        # Group question types by category for better UX
        question_types_by_category = {
            'basic': QuestionType.objects.filter(slug__in=['single_choice', 'multiple_choice', 'open_ended', 'short_answer', 'true_false']),
            'choice': QuestionType.objects.filter(slug__in=['single_choice', 'multiple_choice']),
            'scale': QuestionType.objects.filter(slug__in=['rating_scale', 'likert_scale']),
            'text': QuestionType.objects.filter(slug__in=['essay']),
        }
        context['question_types_by_category'] = question_types_by_category
        
        # Add empty choice formset for JavaScript to use as template
        context['empty_choice_form'] = ChoiceForm(prefix='__prefix__')
        
        return context
    
    @transaction.atomic
    def form_valid(self, form):
        context = self.get_context_data()
        question_formset = context['question_formset']
        
        if not question_formset.is_valid():
            return self.form_invalid(form)
        
        # Save the poll with the creator
        self.object = form.save(commit=False)
        self.object.creator = self.request.user
        self.object.save()
        form.save_m2m()  # Save tags and other M2M relationships
        
        # Process and save questions
        questions = question_formset.save(commit=False)
        for i, question_form in enumerate(question_formset):
            if question_form.is_valid() and not question_form.cleaned_data.get('DELETE', False):
                question = question_form.save(commit=False)
                question.poll = self.object
                question.save()
                
                # Process question type specific requirements
                question_type = question.question_type
                question_slug = question_type.slug
                
                # Handle question types that need choices
                if question_type.requires_choices or question_slug in ['single_choice', 'multiple_choice', 'true_false']:
                    # For true/false, add predefined choices if none exist
                    if question_slug == 'true_false':
                        Choice.objects.create(question=question, text=_('True'), order=1)
                        Choice.objects.create(question=question, text=_('False'), order=2)
                    else:
                        # Get choices from the POST data
                        choice_prefix = f"question_{i}"
                        
                        # Extract all choice fields for this question
                        choices_data = []
                        choice_index = 0
                        
                        # Keep looking for choices until we don't find any more
                        while f'{choice_prefix}_choice_{choice_index}' in self.request.POST:
                            choice_value = self.request.POST[f'{choice_prefix}_choice_{choice_index}'].strip()
                            if choice_value:
                                choices_data.append(choice_value)
                            choice_index += 1
                        
                        # If no choices were found using the index approach, try the older method
                        if not choices_data:
                            for key, value in self.request.POST.items():
                                if key.startswith(f'{choice_prefix}_choice_') and value.strip():
                                    choices_data.append(value.strip())
                        
                        # Create choices
                        for j, choice_text in enumerate(choices_data):
                            Choice.objects.create(
                                question=question,
                                text=choice_text,
                                order=j + 1
                            )
                
                # Handle Likert scale default options if no custom options provided
                if question_slug == 'likert_scale' and not question.choices.exists():
                    likert_options = [
                        (_('Strongly Disagree'), 1),
                        (_('Disagree'), 2),
                        (_('Neutral'), 3),
                        (_('Agree'), 4),
                        (_('Strongly Agree'), 5)
                    ]
                    for text, order in likert_options:
                        Choice.objects.create(
                            question=question,
                            text=text,
                            order=order
                        )
                
                # Handle rating scale default values if not provided
                if question_slug == 'rating_scale':
                    if question.min_value is None:
                        question.min_value = 1
                    if question.max_value is None:
                        question.max_value = 5
                    question.save()
        
        # Handle deleted questions
        for deleted_form in question_formset.deleted_forms:
            if deleted_form.instance.pk:
                deleted_form.instance.delete()
        
        messages.success(self.request, _('Poll created successfully!'))
        return redirect(self.get_success_url())
    
    def form_invalid(self, form):
        """Handle form validation errors"""
        messages.error(self.request, _('Please correct the errors below.'))
        
        # Log specific errors for debugging
        for field, errors in form.errors.items():
            for error in errors:
                messages.error(self.request, f"{field}: {error}")
        
        # Check for formset errors
        context = self.get_context_data()
        question_formset = context.get('question_formset')
        
        if question_formset and question_formset.non_form_errors():
            for error in question_formset.non_form_errors():
                messages.error(self.request, f"Questions: {error}")
        
        if question_formset:
            for i, question_form in enumerate(question_formset.forms):
                if question_form.errors:
                    messages.error(self.request, f"Question #{i+1} has errors")
                    
                    # Add detailed error messages for each field
                    for field, errors in question_form.errors.items():
                        for error in errors:
                            messages.error(self.request, f"Question #{i+1} {field}: {error}")
        
        return super().form_invalid(form)
    
    def get_success_url(self):
        if self.object and self.object.slug:
            return reverse('polls:detail', kwargs={'slug': self.object.slug})
        return reverse('polls:poll_list')
    
    # Add AJAX support for dynamic question type loading
    def get_question_type_details(self, request):
        """AJAX endpoint to get question type details"""
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            type_id = request.GET.get('type_id')
            if type_id:
                try:
                    question_type = QuestionType.objects.get(id=type_id)
                    return JsonResponse({
                        'requires_choices': question_type.requires_choices,
                        'slug': question_type.slug,
                        'name': question_type.name,
                    })
                except QuestionType.DoesNotExist:
                    return JsonResponse({'error': 'Question type not found'}, status=404)
        
        return JsonResponse({'error': 'Invalid request'}, status=400)
class PollUpdateView(UserPassesTestMixin, SuccessMessageMixin, UpdateView):
    model = Poll
    form_class = PollForm
    template_name = 'polls/poll_update.html'
    success_message = _('Poll updated successfully!')

    def test_func(self):
        poll = self.get_object()
        return self.request.user == poll.creator
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['creator'] = self.request.user  # Ensure this matches the PollForm
        return kwargs
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        if self.request.POST:
            context['question_formset'] = QuestionFormSet(
                self.request.POST, 
                instance=self.object
            )
        else:
            context['question_formset'] = QuestionFormSet(instance=self.object)
            
            # Add choices to each question form
            for question_form in context['question_formset']:
                question = question_form.instance
                if question.id:
                    choices = Choice.objects.filter(question=question).order_by('order')
                    question_form.choices = choices
        
        return context
    
    @transaction.atomic
    def form_valid(self, form):
        context = self.get_context_data()
        question_formset = context['question_formset']
        
        if question_formset.is_valid():
            self.object = form.save()
            question_formset.instance = self.object
            question_formset.save()
            
            # Process each question to update choices
            for question_form in question_formset:
                if not question_form.cleaned_data.get('DELETE', False):
                    question = question_form.instance
                    
                    # Delete existing choices if we're updating them
                    if f'question_{question.id}_choices' in self.request.POST:
                        Choice.objects.filter(question=question).delete()
                        
                        # Create new choices
                        choices_data = self.request.POST.getlist(f'question_{question.id}_choices', [])
                        for i, choice_text in enumerate(choices_data):
                            if choice_text.strip():
                                Choice.objects.create(
                                    question=question,
                                    text=choice_text.strip(),
                                    order=i
                                )
            
            messages.success(self.request, self.success_message)
            return redirect(self.get_success_url())
        else:
            return self.form_invalid(form)
    
    def get_success_url(self):
        return reverse('polls:detail', kwargs={'slug': self.object.slug})

@method_decorator(login_required, name='dispatch')
class PollDeleteView(UserPassesTestMixin, DeleteView):
    model = Poll
    template_name = 'polls/poll_confirm_delete.html'
    success_url = reverse_lazy('polls:my_polls')
    
    def test_func(self):
        poll = self.get_object()
        return self.request.user == poll.creator


from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib import messages
from django.utils.translation import gettext_lazy as _

@login_required
def submit_poll_response(request, slug):
    poll = get_object_or_404(Poll, slug=slug, status='active')

    # Check if the user has already responded
    # Fixed query: Accessing poll through question instead of directly
    if PollResponse.objects.filter(question__poll=poll, user=request.user).exists():
        messages.error(request, _('You have already responded to this poll.'))
        return redirect('polls:detail', slug=slug)

    # Check if the poll is restricted to an institution
    if poll.poll_type == 'institution' and request.user.institution != poll.restricted_to_institution:
        messages.error(request, _('This poll is restricted to members of a specific institution.'))
        return redirect('polls:list')

    if request.method == 'POST':
        form = PollResponseForm(request.POST, poll=poll, user=request.user)
        
        if form.is_valid():
            form.save()
            messages.success(request, _('Your response has been recorded. Thank you for participating!'))
            return redirect('polls:results', slug=slug)
    else:
        form = PollResponseForm(poll=poll, user=request.user)

    # Prepare rating ranges for questions of type 'rating_scale'
    rating_ranges = {
        question.id: range(question.min_value or 1, (question.max_value or 5) + 1)
        for question in poll.questions.all()
        if question.question_type.slug == 'rating_scale'
    }

    return render(request, 'polls/poll_respond.html', {
        'form': form,
        'poll': poll,
        'rating_ranges': rating_ranges,  # Pass the ranges to the template
    })


from django.views.generic import DetailView
from django.db.models import Count, Avg, Sum, Q
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404

from .models import Poll, PollResponse, Choice


class PollResultsView(DetailView):
    model = Poll
    template_name = 'polls/poll_results.html'
    context_object_name = 'poll'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        poll = self.get_object()
        
        # Basic poll statistics
        total_responses = poll.total_responses
        total_participants = poll.total_participants
        
        # Calculate completion rate (if poll has multiple questions)
        completion_rate = 0
        if poll.questions.count() > 0:
            completion_rate = (total_responses / (poll.questions.count() * total_participants)) * 100 if total_participants > 0 else 0
        
        # Get time-based metrics
        response_timeline = self.get_response_timeline(poll)
        
        # User demographic data if available and not anonymous
        demographics = {}
        if poll.poll_type != 'anonymous':
            demographics = self.get_demographic_data(poll)
        
        # Prepare detailed data for each question
        questions_data = []
        
        for question in poll.questions.all():
            question_data = {
                'id': question.id,
                'text': question.text,
                'type': question.question_type.slug,
                'response_count': question.responses.count(),
                'chart_data': self.prepare_chart_data(question),
                'statistics': self.get_question_statistics(question),
                'correlations': self.get_correlations(question, poll) if poll.questions.count() > 1 else {},
            }
            questions_data.append(question_data)
        
        # Add data to context
        context.update({
            'total_responses': total_responses,
            'total_participants': total_participants,
            'completion_rate': completion_rate,
            'response_timeline': response_timeline,
            'demographics': demographics,
            'questions_data': questions_data,
            'has_correlations': poll.questions.count() > 1,
            'average_completion_time': self.get_average_completion_time(poll),
            'is_active': poll.status == 'active',
            'end_date': poll.end_date,
            'days_remaining': (poll.end_date - timezone.now()).days if poll.end_date and poll.end_date > timezone.now() else 0,
            'can_export': self.request.user == poll.creator or (hasattr(self.request.user, 'user_type') and self.request.user.user_type == 'researcher'),
        })
        
        return context
    
    def prepare_chart_data(self, question):
        """Prepare data for charts based on question type"""
        question_type = question.question_type.slug
        chart_data = {
            'labels': [],
            'datasets': [],
            'chart_type': 'bar'  # Default chart type
        }
        
        if question_type in ['single_choice', 'multiple_choice', 'true_false']:
            # Count responses for each choice
            choices = Choice.objects.filter(question=question).order_by('order')
            response_counts = []
            
            for choice in choices:
                chart_data['labels'].append(choice.text)
                
                # Count responses that include this choice
                count = PollResponse.objects.filter(
                    question=question,
                    response_data__contains=str(choice.id)
                ).count()
                
                response_counts.append(count)
            
            chart_data['datasets'].append({
                'label': 'Responses',
                'data': response_counts,
                'backgroundColor': self.get_chart_colors(len(choices))
            })
            
        elif question_type == 'rating_scale':
            # For rating scales, show distribution of ratings
            min_value = question.min_value or 1
            max_value = question.max_value or 5
            
            for value in range(min_value, max_value + 1):
                chart_data['labels'].append(str(value))
                
            # Count responses for each rating value
            counts = []
            for value in range(min_value, max_value + 1):
                count = PollResponse.objects.filter(
                    question=question,
                    response_data=str(value)
                ).count()
                counts.append(count)
            
            chart_data['datasets'].append({
                'label': 'Rating Distribution',
                'data': counts,
                'backgroundColor': self.get_chart_colors(max_value - min_value + 1)
            })
            
        elif question_type == 'likert_scale':
            # Similar to rating but with text labels
            choices = Choice.objects.filter(question=question).order_by('order')
            response_counts = []
            
            for choice in choices:
                chart_data['labels'].append(choice.text)
                count = PollResponse.objects.filter(
                    question=question,
                    response_data=str(choice.id)
                ).count()
                response_counts.append(count)
            
            chart_data['datasets'].append({
                'label': 'Responses',
                'data': response_counts,
                'backgroundColor': self.get_chart_colors(len(choices))
            })
            
        elif question_type in ['open_ended', 'short_answer', 'essay']:
            # For text responses, provide word frequency data
            chart_data['chart_type'] = 'wordcloud'
            # Word frequency would be calculated in the template or via an API
            
        return chart_data
    
    def get_chart_colors(self, count):
        """Generate a list of colors for charts"""
        base_colors = [
            'rgba(54, 162, 235, 0.7)',   # Blue
            'rgba(255, 99, 132, 0.7)',   # Pink
            'rgba(255, 206, 86, 0.7)',   # Yellow
            'rgba(75, 192, 192, 0.7)',   # Teal
            'rgba(153, 102, 255, 0.7)',  # Purple
            'rgba(255, 159, 64, 0.7)',   # Orange
            'rgba(199, 199, 199, 0.7)',  # Gray
            'rgba(83, 102, 255, 0.7)',   # Indigo
            'rgba(255, 99, 71, 0.7)',    # Tomato
            'rgba(50, 205, 50, 0.7)',    # Lime
        ]
        
        # If we need more colors than we have base colors, repeat the pattern
        colors = []
        for i in range(count):
            colors.append(base_colors[i % len(base_colors)])
        
        return colors
    
    def get_response_timeline(self, poll):
        """Get response data over time"""
        # Get all responses for this poll
        responses = PollResponse.objects.filter(question__poll=poll).order_by('created_at')
        
        if not responses.exists():
            return {'dates': [], 'counts': []}
        
        # Get response counts by date
        from collections import Counter
        from django.db.models.functions import TruncDate
        
        date_counts = responses.annotate(date=TruncDate('created_at')).values('date').annotate(count=Count('id')).order_by('date')
        
        dates = []
        counts = []
        cumulative_count = 0
        
        for item in date_counts:
            dates.append(item['date'].strftime('%Y-%m-%d'))
            cumulative_count += item['count']
            counts.append(cumulative_count)
        
        return {
            'dates': dates,
            'counts': counts
        }
    
    def get_demographic_data(self, poll):
        """Get demographic information of poll respondents if available"""
        # This is a placeholder - actual implementation depends on your user model
        demographics = {
            'gender': {},
            'age_groups': {},
            'locations': {}
        }
        
        # Example: Get gender distribution
        # Requires User model to have a gender field
        responses = PollResponse.objects.filter(question__poll=poll).select_related('user').distinct('user')
        
        # This is commented out because it depends on your specific User model
        # gender_counts = responses.values('user__gender').annotate(count=Count('user__gender'))
        # for item in gender_counts:
        #     if item['user__gender']:
        #         demographics['gender'][item['user__gender']] = item['count']
        
        return demographics
    
    def get_question_statistics(self, question):
        """Get statistical data for the question responses"""
        stats = {
            'count': question.responses.count(),
            'skip_rate': 0,
        }
        
        question_type = question.question_type.slug
        
        # Add type-specific statistics
        if question_type in ['rating_scale', 'likert_scale']:
            # For numeric ratings
            if question_type == 'rating_scale':
                # Try to calculate average rating
                try:
                    # Assuming response_data contains numeric values
                    avg_rating = PollResponse.objects.filter(question=question).exclude(
                        response_data=''
                    ).aggregate(avg=Avg('response_data'))['avg']
                    
                    if avg_rating is not None:
                        stats['average'] = float(avg_rating)
                except:
                    stats['average'] = None
            
        elif question_type in ['single_choice', 'multiple_choice']:
            # Most common response
            most_common = None
            max_count = 0
            
            for choice in question.choices.all():
                count = PollResponse.objects.filter(
                    question=question,
                    response_data__contains=str(choice.id)
                ).count()
                
                if count > max_count:
                    max_count = count
                    most_common = choice.text
            
            stats['most_common'] = most_common
            stats['most_common_count'] = max_count
            
            # Calculate diversity of answers (how spread out the responses are)
            total = question.responses.count()
            if total > 0:
                choice_counts = []
                for choice in question.choices.all():
                    count = PollResponse.objects.filter(
                        question=question,
                        response_data__contains=str(choice.id)
                    ).count()
                    choice_counts.append(count / total)
                
                # Calculate entropy as a measure of diversity
                import math
                entropy = 0
                for p in choice_counts:
                    if p > 0:
                        entropy -= p * math.log2(p)
                stats['diversity'] = entropy / math.log2(len(choice_counts)) if len(choice_counts) > 1 else 0
        
        return stats
    
    def get_correlations(self, question, poll):
        """Find correlations between this question and others"""
        correlations = []
        
        # Skip for text questions or if there are too few responses
        question_type = question.question_type.slug
        if question_type in ['open_ended', 'short_answer', 'essay'] or question.responses.count() < 10:
            return correlations
        
        # Look for correlations with other questions
        for other_question in poll.questions.exclude(id=question.id):
            other_type = other_question.question_type.slug
            
            # Skip text questions
            if other_type in ['open_ended', 'short_answer', 'essay']:
                continue
            
            # Simple correlation check: do people who choose X for question 1 tend to choose Y for question 2?
            # This is a simplified example
            if question_type in ['single_choice', 'multiple_choice'] and other_type in ['single_choice', 'multiple_choice']:
                for choice in question.choices.all():
                    for other_choice in other_question.choices.all():
                        # Count how many selected both choices
                        joint_count = PollResponse.objects.filter(
                            question=question,
                            response_data__contains=str(choice.id),
                            user__in=PollResponse.objects.filter(
                                question=other_question,
                                response_data__contains=str(other_choice.id)
                            ).values('user')
                        ).count()
                        
                        # If significant correlation
                        if joint_count >= 3:  # Arbitrary threshold
                            correlations.append({
                                'question': other_question.text,
                                'this_choice': choice.text,
                                'other_choice': other_choice.text,
                                'count': joint_count
                            })
        
        return correlations
    
    def get_average_completion_time(self, poll):
        """Estimate average time to complete the poll"""
        # This is just an estimate - actual implementation depends on tracking when users start and finish
        # A simple estimate could be based on question count
        question_count = poll.questions.count()
        
        # Assume average time per question based on question type
        avg_seconds_per_question = {
            'single_choice': 10,
            'multiple_choice': 15,
            'open_ended': 60,
            'short_answer': 30,
            'true_false': 5,
            'rating_scale': 8,
            'likert_scale': 12,
            'essay': 180
        }
        
        total_seconds = 0
        for question in poll.questions.all():
            q_type = question.question_type.slug
            total_seconds += avg_seconds_per_question.get(q_type, 20)  # Default 20 seconds
        
        # Return as minutes
        return round(total_seconds / 60, 1)


@login_required
def my_polls(request):
    """View for displaying polls created by the current user"""
    polls = Poll.objects.filter(creator=request.user).order_by('-created_at')
    
    # Apply filters
    status_filter = request.GET.get('status', '')
    if status_filter:
        polls = polls.filter(status=status_filter)
    
    # Pagination
    paginator = Paginator(polls, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'polls/my_polls.html', {
        'page_obj': page_obj,
        'status_filter': status_filter,
    })


@login_required
def my_responses(request):
    """View for displaying polls the user has responded to"""
    responses = PollResponse.objects.filter(user=request.user).select_related('question__poll').order_by('-created_at')
    
    # Group by poll
    polls_responded = {}
    for response in responses:
        poll = response.question.poll
        if poll.id not in polls_responded:
            polls_responded[poll.id] = {
                'poll': poll,
                'responded_at': response.created_at
            }
    
    # Convert to list and sort by response date
    polls_list = list(polls_responded.values())
    polls_list.sort(key=lambda x: x['responded_at'], reverse=True)
    
    # Pagination
    paginator = Paginator(polls_list, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'polls/my_responses.html', {
        'page_obj': page_obj,
    })


@login_required
@require_POST
def change_poll_status(request, pk):
    """Change the status of a poll"""
    poll = get_object_or_404(Poll, pk=pk)
    
    # Check if user is the creator
    if request.user != poll.creator:
        return HttpResponseForbidden()
    
    new_status = request.POST.get('status')
    if new_status in dict(Poll.POLL_STATUS_CHOICES).keys():
        poll.status = new_status
        poll.save()
        messages.success(request, _('Poll status updated successfully!'))
    else:
        messages.error(request, _('Invalid status.'))
    
    return redirect('polls:my_polls')


@login_required
def save_as_template(request, slug):
    """Save a poll as a template"""
    poll = get_object_or_404(Poll, slug=slug)  # Use slug here

    # Check if user is the creator
    if request.user != poll.creator:
        return HttpResponseForbidden()

    if request.method == 'POST':
        form = PollTemplateForm(request.POST, user=request.user)
        if form.is_valid():
            template = form.save(commit=False)
            template.creator = request.user
            template.category = poll.category

            # Create template data from poll
            template_data = {
                'title': poll.title,
                'description': poll.description,
                'poll_type': poll.poll_type,
                'questions': []
            }

            for question in poll.questions.all():
                q_data = {
                    'text': question.text,
                    'question_type': question.question_type.slug,
                    'is_required': question.is_required,
                    'order': question.order,
                    'min_value': question.min_value,
                    'max_value': question.max_value,
                    'step_value': question.step_value,
                    'settings': question.settings,
                    'choices': []
                }

                for choice in question.choices.all():
                    q_data['choices'].append({
                        'text': choice.text,
                        'order': choice.order
                    })

                template_data['questions'].append(q_data)

            template.template_data = template_data
            template.save()

            messages.success(request, _('Poll saved as template successfully!'))
            return redirect('polls:template_list')
    else:
        form = PollTemplateForm(user=request.user, initial={
            'title': f"{poll.title} - Template",
            'description': poll.description
        })

    return render(request, 'polls/save_as_template.html', {
        'form': form,
        'poll': poll
    })

@login_required
def create_from_template(request, pk):
    """Create a new poll from a template"""
    template = get_object_or_404(PollTemplate, pk=pk)
    
    # Check if user can access this template
    if not template.is_public and template.creator != request.user:
        return HttpResponseForbidden()
    
    if request.method == 'POST':
        form = PollForm(request.POST, user=request.user)
        if form.is_valid():
            with transaction.atomic():
                poll = form.save(commit=False)
                poll.creator = request.user
                poll.save()
                form.save_m2m()  # Save tags
                
                # Create questions and choices from template
                template_data = template.template_data
                for q_data in template_data.get('questions', []):
                    question_type = QuestionType.objects.get(slug=q_data['question_type'])
                    
                    question = Question.objects.create(
                        poll=poll,
                        text=q_data['text'],
                        question_type=question_type,
                        is_required=q_data.get('is_required', True),
                        order=q_data.get('order', 0),
                        min_value=q_data.get('min_value'),
                        max_value=q_data.get('max_value'),
                        step_value=q_data.get('step_value'),
                        settings=q_data.get('settings')
                    )
                    
                    for c_data in q_data.get('choices', []):
                        Choice.objects.create(
                            question=question,
                            text=c_data['text'],
                            order=c_data.get('order', 0)
                        )
                
                # Award points for poll creation
                from gamification.models import award_points
                award_points(request.user, 'poll_creation')
            
            messages.success(request, _('Poll created from template successfully!'))
            return redirect('polls:detail', slug=poll.slug)
    else:
        # Pre-fill form with template data
        template_data = template.template_data
        initial = {
            'title': template_data.get('title', ''),
            'description': template_data.get('description', ''),
            'poll_type': template_data.get('poll_type', 'public'),
            'category': template.category
        }
        form = PollForm(user=request.user, initial=initial)
    
    return render(request, 'polls/create_from_template.html', {
        'form': form,
        'template': template,
        'template_data': template.template_data
    })


class TemplateListView(LoginRequiredMixin, ListView):
    model = PollTemplate
    template_name = 'polls/template_list.html'
    context_object_name = 'templates'
    paginate_by = 12
    
    def get_queryset(self):
        # Show user's templates and public templates
        return PollTemplate.objects.filter(
            Q(creator=self.request.user) | Q(is_public=True)
        ).order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['categories'] = PollCategory.objects.all()
        
        # Filter by category if provided
        category_slug = self.request.GET.get('category', '')
        context['current_category'] = category_slug
        
        return context


@login_required
def export_poll_data(request, slug):
    """Export poll data in various formats"""
    poll = get_object_or_404(Poll, slug=slug)
    
    # Check if user is the creator or a researcher
    if request.user != poll.creator and request.user.user_type != 'researcher':
        return HttpResponseForbidden()
    
    export_format = request.GET.get('format', 'json')
    
    # Prepare data for export
    poll_data = {
        'poll_id': poll.id,
        'title': poll.title,
        'description': poll.description,
        'creator': poll.creator.username,
        'category': poll.category.name if poll.category else None,
        'poll_type': poll.poll_type,
        'status': poll.status,
        'created_at': poll.created_at.isoformat(),
        'questions': []
    }
    
    for question in poll.questions.all():
        q_data = {
            'question_id': question.id,
            'text': question.text,
            'type': question.question_type.slug,
            'is_required': question.is_required,
            'responses': []
        }
        
        for response in question.responses.all():
            r_data = {
                'user_id': response.user.id if poll.poll_type != 'anonymous' else None,
                'response_data': response.response_data,
                'created_at': response.created_at.isoformat()
            }
            q_data['responses'].append(r_data)
        
        poll_data['questions'].append(q_data)
    
    # Generate response based on format
    if export_format == 'json':
        return JsonResponse(poll_data)
    elif export_format == 'csv':
        # Implementation for CSV export
        import csv
        from django.http import HttpResponse
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{poll.slug}_data.csv"'
        
        writer = csv.writer(response)
        writer.writerow(['Question ID', 'Question Text', 'Question Type', 'User ID', 'Response', 'Timestamp'])
        
        for question in poll_data['questions']:
            for response in question['responses']:
                writer.writerow([
                    question['question_id'],
                    question['text'],
                    question['type'],
                    response['user_id'],
                    response['response_data'],
                    response['created_at']
                ])
        
        return response
    else:
        messages.error(request, _('Unsupported export format.'))
        return redirect('polls:detail', slug=slug)


class PollAnalyticsView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    """Advanced analytics for a poll"""
    model = Poll
    template_name = 'polls/poll_analytics.html'
    context_object_name = 'poll'
    
    def test_func(self):
        poll = self.get_object()
        return self.request.user == poll.creator or self.request.user.user_type == 'researcher'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        poll = self.get_object()
        
        # Basic statistics
        total_responses = poll.total_responses
        total_participants = poll.total_participants
        
        context.update({
            'total_responses': total_responses,
            'total_participants': total_participants,
        })
        
        # Response rate over time
        responses = PollResponse.objects.filter(question__poll=poll).order_by('created_at')
        response_dates = responses.values_list('created_at', flat=True)
        
        from collections import Counter
        import datetime
        
        date_counts = Counter([d.date() for d in response_dates])
        date_range = []
        count_range = []
        
        if response_dates.exists():
            start_date = response_dates.first().date()
            end_date = timezone.now().date()
            
            current_date = start_date
            while current_date <= end_date:
                date_range.append(current_date.strftime('%Y-%m-%d'))
                count_range.append(date_counts.get(current_date, 0))
                current_date += datetime.timedelta(days=1)
        
        context['response_timeline'] = {
            'dates': date_range,
            'counts': count_range
        }
        
        # Question-specific analytics
        question_analytics = []
        for question in poll.questions.all():
            analytics = {
                'question': question.text,
                'type': question.question_type.slug,
                'total_responses': question.responses.count(),
                'data': question.response_data
            }
            question_analytics.append(analytics)
        
        context['question_analytics'] = question_analytics
        
        return context


# Category management views
class CategoryListView(ListView):
    model = PollCategory
    template_name = 'polls/category_list.html'
    context_object_name = 'categories'


@login_required
def create_category(request):
    """Create a new poll category (admin only)"""
    if not request.user.is_staff:
        return HttpResponseForbidden()
    
    if request.method == 'POST':
        form = PollCategoryForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, _('Category created successfully!'))
            return redirect('polls:category_list')
    else:
        form = PollCategoryForm()
    
    return render(request, 'polls/category_form.html', {'form': form})


@login_required
def update_category(request, pk):
    """Update a poll category (admin only)"""
    if not request.user.is_staff:
        return HttpResponseForbidden()
    
    category = get_object_or_404(PollCategory, pk=pk)
    
    if request.method == 'POST':
        form = PollCategoryForm(request.POST, instance=category)
        if form.is_valid():
            form.save()
            messages.success(request, _('Category updated successfully!'))
            return redirect('polls:category_list')
    else:
        form = PollCategoryForm(instance=category)
    
    return render(request, 'polls/category_form.html', {'form': form, 'category': category})


@login_required
@require_POST
def delete_category(request, pk):
    """Delete a poll category (admin only)"""
    if not request.user.is_staff:
        return HttpResponseForbidden()
    
    category = get_object_or_404(PollCategory, pk=pk)
    category.delete()
    messages.success(request, _('Category deleted successfully!'))
    return redirect('polls:category_list')


# Question type management views
@login_required
def question_types(request):
    """List and manage question types (admin only)"""
    if not request.user.is_staff:
        return HttpResponseForbidden()
    
    question_types = QuestionType.objects.all()
    
    if request.method == 'POST':
        form = QuestionTypeForm(request.POST)
        if form.is_valid():
            question_type = form.save(commit=False)
            question_type.slug = slugify(question_type.name)
            question_type.save()
            messages.success(request, _('Question type created successfully!'))
            return redirect('polls:question_types')
    else:
        form = QuestionTypeForm()
    
    return render(request, 'polls/question_types.html', {
        'question_types': question_types,
        'form': form
    })


@login_required
@require_POST
def delete_question_type(request, pk):
    """Delete a question type (admin only)"""
    if not request.user.is_staff:
        return HttpResponseForbidden()
    
    question_type = get_object_or_404(QuestionType, pk=pk)
    
    # Check if it's in use
    if question_type.questions.exists():
        messages.error(request, _('Cannot delete question type that is in use.'))
        return redirect('polls:question_types')
    
    question_type.delete()
    messages.success(request, _('Question type deleted successfully!'))
    return redirect('polls:question_types')



@login_required
def add_comment(request, slug):
    """Add a comment to a poll"""
    poll = get_object_or_404(Poll, slug=slug)
    
    if request.method == 'POST':
        form = PollCommentForm(request.POST)
        if form.is_valid():
            comment = form.save(commit=False)
            comment.poll = poll
            comment.user = request.user
            comment.save()
            messages.success(request, _('Your comment has been added.'))
            return redirect('polls:detail', slug=poll.slug)
    else:
        form = PollCommentForm()

    return redirect('polls:detail', slug=poll.slug)  # Redirect to the poll detail on success

class PollDetailWithCommentsView(DetailView):
    model = Poll
    template_name = 'polls/poll_detail.html'
    context_object_name = 'poll'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        poll = self.get_object()

        # Comments for the poll
        context['comments'] = PollComment.objects.filter(poll=poll).order_by('-created_at')
        
        # Include the comment form in context
        context['comment_form'] = PollCommentForm()
        
        return context