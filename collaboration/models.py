from django.db import models
from django.utils.translation import gettext_lazy as _
from django.conf import settings
from django.urls import reverse
import uuid

class ResearchProject(models.Model):
    """Collaborative research projects for researchers"""
    title = models.CharField(max_length=255, verbose_name=_('Title'))
    description = models.TextField(verbose_name=_('Description'))
    
    # Project owner
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='owned_projects',
        verbose_name=_('Owner')
    )
    
    # Team members
    members = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        through='ProjectMembership',
        related_name='projects',
        verbose_name=_('Members')
    )
    
    # Project status
    STATUS_CHOICES = (
        ('planning', _('Planning')),
        ('active', _('Active')),
        ('completed', _('Completed')),
        ('archived', _('Archived')),
    )
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default='planning',
        verbose_name=_('Status')
    )
    
    # Visibility
    is_public = models.BooleanField(default=False, verbose_name=_('Public'))
    
    # Dates
    start_date = models.DateField(null=True, blank=True, verbose_name=_('Start Date'))
    end_date = models.DateField(null=True, blank=True, verbose_name=_('End Date'))
    
    # Related datasets
    datasets = models.ManyToManyField(
        'analytics.DataSet',
        blank=True,
        related_name='projects',
        verbose_name=_('Datasets')
    )
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = _('Research Project')
        verbose_name_plural = _('Research Projects')
        ordering = ['-created_at']
    
    def __str__(self):
        return self.title
    
    def get_absolute_url(self):
        return reverse('collaboration:project_detail', kwargs={'pk': self.pk})


class ProjectMembership(models.Model):
    """Membership and roles in research projects"""
    project = models.ForeignKey(
        ResearchProject,
        on_delete=models.CASCADE,
        related_name='memberships',
        verbose_name=_('Project')
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='project_memberships',
        verbose_name=_('User')
    )
    
    # Role in the project
    ROLE_CHOICES = (
        ('researcher', _('Researcher')),
        ('analyst', _('Data Analyst')),
        ('coordinator', _('Coordinator')),
        ('advisor', _('Advisor')),
        ('observer', _('Observer')),
    )
    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default='researcher',
        verbose_name=_('Role')
    )
    
    # Permissions
    can_edit = models.BooleanField(default=False, verbose_name=_('Can Edit'))
    can_invite = models.BooleanField(default=False, verbose_name=_('Can Invite'))
    
    # Dates
    joined_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = _('Project Membership')
        verbose_name_plural = _('Project Memberships')
        unique_together = ('project', 'user')
    
    def __str__(self):
        return f"{self.user.username} - {self.project.title} ({self.get_role_display()})"


class ProjectTask(models.Model):
    """Tasks within research projects"""
    title = models.CharField(max_length=255, verbose_name=_('Title'))
    description = models.TextField(blank=True, verbose_name=_('Description'))
    
    # Related project
    project = models.ForeignKey(
        ResearchProject,
        on_delete=models.CASCADE,
        related_name='tasks',
        verbose_name=_('Project')
    )
    
    # Task assignment
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_tasks',
        verbose_name=_('Assigned To')
    )
    
    # Task status
    STATUS_CHOICES = (
        ('todo', _('To Do')),
        ('in_progress', _('In Progress')),
        ('review', _('Under Review')),
        ('completed', _('Completed')),
    )
    status = models.CharField(
        max_length=15,
        choices=STATUS_CHOICES,
        default='todo',
        verbose_name=_('Status')
    )
    
    # Priority
    PRIORITY_CHOICES = (
        ('low', _('Low')),
        ('medium', _('Medium')),
        ('high', _('High')),
        ('urgent', _('Urgent')),
    )
    priority = models.CharField(
        max_length=10,
        choices=PRIORITY_CHOICES,
        default='medium',
        verbose_name=_('Priority')
    )
    
    # Dates
    due_date = models.DateField(null=True, blank=True, verbose_name=_('Due Date'))
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name=_('Completed At'))
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = _('Project Task')
        verbose_name_plural = _('Project Tasks')
        ordering = ['due_date', '-priority']
    
    def __str__(self):
        return f"{self.title} ({self.project.title})"


class ProjectDocument(models.Model):
    """Documents shared within research projects"""
    title = models.CharField(max_length=255, verbose_name=_('Title'))
    description = models.TextField(blank=True, verbose_name=_('Description'))
    
    # Related project
    project = models.ForeignKey(
        ResearchProject,
        on_delete=models.CASCADE,
        related_name='documents',
        verbose_name=_('Project')
    )
    
    # Document content
    content = models.TextField(blank=True, verbose_name=_('Content'))
    
    # File upload (optional)
    file = models.FileField(
        upload_to='project_documents/',
        null=True,
        blank=True,
        verbose_name=_('File')
    )
    
    # Creator
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_documents',
        verbose_name=_('Created By')
    )
    
    # Document version
    version = models.PositiveIntegerField(default=1, verbose_name=_('Version'))
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = _('Project Document')
        verbose_name_plural = _('Project Documents')
        ordering = ['-updated_at']
    
    def __str__(self):
        return f"{self.title} v{self.version} ({self.project.title})"


class ProjectInvitation(models.Model):
    """Invitations to join research projects"""
    project = models.ForeignKey(
        ResearchProject,
        on_delete=models.CASCADE,
        related_name='invitations',
        verbose_name=_('Project')
    )
    
    # Can be sent to existing users or by email
    email = models.EmailField(verbose_name=_('Email'))
    invited_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='project_invitations',
        verbose_name=_('Invited User')
    )
    
    # Invitation details
    role = models.CharField(
        max_length=20,
        choices=ProjectMembership.ROLE_CHOICES,
        default='researcher',
        verbose_name=_('Role')
    )
    
    # Invitation token
    token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    
    # Who sent the invitation
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='sent_invitations',
        verbose_name=_('Invited By')
    )
    
    # Status
    STATUS_CHOICES = (
        ('pending', _('Pending')),
        ('accepted', _('Accepted')),
        ('declined', _('Declined')),
        ('expired', _('Expired')),
    )
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default='pending',
        verbose_name=_('Status')
    )
    
    # Dates
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(verbose_name=_('Expires At'))
    responded_at = models.DateTimeField(null=True, blank=True, verbose_name=_('Responded At'))
    
    class Meta:
        verbose_name = _('Project Invitation')
        verbose_name_plural = _('Project Invitations')
        unique_together = ('project', 'email')
    
    def __str__(self):
        return f"Invitation to {self.project.title} for {self.email}"
    
    @property
    def is_expired(self):
        from django.utils import timezone
        return self.expires_at < timezone.now()