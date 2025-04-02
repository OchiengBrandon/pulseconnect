from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse, reverse_lazy
from django.http import HttpResponseForbidden, JsonResponse, HttpResponse
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views import View
from django.views.generic import (
    ListView, DetailView, CreateView, UpdateView, DeleteView, TemplateView
)
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.db.models import Q
from django.views.decorators.http import require_POST
from django.utils.decorators import method_decorator
from django.db import transaction

from .models import DataSet, AnalysisReport, Visualization, AnalyticsJob
from .forms import (
    DataSetForm, CollaboratorForm, AnalysisReportForm, 
    VisualizationForm, DataImportForm, AnalyticsJobForm
)
from polls.models import Poll, PollResponse
from accounts.models import User

import json
import pandas as pd
import numpy as np
from io import BytesIO

class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'analytics/dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # Recent datasets
        context['datasets'] = DataSet.objects.filter(
            Q(creator=user) | Q(collaborators=user) | Q(is_public=True)
        ).distinct().order_by('-created_at')[:5]
        
        # Recent reports
        context['reports'] = AnalysisReport.objects.filter(
            Q(creator=user) | Q(collaborators=user) | Q(is_public=True)
        ).distinct().order_by('-created_at')[:5]
        
        # Recent visualizations
        context['visualizations'] = Visualization.objects.filter(
            Q(creator=user) | Q(dataset__creator=user) | 
            Q(dataset__collaborators=user) | Q(dataset__is_public=True)
        ).distinct().order_by('-created_at')[:5]
        
        # Recent jobs
        context['jobs'] = AnalyticsJob.objects.filter(creator=user).order_by('-created_at')[:5]
        
        return context


class DataSetListView(LoginRequiredMixin, ListView):
    model = DataSet
    template_name = 'analytics/dataset_list.html'
    context_object_name = 'datasets'
    paginate_by = 10
    
    def get_queryset(self):
        user = self.request.user
        
        # Show datasets the user has access to
        queryset = DataSet.objects.filter(
            Q(creator=user) | Q(collaborators=user) | Q(is_public=True)
        ).distinct()
        
        # Apply filters
        filter_type = self.request.GET.get('filter', '')
        if filter_type == 'mine':
            queryset = queryset.filter(creator=user)
        elif filter_type == 'shared':
            queryset = queryset.filter(collaborators=user)
        elif filter_type == 'public':
            queryset = queryset.filter(is_public=True)
        
        return queryset.order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['filter'] = self.request.GET.get('filter', '')
        return context


@method_decorator(login_required, name='dispatch')
class DataSetCreateView(CreateView):
    model = DataSet
    form_class = DataSetForm
    template_name = 'analytics/dataset_form.html'
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def form_valid(self, form):
        # Set creator
        form.instance.creator = self.request.user
        
        # Process poll data into a dataset
        source_polls = form.cleaned_data['source_polls']
        dataset_data = self._process_poll_data(source_polls)
        form.instance.data = dataset_data
        
        messages.success(self.request, _('Dataset created successfully!'))
        return super().form_valid(form)
    
    def _process_poll_data(self, polls):
        """Process poll data into a structured dataset"""
        dataset = []
        
        for poll in polls:
            poll_data = {
                'poll_id': poll.id,
                'title': poll.title,
                'questions': []
            }
            
            for question in poll.questions.all():
                question_data = {
                    'question_id': question.id,
                    'text': question.text,
                    'type': question.question_type.slug,
                    'responses': []
                }
                
                for response in question.responses.all():
                    response_data = {
                        'user_id': response.user.id if poll.poll_type != 'anonymous' else None,
                        'response': response.response_data,
                        'timestamp': response.created_at.isoformat()
                    }
                    question_data['responses'].append(response_data)
                
                poll_data['questions'].append(question_data)
            
            dataset.append(poll_data)
        
        return dataset
    
    def get_success_url(self):
        return reverse('analytics:dataset_detail', kwargs={'uuid': self.object.uuid})

@method_decorator(login_required, name='dispatch')
class DataSetUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = DataSet
    form_class = DataSetForm
    template_name = 'analytics/dataset_form.html'
    slug_field = 'uuid'
    slug_url_kwarg = 'uuid'
    
    def test_func(self):
        dataset = self.get_object()
        return self.request.user == dataset.creator

    def form_valid(self, form):
        messages.success(self.request, _('Dataset updated successfully!'))
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('analytics:dataset_detail', kwargs={'uuid': self.object.uuid})
    
    
@method_decorator(login_required, name='dispatch')
class DataSetDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = DataSet
    template_name = 'analytics/dataset_confirm_delete.html'
    slug_field = 'uuid'
    slug_url_kwarg = 'uuid'
    
    def test_func(self):
        dataset = self.get_object()
        return self.request.user == dataset.creator

    def get_success_url(self):
        messages.success(self.request, _('Dataset deleted successfully!'))
        return reverse_lazy('analytics:dataset_list')


class DataSetDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    model = DataSet
    template_name = 'analytics/dataset_detail.html'
    context_object_name = 'dataset'
    slug_field = 'uuid'
    slug_url_kwarg = 'uuid'
    
    def test_func(self):
        dataset = self.get_object()
        user = self.request.user
        
        # Check if user has access to this dataset
        return (dataset.creator == user or 
                user in dataset.collaborators.all() or 
                dataset.is_public)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        dataset = self.get_object()
        
        # Add collaborator form
        context['collaborator_form'] = CollaboratorForm()
        
        # Add visualizations for this dataset
        context['visualizations'] = Visualization.objects.filter(dataset=dataset)
        
        # Add reports using this dataset
        context['reports'] = AnalysisReport.objects.filter(datasets=dataset)
        
        # Add sample data preview
        context['data_preview'] = self._generate_data_preview(dataset)
        
        return context
    
    def _generate_data_preview(self, dataset):
        """Generate a preview of the dataset for display"""
        # This is a simplified example - in a real implementation, 
        # you would process the JSON data into a tabular format for display
        data = dataset.data
        
        if not data or not isinstance(data, list) or not data:
            return None
        
        # For simplicity, just return the first poll's first question's first few responses
        if data[0].get('questions') and data[0]['questions']:
            question = data[0]['questions'][0]
            responses = question.get('responses', [])
            return {
                'poll_title': data[0].get('title', ''),
                'question_text': question.get('text', ''),
                'responses': responses[:5]  # First 5 responses
            }
        
        return None


@login_required
def add_dataset_collaborator(request, uuid):
    """Add collaborators to a dataset"""
    dataset = get_object_or_404(DataSet, uuid=uuid)
    
    # Check if user is the creator
    if request.user != dataset.creator:
        return HttpResponseForbidden()
    
    if request.method == 'POST':
        form = CollaboratorForm(request.POST)
        if form.is_valid():
            collaborator_usernames = [u.strip() for u in form.cleaned_data['collaborators'].split(',')]
            
            added_count = 0
            for username in collaborator_usernames:
                try:
                    user = User.objects.get(username=username)
                    if user != request.user and user not in dataset.collaborators.all():
                        dataset.collaborators.add(user)
                        added_count += 1
                except User.DoesNotExist:
                    pass
            
            if added_count:
                messages.success(request, _('Added {} collaborators successfully!').format(added_count))
            else:
                messages.info(request, _('No new collaborators were added.'))
    
    return redirect('analytics:dataset_detail', uuid=uuid)


@login_required
@require_POST
def remove_dataset_collaborator(request, uuid, user_id):
    """Remove a collaborator from a dataset"""
    dataset = get_object_or_404(DataSet, uuid=uuid)
    
    # Check if user is the creator
    if request.user != dataset.creator:
        return HttpResponseForbidden()
    
    try:
        user = User.objects.get(id=user_id)
        dataset.collaborators.remove(user)
        messages.success(request, _('Collaborator removed successfully!'))
    except User.DoesNotExist:
        messages.error(request, _('User not found.'))
    
    return redirect('analytics:dataset_detail', uuid=uuid)


@login_required
def export_dataset(request, uuid):
    """Export dataset in various formats"""
    dataset = get_object_or_404(DataSet, uuid=uuid)
    
    # Check if user has access to this dataset
    if not (dataset.creator == request.user or 
            request.user in dataset.collaborators.all() or 
            dataset.is_public):
        return HttpResponseForbidden()
    
    export_format = request.GET.get('format', 'json')
    
    # Convert dataset to appropriate format
    if export_format == 'json':
        response = HttpResponse(json.dumps(dataset.data, indent=2), content_type='application/json')
        response['Content-Disposition'] = f'attachment; filename="{dataset.title}.json"'
    elif export_format == 'csv':
        # Convert JSON to DataFrame
        df = self._dataset_to_dataframe(dataset)
        
        # Convert DataFrame to CSV
        csv_data = BytesIO()
        df.to_csv(csv_data, index=False)
        csv_data.seek(0)
        
        response = HttpResponse(csv_data.read(), content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{dataset.title}.csv"'
    elif export_format == 'excel':
        # Convert JSON to DataFrame
        df = self._dataset_to_dataframe(dataset)
        
        # Convert DataFrame to Excel
        excel_data = BytesIO()
        df.to_excel(excel_data, index=False)
        excel_data.seek(0)
        
        response = HttpResponse(excel_data.read(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = f'attachment; filename="{dataset.title}.xlsx"'
    else:
        messages.error(request, _('Unsupported export format.'))
        return redirect('analytics:dataset_detail', uuid=uuid)
    
    return response


def _dataset_to_dataframe(dataset):
    """Convert dataset JSON to pandas DataFrame"""
    # This is a simplified implementation
    # In a real application, you would need to handle different question types
    # and create a properly structured DataFrame
    
    rows = []
    
    for poll in dataset.data:
        poll_id = poll.get('poll_id')
        poll_title = poll.get('title')
        
        for question in poll.get('questions', []):
            question_id = question.get('question_id')
            question_text = question.get('text')
            question_type = question.get('type')
            
            for response in question.get('responses', []):
                row = {
                    'poll_id': poll_id,
                    'poll_title': poll_title,
                    'question_id': question_id,
                    'question_text': question_text,
                    'question_type': question_type,
                    'user_id': response.get('user_id'),
                    'response': response.get('response'),
                    'timestamp': response.get('timestamp')
                }
                rows.append(row)
    
    return pd.DataFrame(rows)


@method_decorator(login_required, name='dispatch')
class AnalysisReportListView(LoginRequiredMixin, ListView):
    model = AnalysisReport
    template_name = 'analytics/report_list.html'
    context_object_name = 'reports'
    paginate_by = 10

    def get_queryset(self):
        user = self.request.user
        
        # Base queryset showing reports the user has access to
        queryset = AnalysisReport.objects.filter(
            Q(creator=user) | Q(collaborators=user) | Q(is_public=True)
        ).distinct()
        
        # Apply filters based on the query parameter
        filter_type = self.request.GET.get('filter', '')
        if filter_type == 'mine':
            queryset = queryset.filter(creator=user)
        elif filter_type == 'shared':
            queryset = queryset.filter(collaborators=user)
        elif filter_type == 'public':
            queryset = queryset.filter(is_public=True)
        
        return queryset.order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['filter'] = self.request.GET.get('filter', '')
        context['my_reports_count'] = AnalysisReport.objects.filter(creator=self.request.user).count()
        context['shared_reports_count'] = AnalysisReport.objects.filter(collaborators=self.request.user).count()
        context['public_reports_count'] = AnalysisReport.objects.filter(is_public=True).count()
        return context

@login_required
def duplicate_report(request, uuid):
    """Duplicate an existing analysis report."""
    original_report = get_object_or_404(AnalysisReport, uuid=uuid)

    # Check if the user has permission to duplicate the report
    if request.user != original_report.creator:
        return HttpResponseForbidden()

    # Create a copy of the original report
    new_report = AnalysisReport.objects.create(
        title=f"Copy of {original_report.title}",
        description=original_report.description,
        creator=request.user,
        content=original_report.content,  # Adjust as necessary
        is_public=original_report.is_public,
        # Copy other relevant fields as necessary
    )

    messages.success(request, _('Report duplicated successfully!'))
    return redirect('analytics:report_detail', uuid=new_report.uuid)


@login_required
def delete_report(request, uuid):
    """Delete an existing analysis report."""
    report = get_object_or_404(AnalysisReport, uuid=uuid)

    # Check if the user has permission to delete the report
    if request.user != report.creator:
        return HttpResponseForbidden()

    report.delete()
    messages.success(request, _('Report deleted successfully!'))
    return redirect('analytics:report_list')

@method_decorator(login_required, name='dispatch')
class AnalysisReportCreateView(CreateView):
    model = AnalysisReport
    form_class = AnalysisReportForm
    template_name = 'analytics/report_form.html'
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def form_valid(self, form):
        # Set creator
        form.instance.creator = self.request.user
        
        # Initialize empty report content
        form.instance.content = {
            'sections': [],
            'visualizations': [],
            'findings': [],
            'recommendations': []
        }
        
        messages.success(self.request, _('Report created successfully! Now you can add content to it.'))
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse('analytics:report_edit', kwargs={'uuid': self.object.uuid})


class AnalysisReportDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    model = AnalysisReport
    template_name = 'analytics/report_detail.html'
    context_object_name = 'report'
    slug_field = 'uuid'
    slug_url_kwarg = 'uuid'
    
    def test_func(self):
        report = self.get_object()
        user = self.request.user
        
        # Check if user has access to this report
        return (report.creator == user or 
                user in report.collaborators.all() or 
                report.is_public)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        report = self.get_object()
        
        # Add collaborator form
        context['collaborator_form'] = CollaboratorForm()
        
        # Add datasets used in this report
        context['datasets'] = report.datasets.all()
        
        return context


@login_required
def export_report(request, uuid):
    """Export an analysis report in various formats."""
    report = get_object_or_404(AnalysisReport, uuid=uuid)

    # Check if user has access to this report
    if not (report.creator == request.user or 
            request.user in report.collaborators.all() or 
            report.is_public):
        return HttpResponseForbidden()

    export_format = request.GET.get('format', 'json')

    if export_format == 'json':
        response = HttpResponse(json.dumps(report.content, indent=2), content_type='application/json')
        response['Content-Disposition'] = f'attachment; filename="{report.title}.json"'
    elif export_format == 'csv':
        # Convert report content to CSV and return as response
        pass  # Implement CSV export logic
    elif export_format == 'excel':
        # Convert report content to Excel and return as response
        pass  # Implement Excel export logic
    else:
        messages.error(request, _('Unsupported export format.'))
        return redirect('analytics:report_detail', uuid=uuid)

    return response

@login_required
@require_POST
def toggle_visibility(request, uuid):
    """Toggle the visibility of an analysis report."""
    report = get_object_or_404(AnalysisReport, uuid=uuid)

    # Check if the user has permission to toggle visibility
    if request.user != report.creator:
        return JsonResponse({'error': 'Forbidden'}, status=403)

    # Update the visibility
    report.is_public = not report.is_public
    report.save()

    return JsonResponse({'is_public': report.is_public})

from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import AnalysisReport

@login_required
def report_preview(request, uuid):
    """Preview an analysis report."""
    report = get_object_or_404(AnalysisReport, uuid=uuid)

    # Check if the user has access to view the report
    if not (report.creator == request.user or 
            request.user in report.collaborators.all() or 
            report.is_public):
        return HttpResponseForbidden()

    # Render the preview template with the report content
    return render(request, 'analytics/report_preview.html', {'report': report})

@login_required
def edit_report(request, uuid):
    """Edit report content"""
    report = get_object_or_404(AnalysisReport, uuid=uuid)
    
    # Check if user has edit access
    if not (report.creator == request.user or request.user in report.collaborators.all()):
        return HttpResponseForbidden()
    
    if request.method == 'POST':
        # Save report content
        content = json.loads(request.POST.get('content', '{}'))
        report.content = content
        report.save()
        
        messages.success(request, _('Report updated successfully!'))
        return redirect('analytics:report_detail', uuid=uuid)
    
    # Get visualizations for datasets in this report
    visualizations = Visualization.objects.filter(dataset__in=report.datasets.all())
    
    return render(request, 'analytics/report_edit.html', {
        'report': report,
        'visualizations': visualizations
    })


@login_required
def add_report_collaborator(request, uuid):
    """Add collaborators to a report"""
    report = get_object_or_404(AnalysisReport, uuid=uuid)
    
    # Check if user is the creator
    if request.user != report.creator:
        return HttpResponseForbidden()
    
    if request.method == 'POST':
        form = CollaboratorForm(request.POST)
        if form.is_valid():
            collaborator_usernames = [u.strip() for u in form.cleaned_data['collaborators'].split(',')]
            
            added_count = 0
            for username in collaborator_usernames:
                try:
                    user = User.objects.get(username=username)
                    if user != request.user and user not in report.collaborators.all():
                        report.collaborators.add(user)
                        added_count += 1
                except User.DoesNotExist:
                    pass
            
            if added_count:
                messages.success(request, _('Added {} collaborators successfully!').format(added_count))
            else:
                messages.info(request, _('No new collaborators were added.'))
    
    return redirect('analytics:report_detail', uuid=uuid)


@login_required
@require_POST
def remove_report_collaborator(request, uuid, user_id):
    """Remove a collaborator from a report"""
    report = get_object_or_404(AnalysisReport, uuid=uuid)
    
    # Check if user is the creator
    if request.user != report.creator:
        return HttpResponseForbidden()
    
    try:
        user = User.objects.get(id=user_id)
        report.collaborators.remove(user)
        messages.success(request, _('Collaborator removed successfully!'))
    except User.DoesNotExist:
        messages.error(request, _('User not found.'))
    
    return redirect('analytics:report_detail', uuid=uuid)


class VisualizationListView(LoginRequiredMixin, ListView):
    model = Visualization
    template_name = 'analytics/visualization_list.html'
    context_object_name = 'visualizations'
    paginate_by = 12
    
    def get_queryset(self):
        user = self.request.user
        
        # Show visualizations the user has access to
        queryset = Visualization.objects.filter(
            Q(creator=user) | 
            Q(dataset__creator=user) | 
            Q(dataset__collaborators=user) | 
            Q(dataset__is_public=True)
        ).distinct()
        
        # Filter by visualization type
        viz_type = self.request.GET.get('type', '')
        if viz_type:
            queryset = queryset.filter(visualization_type=viz_type)
        
        # Filter by dataset
        dataset_uuid = self.request.GET.get('dataset', '')
        if dataset_uuid:
            try:
                dataset = DataSet.objects.get(uuid=dataset_uuid)
                queryset = queryset.filter(dataset=dataset)
            except DataSet.DoesNotExist:
                pass
        
        return queryset.order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Add filters to context
        context['visualization_types'] = dict(Visualization.VISUALIZATION_TYPES)
        context['current_type'] = self.request.GET.get('type', '')
        context['current_dataset'] = self.request.GET.get('dataset', '')
        
        # Add datasets for filter dropdown
        user = self.request.user
        context['datasets'] = DataSet.objects.filter(
            Q(creator=user) | Q(collaborators=user) | Q(is_public=True)
        ).distinct()
        
        return context


@method_decorator(login_required, name='dispatch')
class VisualizationCreateView(CreateView):
    model = Visualization
    form_class = VisualizationForm  
    template_name = 'analytics/visualization_form.html'
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        
        # Pre-fill dataset if provided in URL
        dataset_uuid = self.request.GET.get('dataset', '')
        if dataset_uuid:
            try:
                dataset = DataSet.objects.get(uuid=dataset_uuid)
                if self.request.method == 'GET':
                    kwargs['initial'] = kwargs.get('initial', {})
                    kwargs['initial']['dataset'] = dataset
            except DataSet.DoesNotExist:
                pass
        
        return kwargs
    
    def form_valid(self, form):
        # Set creator
        form.instance.creator = self.request.user
        
        # Generate visualization data
        dataset = form.cleaned_data['dataset']
        viz_type = form.cleaned_data['visualization_type']
        config = form.cleaned_data['config']
        
        try:
            # Generate visualization data based on type
            viz_data = self._generate_visualization_data(dataset, viz_type, config)
            form.instance.data = viz_data
            
            messages.success(self.request, _('Visualization created successfully!'))
            return super().form_valid(form)
        except Exception as e:
            form.add_error(None, str(e))
            return self.form_invalid(form)
    
    def _generate_visualization_data(self, dataset, viz_type, config):
        """Generate visualization data based on dataset and config"""
        # Load the dataset data
        data = dataset.get_data()
        
        if not data:
            raise ValueError("Dataset contains no data")
        
        # Process data based on visualization type
        if viz_type == 'bar':
            return self._generate_bar_chart_data(data, config)
        elif viz_type == 'pie':
            return self._generate_pie_chart_data(data, config)
        elif viz_type == 'line':
            return self._generate_line_chart_data(data, config)
        elif viz_type == 'scatter':
            return self._generate_scatter_plot_data(data, config)
        elif viz_type == 'wordcloud':
            return self._generate_wordcloud_data(data, config)
        else:
            # Default to returning sample of raw data
            return {'raw_data': data[:10]}  # First 10 items
    
    def _generate_bar_chart_data(self, data, config):
        """Generate data for a bar chart."""
        try:
            # Extract configuration options
            category_field = config.get('category_field')
            value_field = config.get('value_field')
            
            if not category_field or not value_field:
                raise ValueError("Both category_field and value_field must be specified for bar charts")
            
            # Extract labels and values from the dataset
            categories = {}
            
            # Aggregate data by category
            for item in data:
                category = str(item.get(category_field, 'Unknown'))
                value = float(item.get(value_field, 0))
                
                if category in categories:
                    categories[category] += value
                else:
                    categories[category] = value
            
            # Convert to sorted lists for the chart
            sorted_categories = sorted(categories.items(), 
                                      key=lambda x: x[1], 
                                      reverse=config.get('sort_desc', True))
            
            # Limit to top N categories if specified
            limit = config.get('limit', len(sorted_categories))
            top_categories = sorted_categories[:limit]
            
            labels = [item[0] for item in top_categories]
            values = [item[1] for item in top_categories]
            
            # Generate colors based on the number of categories
            colors = self._generate_colors(len(labels))
            
            return {
                'labels': labels,
                'datasets': [{
                    'label': config.get('chart_title', 'Data by ' + category_field),
                    'data': values,
                    'backgroundColor': [color + '0.2)' for color in colors],
                    'borderColor': [color + '1)' for color in colors],
                    'borderWidth': 1
                }]
            }
        except Exception as e:
            raise ValueError(f"Error generating bar chart data: {str(e)}")
    
    def _generate_pie_chart_data(self, data, config):
        """Generate data for a pie chart."""
        try:
            # Extract configuration options
            category_field = config.get('category_field')
            value_field = config.get('value_field')
            
            if not category_field or not value_field:
                raise ValueError("Both category_field and value_field must be specified for pie charts")
            
            # Extract labels and values from the dataset
            categories = {}
            
            # Aggregate data by category
            for item in data:
                category = str(item.get(category_field, 'Unknown'))
                value = float(item.get(value_field, 0))
                
                if category in categories:
                    categories[category] += value
                else:
                    categories[category] = value
            
            # Convert to sorted lists for the chart
            sorted_categories = sorted(categories.items(), 
                                      key=lambda x: x[1], 
                                      reverse=config.get('sort_desc', True))
            
            # Limit to top N categories if specified
            limit = config.get('limit', len(sorted_categories))
            top_categories = sorted_categories[:limit]
            
            labels = [item[0] for item in top_categories]
            values = [item[1] for item in top_categories]
            
            # Generate colors based on the number of categories
            colors = self._generate_colors(len(labels))
            
            return {
                'labels': labels,
                'datasets': [{
                    'data': values,
                    'backgroundColor': [color + '0.7)' for color in colors],
                    'borderColor': [color + '1)' for color in colors],
                    'borderWidth': 1
                }]
            }
        except Exception as e:
            raise ValueError(f"Error generating pie chart data: {str(e)}")
    
    def _generate_line_chart_data(self, data, config):
        """Generate data for a line chart."""
        try:
            # Extract configuration options
            time_field = config.get('time_field')
            value_field = config.get('value_field')
            series_field = config.get('series_field')
            
            if not time_field or not value_field:
                raise ValueError("Both time_field and value_field must be specified for line charts")
            
            # Sort data by time field
            sorted_data = sorted(data, key=lambda x: x.get(time_field, ''))
            
            if series_field:
                # Create multiple series
                series = {}
                times = set()
                
                for item in sorted_data:
                    time_value = str(item.get(time_field, ''))
                    series_value = str(item.get(series_field, 'Unknown'))
                    value = float(item.get(value_field, 0))
                    
                    times.add(time_value)
                    
                    if series_value not in series:
                        series[series_value] = {}
                    
                    if time_value in series[series_value]:
                        series[series_value][time_value] += value
                    else:
                        series[series_value][time_value] = value
                
                # Sort times
                sorted_times = sorted(list(times))
                
                # Generate datasets
                datasets = []
                colors = self._generate_colors(len(series))
                
                for i, (series_name, values) in enumerate(series.items()):
                    # Ensure all time periods have values (fill gaps with 0)
                    series_data = [values.get(time, 0) for time in sorted_times]
                    
                    datasets.append({
                        'label': series_name,
                        'data': series_data,
                        'fill': False,
                        'borderColor': colors[i] + '1)',
                        'backgroundColor': colors[i] + '0.2)',
                        'tension': 0.1
                    })
                
                return {
                    'labels': sorted_times,
                    'datasets': datasets
                }
            else:
                # Single series
                times = []
                values = []
                
                for item in sorted_data:
                    times.append(str(item.get(time_field, '')))
                    values.append(float(item.get(value_field, 0)))
                
                return {
                    'labels': times,
                    'datasets': [{
                        'label': config.get('chart_title', 'Trend Data'),
                        'data': values,
                        'fill': config.get('fill', False),
                        'borderColor': 'rgb(75, 192, 192)',
                        'backgroundColor': 'rgba(75, 192, 192, 0.2)',
                        'tension': 0.1
                    }]
                }
        except Exception as e:
            raise ValueError(f"Error generating line chart data: {str(e)}")
    
    def _generate_scatter_plot_data(self, data, config):
        """Generate data for a scatter plot."""
        try:
            # Extract configuration options
            x_field = config.get('x_field')
            y_field = config.get('y_field')
            series_field = config.get('series_field')
            
            if not x_field or not y_field:
                raise ValueError("Both x_field and y_field must be specified for scatter plots")
            
            if series_field:
                # Create multiple series
                series = {}
                
                for item in data:
                    x_value = float(item.get(x_field, 0))
                    y_value = float(item.get(y_field, 0))
                    series_value = str(item.get(series_field, 'Unknown'))
                    
                    if series_value not in series:
                        series[series_value] = []
                    
                    series[series_value].append({'x': x_value, 'y': y_value})
                
                # Generate datasets
                datasets = []
                colors = self._generate_colors(len(series))
                
                for i, (series_name, points) in enumerate(series.items()):
                    datasets.append({
                        'label': series_name,
                        'data': points,
                        'backgroundColor': colors[i] + '0.7)'
                    })
                
                return {'datasets': datasets}
            else:
                # Single series
                points = []
                
                for item in data:
                    points.append({
                        'x': float(item.get(x_field, 0)),
                        'y': float(item.get(y_field, 0))
                    })
                
                return {
                    'datasets': [{
                        'label': config.get('chart_title', 'Scatter Data'),
                        'data': points,
                        'backgroundColor': 'rgb(255, 99, 132)'
                    }]
                }
        except Exception as e:
            raise ValueError(f"Error generating scatter plot data: {str(e)}")
    
    def _generate_wordcloud_data(self, data, config):
        """Generate data for a word cloud."""
        try:
            # Extract configuration
            text_field = config.get('text_field')
            weight_field = config.get('weight_field')
            
            if not text_field:
                raise ValueError("text_field must be specified for wordclouds")
            
            # Process text data
            word_counts = {}
            
            for item in data:
                text = str(item.get(text_field, '')).lower()
                
                # If a weight field is provided, use it for word weighting
                if weight_field:
                    weight = float(item.get(weight_field, 1))
                else:
                    weight = 1
                
                # Simple text normalization
                words = ''.join(c if c.isalnum() or c.isspace() else ' ' for c in text).split()
                
                # Remove stopwords if configured
                stopwords = config.get('stopwords', [])
                filtered_words = [w for w in words if w.lower() not in stopwords]
                
                # Count words
                for word in filtered_words:
                    if len(word) > 2:  # Skip very short words
                        if word in word_counts:
                            word_counts[word] += weight
                        else:
                            word_counts[word] = weight
            
            # Sort and limit words
            limit = config.get('limit', 100)
            sorted_words = sorted(word_counts.items(), key=lambda x: x[1], reverse=True)[:limit]
            
            words = [{'text': word, 'value': int(count)} for word, count in sorted_words]
            
            return {'words': words}
        except Exception as e:
            raise ValueError(f"Error generating wordcloud data: {str(e)}")
    
    def _generate_colors(self, count):
        """Generate a list of colors for charts."""
        # Predefined colors for consistency
        base_colors = [
            'rgba(255, 99, 132, ',   # Red
            'rgba(54, 162, 235, ',   # Blue
            'rgba(255, 206, 86, ',   # Yellow
            'rgba(75, 192, 192, ',   # Green
            'rgba(153, 102, 255, ',  # Purple
            'rgba(255, 159, 64, ',   # Orange
            'rgba(199, 199, 199, ',  # Gray
            'rgba(83, 102, 255, ',   # Indigo
            'rgba(255, 99, 255, ',   # Pink
            'rgba(0, 168, 133, '     # Teal
        ]
        
        # If we need more colors than predefined, generate them
        colors = []
        for i in range(count):
            if i < len(base_colors):
                colors.append(base_colors[i])
            else:
                # Generate random colors for additional items
                r = (i * 23) % 256
                g = (i * 47) % 256
                b = (i * 91) % 256
                colors.append(f'rgba({r}, {g}, {b}, ')
        
        return colors
    
    def get_success_url(self):
        return reverse('analytics:visualization_detail', kwargs={'pk': self.object.pk})


# FETCH DATASET FIELDS BY UUID
class DatasetFieldsView(View):
    """View to return fields of a dataset based on its UUID."""
    
    def get(self, request, uuid):
        # Get the dataset by UUID
        dataset = get_object_or_404(DataSet, uuid=uuid)
        
        # Extract fields from dataset data
        fields = []
        if hasattr(dataset, 'data') and dataset.data:
            if isinstance(dataset.data, list) and dataset.data:
                first_record = dataset.data[0]  # Get the first record to infer fields
                fields = [{'name': key, 'type': type(value).__name__} for key, value in first_record.items()]
            elif isinstance(dataset.data, dict):
                # If data is a dict, use its keys as fields
                fields = [{'name': key, 'type': type(value).__name__} for key, value in dataset.data.items()]
        
        # Return fields as JSON response
        return JsonResponse({'fields': fields})

# Additional view to get UUID by ID if needed (for compatibility)
class DatasetUUIDView(View):
    """View to return UUID of a dataset based on its ID."""
    
    def get(self, request, pk):
        try:
            dataset = get_object_or_404(DataSet, pk=pk)
            return JsonResponse({'uuid': str(dataset.uuid)})
        except DataSet.DoesNotExist:
            return JsonResponse({'error': 'Dataset not found'}, status=404)


class VisualizationDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    model = Visualization
    template_name = 'analytics/visualization_detail.html'
    context_object_name = 'visualization'
    
    def test_func(self):
        visualization = self.get_object()
        user = self.request.user
        dataset = visualization.dataset
        
        # Check if user has access to the dataset
        return (dataset.creator == user or 
                user in dataset.collaborators.all() or 
                dataset.is_public)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        visualization = self.get_object()
        
        # Add dataset to context
        context['dataset'] = visualization.dataset
        
        return context


@login_required
def data_import(request):
    """Import external data"""
    if request.method == 'POST':
        form = DataImportForm(request.POST, request.FILES)
        if form.is_valid():
            # Create a background job for data import
            job = AnalyticsJob.objects.create(
                job_type='import',
                status='pending',
                creator=request.user,
                parameters={
                    'title': form.cleaned_data['title'],
                    'description': form.cleaned_data['description'],
                    'file_format': form.cleaned_data['file_format'],
                    'is_public': form.cleaned_data['is_public']
                }
            )
            
            # Save the uploaded file
            file = request.FILES['file']
            file_path = f'uploads/imports/{job.id}_{file.name}'
            
            with open(file_path, 'wb+') as destination:
                for chunk in file.chunks():
                    destination.write(chunk)
            
            # Update job parameters with file path
            job.parameters['file_path'] = file_path
            job.save()
            
            # In a real application, you would now trigger a Celery task to process this job
            # For simplicity, we'll process it synchronously here
            try:
                process_import_job(job)
                messages.success(request, _('Data imported successfully!'))
                
                # Redirect to the created dataset
                if job.result and 'dataset_uuid' in job.result:
                    return redirect('analytics:dataset_detail', uuid=job.result['dataset_uuid'])
            except Exception as e:
                job.status = 'failed'
                job.error_message = str(e)
                job.save()
                messages.error(request, _('Error importing data: {}').format(str(e)))
    else:
        form = DataImportForm()
    
    return render(request, 'analytics/data_import.html', {'form': form})


def process_import_job(job):
    """Process a data import job"""
    job.status = 'processing'
    job.started_at = timezone.now()
    job.save()
    
    try:
        params = job.parameters
        file_path = params.get('file_path')
        file_format = params.get('file_format')
        
        # Read the file based on format
        if file_format == 'csv':
            df = pd.read_csv(file_path)
        elif file_format == 'excel':
            df = pd.read_excel(file_path)
        elif file_format == 'json':
            with open(file_path, 'r') as f:
                data = json.load(f)
            # If it's not tabular, convert to DataFrame for consistency
            if isinstance(data, list) and all(isinstance(item, dict) for item in data):
                df = pd.DataFrame(data)
            else:
                # Create a dataset directly from the JSON
                dataset = DataSet.objects.create(
                    title=params.get('title'),
                    description=params.get('description'),
                    creator=job.creator,
                    is_public=params.get('is_public', False),
                    data=data
                )
                
                job.status = 'completed'
                job.completed_at = timezone.now()
                job.result = {'dataset_uuid': str(dataset.uuid)}
                job.dataset = dataset
                job.save()
                return
        else:
            raise ValueError(f"Unsupported file format: {file_format}")
        
        # Convert DataFrame to structured data
        data = df.to_dict(orient='records')
        
        # Create dataset
        dataset = DataSet.objects.create(
            title=params.get('title'),
            description=params.get('description'),
            creator=job.creator,
            is_public=params.get('is_public', False),
            data=data
        )
        
        job.status = 'completed'
        job.completed_at = timezone.now()
        job.result = {'dataset_uuid': str(dataset.uuid)}
        job.dataset = dataset
        job.save()
    
    except Exception as e:
        job.status = 'failed'
        job.error_message = str(e)
        job.completed_at = timezone.now()
        job.save()
        raise


class AnalyticsJobListView(LoginRequiredMixin, ListView):
    model = AnalyticsJob
    template_name = 'analytics/job_list.html'
    context_object_name = 'jobs'
    paginate_by = 20
    
    def get_queryset(self):
        return AnalyticsJob.objects.filter(creator=self.request.user).order_by('-created_at')


@login_required
def job_detail(request, pk):
    """View details of an analytics job"""
    job = get_object_or_404(AnalyticsJob, pk=pk, creator=request.user)
    return render(request, 'analytics/job_detail.html', {'job': job})