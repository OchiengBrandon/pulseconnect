from django.db import models
from django.utils.translation import gettext_lazy as _
from django.conf import settings
from django.utils import timezone
from django.db.models.signals import post_save
from django.dispatch import receiver

class Badge(models.Model):
    """Badges that users can earn"""
    name = models.CharField(max_length=100, verbose_name=_('Name'))
    description = models.TextField(verbose_name=_('Description'))
    icon = models.CharField(max_length=50, verbose_name=_('Icon'))
    
    # Badge requirements
    REQUIREMENT_TYPE_CHOICES = (
        ('polls_created', _('Polls Created')),
        ('polls_participated', _('Polls Participated')),
        ('discussions_created', _('Discussions Created')),
        ('comments_made', _('Comments Made')),
        ('points_earned', _('Points Earned')),
        ('impact_reports', _('Impact Reports')),
        ('volunteer_signups', _('Volunteer Signups')),
    )
    requirement_type = models.CharField(
        max_length=20,
        choices=REQUIREMENT_TYPE_CHOICES,
        verbose_name=_('Requirement Type')
    )
    requirement_count = models.PositiveIntegerField(verbose_name=_('Requirement Count'))
    
    # Badge level
    LEVEL_CHOICES = (
        ('bronze', _('Bronze')),
        ('silver', _('Silver')),
        ('gold', _('Gold')),
        ('platinum', _('Platinum')),
    )
    level = models.CharField(
        max_length=10,
        choices=LEVEL_CHOICES,
        default='bronze',
        verbose_name=_('Level')
    )
    
    # Users who have earned this badge
    users = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        through='BadgeAward',
        related_name='badges',
        verbose_name=_('Users')
    )
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = _('Badge')
        verbose_name_plural = _('Badges')
    
    def __str__(self):
        return f"{self.name} ({self.get_level_display()})"


class BadgeAward(models.Model):
    """Record of when a user earned a badge"""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='badge_awards',
        verbose_name=_('User')
    )
    badge = models.ForeignKey(
        Badge,
        on_delete=models.CASCADE,
        related_name='awards',
        verbose_name=_('Badge')
    )
    awarded_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = _('Badge Award')
        verbose_name_plural = _('Badge Awards')
        unique_together = ('user', 'badge')
    
    def __str__(self):
        return f"{self.user.username} - {self.badge.name}"


class UserPoints(models.Model):
    """Points earned by users"""
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='points',
        verbose_name=_('User')
    )
    total_points = models.PositiveIntegerField(default=0, verbose_name=_('Total Points'))
    
    # Point breakdown
    poll_creation_points = models.PositiveIntegerField(default=0, verbose_name=_('Poll Creation Points'))
    poll_participation_points = models.PositiveIntegerField(default=0, verbose_name=_('Poll Participation Points'))
    discussion_points = models.PositiveIntegerField(default=0, verbose_name=_('Discussion Points'))
    comment_points = models.PositiveIntegerField(default=0, verbose_name=_('Comment Points'))
    sharing_points = models.PositiveIntegerField(default=0, verbose_name=_('Sharing Points'))
    impact_points = models.PositiveIntegerField(default=0, verbose_name=_('Impact Points'))
    volunteer_points = models.PositiveIntegerField(default=0, verbose_name=_('Volunteer Points'))
    
    # Metadata
    last_updated = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = _('User Points')
        verbose_name_plural = _('User Points')
    
    def __str__(self):
        return f"{self.user.username} - {self.total_points} points"


class PointTransaction(models.Model):
    """Record of point transactions"""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='point_transactions',
        verbose_name=_('User')
    )
    
    TRANSACTION_TYPE_CHOICES = (
        ('poll_creation', _('Poll Creation')),
        ('poll_participation', _('Poll Participation')),
        ('discussion_creation', _('Discussion Creation')),
        ('comment', _('Comment')),
        ('sharing', _('Sharing')),
        ('impact_report', _('Impact Report')),
        ('volunteer_signup', _('Volunteer Signup')),
        ('bonus', _('Bonus')),
    )
    transaction_type = models.CharField(
        max_length=20,
        choices=TRANSACTION_TYPE_CHOICES,
        verbose_name=_('Transaction Type')
    )
    
    points = models.PositiveIntegerField(verbose_name=_('Points'))
    description = models.CharField(max_length=255, blank=True, verbose_name=_('Description'))
    
    # Optional reference to related object
    content_type = models.ForeignKey(
        'contenttypes.ContentType',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_('Content Type')
    )
    object_id = models.PositiveIntegerField(null=True, blank=True, verbose_name=_('Object ID'))
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = _('Point Transaction')
        verbose_name_plural = _('Point Transactions')
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.username} - {self.points} points for {self.get_transaction_type_display()}"


class Leaderboard(models.Model):
    """Leaderboard configuration"""
    title = models.CharField(max_length=100, verbose_name=_('Title'))
    description = models.TextField(blank=True, verbose_name=_('Description'))
    
    # Leaderboard type
    LEADERBOARD_TYPE_CHOICES = (
        ('overall', _('Overall Points')),
        ('polls', _('Polls')),
        ('discussions', _('Discussions')),
        ('comments', _('Comments')),
        ('volunteer', _('Volunteer')),
    )
    leaderboard_type = models.CharField(
        max_length=15,
        choices=LEADERBOARD_TYPE_CHOICES,
        default='overall',
        verbose_name=_('Leaderboard Type')
    )
    
    # Time period
    TIME_PERIOD_CHOICES = (
        ('all_time', _('All Time')),
        ('this_month', _('This Month')),
        ('this_week', _('This Week')),
        ('today', _('Today')),
    )
    time_period = models.CharField(
        max_length=10,
        choices=TIME_PERIOD_CHOICES,
        default='all_time',
        verbose_name=_('Time Period')
    )
    
    # Display settings
    max_entries = models.PositiveIntegerField(default=10, verbose_name=_('Maximum Entries'))
    is_active = models.BooleanField(default=True, verbose_name=_('Active'))
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = _('Leaderboard')
        verbose_name_plural = _('Leaderboards')
        unique_together = ('leaderboard_type', 'time_period')
    
    def __str__(self):
        return f"{self.title} ({self.get_time_period_display()})"
    
    def get_leaders(self):
        """Get the leaders for this leaderboard"""
        from django.db.models import Sum, Count
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        # Get time filter
        time_filter = None
        if self.time_period == 'this_month':
            time_filter = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        elif self.time_period == 'this_week':
            # Get the start of the week (Sunday)
            today = timezone.now().date()
            time_filter = timezone.now().replace(
                day=today.day - today.weekday(),
                hour=0, minute=0, second=0, microsecond=0
            )
            if time_filter > timezone.now():
                # If we went into the future, go back 7 days
                time_filter = time_filter - timezone.timedelta(days=7)
        elif self.time_period == 'today':
            time_filter = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Get the appropriate queryset based on leaderboard type
        if self.leaderboard_type == 'overall':
            if time_filter:
                # For time-filtered overall points, we need to sum transactions
                leaders = User.objects.annotate(
                    score=Sum('point_transactions__points', 
                              filter=models.Q(point_transactions__created_at__gte=time_filter))
                ).filter(score__gt=0).order_by('-score')[:self.max_entries]
            else:
                # For all-time, we can use the pre-calculated total
                leaders = User.objects.annotate(
                    score=models.F('points__total_points')
                ).filter(score__gt=0).order_by('-score')[:self.max_entries]
        
        elif self.leaderboard_type == 'polls':
            # Count polls created
            if time_filter:
                leaders = User.objects.annotate(
                    score=Count('created_polls', 
                                filter=models.Q(created_polls__created_at__gte=time_filter))
                ).filter(score__gt=0).order_by('-score')[:self.max_entries]
            else:
                leaders = User.objects.annotate(
                    score=Count('created_polls')
                ).filter(score__gt=0).order_by('-score')[:self.max_entries]
        
        elif self.leaderboard_type == 'discussions':
            # Count discussions created
            if time_filter:
                leaders = User.objects.annotate(
                    score=Count('discussions', 
                                filter=models.Q(discussions__created_at__gte=time_filter))
                ).filter(score__gt=0).order_by('-score')[:self.max_entries]
            else:
                leaders = User.objects.annotate(
                    score=Count('discussions')
                ).filter(score__gt=0).order_by('-score')[:self.max_entries]
        
        elif self.leaderboard_type == 'comments':
            # Count comments made
            if time_filter:
                leaders = User.objects.annotate(
                    score=Count('comments', 
                                filter=models.Q(comments__created_at__gte=time_filter))
                ).filter(score__gt=0).order_by('-score')[:self.max_entries]
            else:
                leaders = User.objects.annotate(
                    score=Count('comments')
                ).filter(score__gt=0).order_by('-score')[:self.max_entries]
        
        elif self.leaderboard_type == 'volunteer':
            # Count volunteer signups
            if time_filter:
                leaders = User.objects.annotate(
                    score=Count('interested_opportunities', 
                                filter=models.Q(interested_opportunities__created_at__gte=time_filter))
                ).filter(score__gt=0).order_by('-score')[:self.max_entries]
            else:
                leaders = User.objects.annotate(
                    score=Count('interested_opportunities')
                ).filter(score__gt=0).order_by('-score')[:self.max_entries]
        
        return leaders


# Create UserPoints for new users
@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_user_points(sender, instance, created, **kwargs):
    if created:
        UserPoints.objects.create(user=instance)


# Award points function
def award_points(user, transaction_type, related_object=None, points=None, description=''):
    """Award points to a user"""
    from django.contrib.contenttypes.models import ContentType
    
    # Get point values from settings
    if points is None:
        if transaction_type == 'poll_creation':
            points = settings.POINTS_FOR_POLL_CREATION
        elif transaction_type == 'poll_participation':
            points = settings.POINTS_FOR_POLL_PARTICIPATION
        elif transaction_type == 'discussion_creation':
            points = 10  # Default value
        elif transaction_type == 'comment':
            points = settings.POINTS_FOR_COMMENT
        elif transaction_type == 'sharing':
            points = settings.POINTS_FOR_SHARING
        elif transaction_type == 'impact_report':
            points = 15  # Default value
        elif transaction_type == 'volunteer_signup':
            points = 8  # Default value
        elif transaction_type == 'bonus':
            points = 5  # Default value, should be overridden
    
    # Create the transaction
    transaction = PointTransaction(
        user=user,
        transaction_type=transaction_type,
        points=points,
        description=description
    )
    
    # Set content object if provided
    if related_object:
        content_type = ContentType.objects.get_for_model(related_object)
        transaction.content_type = content_type
        transaction.object_id = related_object.id
    
    transaction.save()
    
    # Update user points
    try:
        user_points = UserPoints.objects.get(user=user)
    except UserPoints.DoesNotExist:
        user_points = UserPoints.objects.create(user=user)
    
    # Update specific point category
    if transaction_type == 'poll_creation':
        user_points.poll_creation_points += points
    elif transaction_type == 'poll_participation':
        user_points.poll_participation_points += points
    elif transaction_type == 'discussion_creation':
        user_points.discussion_points += points
    elif transaction_type == 'comment':
        user_points.comment_points += points
    elif transaction_type == 'sharing':
        user_points.sharing_points += points
    elif transaction_type == 'impact_report':
        user_points.impact_points += points
    elif transaction_type == 'volunteer_signup':
        user_points.volunteer_points += points
    
    # Update total points
    user_points.total_points += points
    user_points.save()
    
    # Check for badges
    check_for_badges(user)
    
    return transaction


def check_for_badges(user):
    """Check if user has earned any badges"""
    from django.db.models import Count
    
    # Get all badges the user doesn't have yet
    user_badge_ids = user.badges.values_list('id', flat=True)
    available_badges = Badge.objects.exclude(id__in=user_badge_ids)
    
    for badge in available_badges:
        requirement_met = False
        
        if badge.requirement_type == 'polls_created':
            count = user.created_polls.count()
            requirement_met = count >= badge.requirement_count
        
        elif badge.requirement_type == 'polls_participated':
            count = user.poll_responses.values('question__poll').distinct().count()
            requirement_met = count >= badge.requirement_count
        
        elif badge.requirement_type == 'discussions_created':
            count = user.discussions.count()
            requirement_met = count >= badge.requirement_count
        
        elif badge.requirement_type == 'comments_made':
            count = user.comments.count()
            requirement_met = count >= badge.requirement_count
        
        elif badge.requirement_type == 'points_earned':
            try:
                user_points = UserPoints.objects.get(user=user)
                requirement_met = user_points.total_points >= badge.requirement_count
            except UserPoints.DoesNotExist:
                requirement_met = False
        
        elif badge.requirement_type == 'impact_reports':
            count = user.reported_impacts.count()
            requirement_met = count >= badge.requirement_count
        
        elif badge.requirement_type == 'volunteer_signups':
            count = user.interested_opportunities.count()
            requirement_met = count >= badge.requirement_count
        
        if requirement_met:
            # Award the badge
            BadgeAward.objects.create(user=user, badge=badge)