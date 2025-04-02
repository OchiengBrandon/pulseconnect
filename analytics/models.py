from django.db import models
from django.utils.translation import gettext_lazy as _
from django.conf import settings
from django.urls import reverse
import uuid

class DataSet(models.Model):
    """Dataset created by researchers from poll data"""
    title = models.CharField(max_length=255, verbose_name=_('Title'))
    description = models.TextField(verbose_name=_('Description'))
    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='datasets',
        verbose_name=_('Creator')
    )
    
    # UUID for secure sharing
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    
    # Access control
    is_public = models.BooleanField(default=False, verbose_name=_('Public'))
    collaborators = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='shared_datasets',
        blank=True,
        verbose_name=_('Collaborators')
    )
    
    # Data source tracking
    source_polls = models.ManyToManyField(
        'polls.Poll',
        related_name='datasets',
        verbose_name=_('Source Polls')
    )
    
    # Dataset content
    data = models.JSONField(verbose_name=_('Dataset'))
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = _('Data Set')
        verbose_name_plural = _('Data Sets')
        ordering = ['-created_at']
    
    def __str__(self):
        return self.title
    
    def get_absolute_url(self):
        return reverse('analytics:dataset_detail', kwargs={'uuid': self.uuid})
    
    def get_data(self):
        """Return the dataset content as a dictionary."""
        return self.data


class AnalysisReport(models.Model):
    """Analysis report created from dataset(s)"""
    title = models.CharField(max_length=255, verbose_name=_('Title'))
    description = models.TextField(verbose_name=_('Description'))
    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='analysis_reports',
        verbose_name=_('Creator')
    )
    
    # UUID for secure sharing
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    
    # Access control
    is_public = models.BooleanField(default=False, verbose_name=_('Public'))
    collaborators = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='shared_reports',
        blank=True,
        verbose_name=_('Collaborators')
    )
    
    # Related datasets
    datasets = models.ManyToManyField(
        DataSet,
        related_name='reports',
        verbose_name=_('Datasets')
    )
    
    # Report content
    content = models.JSONField(verbose_name=_('Report Content'))
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = _('Analysis Report')
        verbose_name_plural = _('Analysis Reports')
        ordering = ['-created_at']
    
    def __str__(self):
        return self.title
    
    def get_absolute_url(self):
        return reverse('analytics:report_detail', kwargs={'uuid': self.uuid})


class Visualization(models.Model):
    """Visualizations created from datasets"""
    VISUALIZATION_TYPES = (
        ('bar', _('Bar Chart')),
        ('line', _('Line Chart')),
        ('pie', _('Pie Chart')),
        ('scatter', _('Scatter Plot')),
        ('heatmap', _('Heat Map')),
        ('table', _('Table')),
        ('wordcloud', _('Word Cloud')),
        ('custom', _('Custom')),
    )
    
    title = models.CharField(max_length=255, verbose_name=_('Title'))
    description = models.TextField(blank=True, verbose_name=_('Description'))
    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='visualizations',
        verbose_name=_('Creator')
    )
    
    # Visualization type and data
    visualization_type = models.CharField(
        max_length=20,
        choices=VISUALIZATION_TYPES,
        verbose_name=_('Visualization Type')
    )
    dataset = models.ForeignKey(
        DataSet,
        on_delete=models.CASCADE,
        related_name='visualizations',
        verbose_name=_('Dataset')
    )
    
    # Configuration for the visualization
    config = models.JSONField(verbose_name=_('Configuration'))
    
    # Generated visualization data
    data = models.JSONField(verbose_name=_('Visualization Data'))
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = _('Visualization')
        verbose_name_plural = _('Visualizations')
        ordering = ['-created_at']
    
    def __str__(self):
        return self.title


class AnalyticsJob(models.Model):
    """Background analytics jobs"""
    JOB_TYPES = (
        ('export', _('Data Export')),
        ('import', _('Data Import')),
        ('analysis', _('Data Analysis')),
        ('visualization', _('Visualization Generation')),
    )
    
    JOB_STATUS = (
        ('pending', _('Pending')),
        ('processing', _('Processing')),
        ('completed', _('Completed')),
        ('failed', _('Failed')),
    )
    
    job_type = models.CharField(
        max_length=20,
        choices=JOB_TYPES,
        verbose_name=_('Job Type')
    )
    status = models.CharField(
        max_length=20,
        choices=JOB_STATUS,
        default='pending',
        verbose_name=_('Status')
    )
    
    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='analytics_jobs',
        verbose_name=_('Creator')
    )
    
    # Job parameters and results
    parameters = models.JSONField(verbose_name=_('Job Parameters'))
    result = models.JSONField(null=True, blank=True, verbose_name=_('Job Result'))
    error_message = models.TextField(blank=True, verbose_name=_('Error Message'))
    
    # Related objects
    dataset = models.ForeignKey(
        DataSet,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='jobs',
        verbose_name=_('Dataset')
    )
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        verbose_name = _('Analytics Job')
        verbose_name_plural = _('Analytics Jobs')
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.get_job_type_display()} - {self.get_status_display()}"