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
from django.db.models import Sum, Count, Q
from django.views.decorators.http import require_POST
from django.utils.decorators import method_decorator
from django.core.paginator import Paginator
from django.db.models.functions import TruncDate

from .models import Badge, BadgeAward, UserPoints, PointTransaction, Leaderboard
from accounts.models import User

class RewardsHomeView(LoginRequiredMixin, TemplateView):
    template_name = 'gamification/rewards_home.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get available badges
        context['badges'] = Badge.objects.all()
        
        # Get active leaderboards
        context['leaderboards'] = Leaderboard.objects.filter(is_active=True)
        
        # Get user points and statistics
        try:
            user_points = UserPoints.objects.get(user=self.request.user)
            context['user_points'] = user_points
            
            # Calculate point statistics
            now = timezone.now()
            week_ago = now - timezone.timedelta(days=7)
            month_ago = now - timezone.timedelta(days=30)
            
            # Get point history for charts
            point_history = PointTransaction.objects.filter(
                user=self.request.user,
                created_at__gte=month_ago
            ).annotate(
                date=TruncDate('created_at')
            ).values('date').annotate(
                total=Sum('points')
            ).order_by('date')
            
            context['point_history'] = list(point_history)
            
            # Get recent achievements
            context['recent_achievements'] = BadgeAward.objects.filter(
                user=self.request.user
            ).select_related('badge').order_by('-awarded_at')[:5]
            
            # Get progress towards next badges
            context['badge_progress'] = self.get_badge_progress()
            
        except UserPoints.DoesNotExist:
            context['user_points'] = None
        
        return context
    
    def get_badge_progress(self):
        """Calculate progress towards next available badges"""
        progress = []
        user_badge_ids = self.request.user.badges.values_list('id', flat=True)
        available_badges = Badge.objects.exclude(id__in=user_badge_ids)
        
        for badge in available_badges:
            current_count = 0
            
            if badge.requirement_type == 'polls_created':
                current_count = self.request.user.created_polls.count()
            elif badge.requirement_type == 'polls_participated':
                current_count = self.request.user.poll_responses.values('poll').distinct().count()
            elif badge.requirement_type == 'points_earned':
                try:
                    current_count = UserPoints.objects.get(user=self.request.user).total_points
                except UserPoints.DoesNotExist:
                    current_count = 0
            
            if current_count > 0:
                progress.append({
                    'badge': badge,
                    'current': current_count,
                    'required': badge.requirement_count,
                    'percentage': min(100, int((current_count / badge.requirement_count) * 100))
                })
        
        return sorted(progress, key=lambda x: x['percentage'], reverse=True)[:3]


class LeaderboardView(ListView):
    model = Leaderboard
    template_name = 'gamification/leaderboard.html'
    context_object_name = 'leaderboards'
    
    def get_queryset(self):
        return Leaderboard.objects.filter(is_active=True)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get selected time period from query params
        time_period = self.request.GET.get('period', 'all_time')
        context['selected_period'] = time_period
        
        # Get leaders for each leaderboard
        for leaderboard in context['leaderboards']:
            leaderboard.leaders = leaderboard.get_leaders(time_period=time_period)
        
        if self.request.user.is_authenticated:
            # Get user's ranks and points
            user_stats = {}
            for leaderboard in context['leaderboards']:
                leaders = list(leaderboard.get_leaders(time_period=time_period))
                try:
                    user_rank = next(i for i, leader in enumerate(leaders) if leader.id == self.request.user.id) + 1
                    user_score = next(leader.score for leader in leaders if leader.id == self.request.user.id)
                except StopIteration:
                    user_rank = None
                    user_score = 0
                
                user_stats[leaderboard.id] = {
                    'rank': user_rank,
                    'score': user_score,
                    'total_participants': len(leaders)
                }
            
            context['user_stats'] = user_stats
        
        return context


class BadgeListView(ListView):
    model = Badge
    template_name = 'gamification/badge_list.html'
    context_object_name = 'badges'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Group badges by level
        badges_by_level = {}
        for level, level_display in Badge.LEVEL_CHOICES:
            badges_by_level[level] = {
                'display': level_display,
                'badges': Badge.objects.filter(level=level)
            }
        
        context['badges_by_level'] = badges_by_level
        
        if self.request.user.is_authenticated:
            # Get user's earned badges
            user_badge_ids = self.request.user.badge_awards.values_list('badge_id', flat=True)
            context['user_badge_ids'] = set(user_badge_ids)
            
            # Calculate progress for unearned badges
            badge_progress = {}
            for badge in Badge.objects.exclude(id__in=user_badge_ids):
                progress = self.calculate_badge_progress(badge)
                if progress > 0:
                    badge_progress[badge.id] = progress
            
            context['badge_progress'] = badge_progress
        
        return context
    
    def calculate_badge_progress(self, badge):
        """Calculate progress percentage towards a badge"""
        current_count = 0
        
        if badge.requirement_type == 'polls_created':
            current_count = self.request.user.created_polls.count()
        elif badge.requirement_type == 'polls_participated':
            current_count = self.request.user.poll_responses.values('poll').distinct().count()
        elif badge.requirement_type == 'points_earned':
            try:
                current_count = UserPoints.objects.get(user=self.request.user).total_points
            except UserPoints.DoesNotExist:
                current_count = 0
        
        return min(100, int((current_count / badge.requirement_count) * 100))


class BadgeDetailView(DetailView):
    model = Badge
    template_name = 'gamification/badge_detail.html'
    context_object_name = 'badge'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get recent earners
        context['recent_earners'] = BadgeAward.objects.filter(
            badge=self.object
        ).select_related('user').order_by('-awarded_at')[:10]
        
        if self.request.user.is_authenticated:
            # Check if user has earned this badge
            try:
                context['user_award'] = BadgeAward.objects.get(
                    badge=self.object,
                    user=self.request.user
                )
            except BadgeAward.DoesNotExist:
                context['user_award'] = None
                # Calculate progress if not earned
                context['progress'] = self.calculate_badge_progress(self.object)
        
        return context
    
    def calculate_badge_progress(self, badge):
        """Calculate detailed progress information for a badge"""
        current_count = 0
        
        if badge.requirement_type == 'polls_created':
            current_count = self.request.user.created_polls.count()
        elif badge.requirement_type == 'polls_participated':
            current_count = self.request.user.poll_responses.values('poll').distinct().count()
        elif badge.requirement_type == 'points_earned':
            try:
                current_count = UserPoints.objects.get(user=self.request.user).total_points
            except UserPoints.DoesNotExist:
                current_count = 0
        
        return {
            'current': current_count,
            'required': badge.requirement_count,
            'percentage': min(100, int((current_count / badge.requirement_count) * 100)),
            'remaining': max(0, badge.requirement_count - current_count)
        }


@method_decorator(login_required, name='dispatch')
class UserPointsHistoryView(ListView):
    template_name = 'gamification/points_history.html'
    context_object_name = 'transactions'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = PointTransaction.objects.filter(user=self.request.user)
        
        # Filter by transaction type if specified
        transaction_type = self.request.GET.get('type')
        if transaction_type:
            queryset = queryset.filter(transaction_type=transaction_type)
        
        # Filter by date range if specified
        start_date = self.request.GET.get('start_date')
        end_date = self.request.GET.get('end_date')
        if start_date and end_date:
            try:
                start_date = timezone.datetime.strptime(start_date, '%Y-%m-%d')
                end_date = timezone.datetime.strptime(end_date, '%Y-%m-%d')
                queryset = queryset.filter(created_at__date__range=[start_date, end_date])
            except ValueError:
                pass
        
        return queryset.order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get point statistics
        total_points = UserPoints.objects.get(user=self.request.user)
        context['total_points'] = total_points
        
        # Get point breakdown by type
        point_breakdown = PointTransaction.objects.filter(
            user=self.request.user
        ).values('transaction_type').annotate(
            total=Sum('points')
        ).order_by('-total')
        context['point_breakdown'] = point_breakdown
        
        return context


# API endpoints for AJAX requests
@login_required
@require_POST
def refresh_points(request):
    """Refresh user points data"""
    try:
        user_points = UserPoints.objects.get(user=request.user)
        data = {
            'total_points': user_points.total_points,
            'poll_points': user_points.poll_creation_points + user_points.poll_participation_points,
            'discussion_points': user_points.discussion_points,
            'comment_points': user_points.comment_points,
            'impact_points': user_points.impact_points,
            'volunteer_points': user_points.volunteer_points
        }
        return JsonResponse(data)
    except UserPoints.DoesNotExist:
        return JsonResponse({'error': 'User points not found'}, status=404)

@login_required
def get_point_history(request):
    """Get point history for charts"""
    days = int(request.GET.get('days', 30))
    start_date = timezone.now() - timezone.timedelta(days=days)
    
    point_history = PointTransaction.objects.filter(
        user=request.user,
        created_at__gte=start_date
    ).annotate(
        date=TruncDate('created_at')
    ).values('date').annotate(
        total=Sum('points')
    ).order_by('date')
    
    data = list(point_history)
    return JsonResponse(data, safe=False)


class UserBadgesView(LoginRequiredMixin, ListView):
    model = BadgeAward
    template_name = 'gamification/user_badges.html'
    context_object_name = 'badges'

    def get_queryset(self):
        # Get badges awarded to the logged-in user
        return BadgeAward.objects.filter(user=self.request.user).select_related('badge').order_by('-awarded_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['user'] = self.request.user  # Add user info to context
        return context


@login_required
def get_user_points(request):
    """Retrieve user points for the API."""
    user_points = get_object_or_404(UserPoints, user=request.user)

    data = {
        'total_points': user_points.total_points,
        'poll_creation_points': user_points.poll_creation_points,
        'poll_participation_points': user_points.poll_participation_points,
        'discussion_points': user_points.discussion_points,
        'comment_points': user_points.comment_points,
        'impact_points': user_points.impact_points,
        'volunteer_points': user_points.volunteer_points,
    }
    
    return JsonResponse(data)