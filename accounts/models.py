from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _
from django.urls import reverse
from django.conf import settings

class User(AbstractUser):
    USER_TYPE_CHOICES = (
        ('student', _('Student')),
        ('institution', _('Institution')),
        ('researcher', _('Researcher')),
        ('community', _('Community Member')),
    )
    
    user_type = models.CharField(
        max_length=15,
        choices=USER_TYPE_CHOICES,
        default='student',
        verbose_name=_('User Type')
    )
    
    bio = models.TextField(blank=True, verbose_name=_('Biography'))
    profile_picture = models.ImageField(
        upload_to='profile_pictures/', 
        blank=True, 
        null=True,
        verbose_name=_('Profile Picture')
    )
    institution = models.CharField(
        max_length=100, 
        blank=True, 
        verbose_name=_('Institution')
    )
    field_of_study = models.CharField(
        max_length=100, 
        blank=True, 
        verbose_name=_('Field of Study')
    )
    location = models.CharField(
        max_length=100, 
        blank=True, 
        verbose_name=_('Location')
    )
    website = models.URLField(blank=True, verbose_name=_('Website'))
    social_linkedin = models.URLField(blank=True, verbose_name=_('LinkedIn'))
    social_twitter = models.URLField(blank=True, verbose_name=_('Twitter'))
    social_github = models.URLField(blank=True, verbose_name=_('GitHub'))
    
    # Notification preferences
    email_notifications = models.BooleanField(default=True, verbose_name=_('Email Notifications'))
    poll_notifications = models.BooleanField(default=True, verbose_name=_('Poll Notifications'))
    comment_notifications = models.BooleanField(default=True, verbose_name=_('Comment Notifications'))
    
    # Privacy settings
    public_profile = models.BooleanField(default=True, verbose_name=_('Public Profile'))
    show_email = models.BooleanField(default=False, verbose_name=_('Show Email'))
    
    # Accessibility preferences
    high_contrast = models.BooleanField(default=False, verbose_name=_('High Contrast Mode'))
    large_text = models.BooleanField(default=False, verbose_name=_('Large Text'))
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = _('User')
        verbose_name_plural = _('Users')
        
    def __str__(self):
        return self.username
    
    def get_absolute_url(self):
        return reverse('accounts:profile', kwargs={'username': self.username})
    
    def get_full_name(self):
        return f"{self.first_name} {self.last_name}" if self.first_name or self.last_name else self.username
    
    @property
    def is_student(self):
        return self.user_type == 'student'
    
    @property
    def is_institution(self):
        return self.user_type == 'institution'
    
    @property
    def is_researcher(self):
        return self.user_type == 'researcher'
    
    @property
    def total_points(self):
        from gamification.models import UserPoints
        points = UserPoints.objects.filter(user=self).first()
        return points.total_points if points else 0
    
    # Follow functionality
    def follow(self, user_to_follow):
        Follow.objects.get_or_create(follower=self, followee=user_to_follow)

    def unfollow(self, user_to_unfollow):
        Follow.objects.filter(follower=self, followee=user_to_unfollow).delete()

    def is_following(self, user):
        return Follow.objects.filter(follower=self, followee=user).exists()

    def followers_count(self):
        return self.followers.count()

    def following_count(self):
        return self.following.count()


class Follow(models.Model):
    follower = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name='following',
        on_delete=models.CASCADE
    )
    followee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name='followers',
        on_delete=models.CASCADE
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('follower', 'followee')  # Ensure one follow relationship per user pair

    def __str__(self):
        return f"{self.follower} follows {self.followee}"


class UserVerification(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='verification'
    )
    is_verified = models.BooleanField(default=False, verbose_name=_('Is Verified'))
    verification_token = models.CharField(
        max_length=64, 
        blank=True, 
        null=True,
        verbose_name=_('Verification Token')
    )
    token_expiry = models.DateTimeField(
        blank=True, 
        null=True,
        verbose_name=_('Token Expiry')
    )
    
    class Meta:
        verbose_name = _('User Verification')
        verbose_name_plural = _('User Verifications')
    
    def __str__(self):
        return f"{self.user.username} - {'Verified' if self.is_verified else 'Not Verified'}"


class InstitutionProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='institution_profile'
    )
    institution_name = models.CharField(max_length=255, verbose_name=_('Institution Name'))
    institution_type = models.CharField(
        max_length=50,
        choices=(
            ('university', _('University')),
            ('college', _('College')),
            ('high_school', _('High School')),
            ('research', _('Research Institute')),
            ('government', _('Government Agency')),
            ('nonprofit', _('Non-profit Organization')),
            ('other', _('Other')),
        ),
        verbose_name=_('Institution Type')
    )
    address = models.TextField(blank=True, verbose_name=_('Address'))
    phone = models.CharField(max_length=20, blank=True, verbose_name=_('Phone'))
    established_year = models.PositiveIntegerField(
        blank=True, 
        null=True,
        verbose_name=_('Established Year')
    )
    description = models.TextField(blank=True, verbose_name=_('Description'))
    logo = models.ImageField(
        upload_to='institution_logos/', 
        blank=True, 
        null=True,
        verbose_name=_('Logo')
    )
    is_verified = models.BooleanField(default=False, verbose_name=_('Is Verified'))
    
    class Meta:
        verbose_name = _('Institution Profile')
        verbose_name_plural = _('Institution Profiles')
    
    def __str__(self):
        return self.institution_name