# Generated by Django 5.1.6 on 2025-04-06 23:26

import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Visualization',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=255, verbose_name='Title')),
                ('description', models.TextField(blank=True, verbose_name='Description')),
                ('visualization_type', models.CharField(choices=[('bar', 'Bar Chart'), ('line', 'Line Chart'), ('pie', 'Pie Chart'), ('scatter', 'Scatter Plot'), ('heatmap', 'Heat Map'), ('table', 'Table'), ('wordcloud', 'Word Cloud'), ('custom', 'Custom')], max_length=20, verbose_name='Visualization Type')),
                ('config', models.JSONField(verbose_name='Configuration')),
                ('data', models.JSONField(verbose_name='Visualization Data')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Visualization',
                'verbose_name_plural': 'Visualizations',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='AnalysisReport',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=255, verbose_name='Title')),
                ('description', models.TextField(verbose_name='Description')),
                ('uuid', models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ('is_public', models.BooleanField(default=False, verbose_name='Public')),
                ('content', models.JSONField(verbose_name='Report Content')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('collaborators', models.ManyToManyField(blank=True, related_name='shared_reports', to=settings.AUTH_USER_MODEL, verbose_name='Collaborators')),
                ('creator', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='analysis_reports', to=settings.AUTH_USER_MODEL, verbose_name='Creator')),
            ],
            options={
                'verbose_name': 'Analysis Report',
                'verbose_name_plural': 'Analysis Reports',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='AnalyticsJob',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('job_type', models.CharField(choices=[('export', 'Data Export'), ('import', 'Data Import'), ('analysis', 'Data Analysis'), ('visualization', 'Visualization Generation')], max_length=20, verbose_name='Job Type')),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('processing', 'Processing'), ('completed', 'Completed'), ('failed', 'Failed')], default='pending', max_length=20, verbose_name='Status')),
                ('parameters', models.JSONField(verbose_name='Job Parameters')),
                ('result', models.JSONField(blank=True, null=True, verbose_name='Job Result')),
                ('error_message', models.TextField(blank=True, verbose_name='Error Message')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('started_at', models.DateTimeField(blank=True, null=True)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('creator', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='analytics_jobs', to=settings.AUTH_USER_MODEL, verbose_name='Creator')),
            ],
            options={
                'verbose_name': 'Analytics Job',
                'verbose_name_plural': 'Analytics Jobs',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='DataSet',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=255, verbose_name='Title')),
                ('description', models.TextField(verbose_name='Description')),
                ('uuid', models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ('is_public', models.BooleanField(default=False, verbose_name='Public')),
                ('data', models.JSONField(verbose_name='Dataset')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('collaborators', models.ManyToManyField(blank=True, related_name='shared_datasets', to=settings.AUTH_USER_MODEL, verbose_name='Collaborators')),
                ('creator', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='datasets', to=settings.AUTH_USER_MODEL, verbose_name='Creator')),
            ],
            options={
                'verbose_name': 'Data Set',
                'verbose_name_plural': 'Data Sets',
                'ordering': ['-created_at'],
            },
        ),
    ]
