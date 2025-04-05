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
        df = dataset_to_dataframe(dataset)  # Ensure this function is defined
        
        # Convert DataFrame to CSV
        csv_data = BytesIO()
        df.to_csv(csv_data, index=False)
        csv_data.seek(0)
        
        response = HttpResponse(csv_data.read(), content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{dataset.title}.csv"'
    
    elif export_format == 'excel':
        # Convert JSON to DataFrame
        df = dataset_to_dataframe(dataset)  # Ensure this function is defined
        
        # Convert DataFrame to Excel
        excel_data = BytesIO()
        df.to_excel(excel_data, index=False)
        excel_data.seek(0)
        
        response = HttpResponse(excel_data.read(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = f'attachment; filename="{dataset.title}.xlsx"'
    
    elif export_format == 'pdf':
        # Generate a detailed PDF report
        pdf_data = BytesIO()
        create_detailed_pdf_report(dataset, pdf_data)
        pdf_data.seek(0)
        
        response = HttpResponse(pdf_data.read(), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{dataset.title}_detailed_report.pdf"'
    
    else:
        messages.error(request, _('Unsupported export format.'))
        return redirect('analytics:dataset_detail', uuid=uuid)
    
    return response


def create_detailed_pdf_report(dataset, output_stream):
    """
    Create a comprehensive analytics PDF report with advanced visualizations and insights
    
    Args:
        dataset: Dataset object containing poll data
        output_stream: BytesIO or file-like object to write PDF to
    """
    from reportlab.lib.pagesizes import letter
    from reportlab.lib import colors
    from reportlab.lib.units import inch
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak, ListFlowable, ListItem
    from reportlab.graphics.shapes import Drawing, Line, String
    from reportlab.graphics.charts.barcharts import VerticalBarChart, HorizontalBarChart
    from reportlab.graphics.charts.piecharts import Pie
    from reportlab.graphics.charts.linecharts import LineChart
    from reportlab.graphics.charts.legends import Legend
    from reportlab.lib.colors import HexColor
    import matplotlib.pyplot as plt
    import numpy as np
    from datetime import datetime
    import pandas as pd
    from io import BytesIO
    import re
    from collections import Counter
    from textwrap import wrap
    
    # Create custom color palette for a professional look
    brand_colors = {
        'primary': HexColor('#1F77B4'),  # Blue
        'secondary': HexColor('#FF7F0E'),  # Orange
        'tertiary': HexColor('#2CA02C'),  # Green
        'quaternary': HexColor('#D62728'),  # Red
        'quinary': HexColor('#9467BD'),  # Purple
        'background': HexColor('#F5F5F5'),  # Light gray
        'text': HexColor('#333333'),  # Dark gray
        'highlight': HexColor('#FFD700')  # Gold
    }
    
    # Convert dataset to DataFrame for easier analysis
    df = dataset_to_dataframe(dataset)
    
    # Create the PDF document with custom margins
    doc = SimpleDocTemplate(
        output_stream, 
        pagesize=letter,
        leftMargin=0.5*inch,
        rightMargin=0.5*inch,
        topMargin=0.75*inch,
        bottomMargin=0.75*inch
    )
    
    # Set up styles
    styles = getSampleStyleSheet()
    
    # Create custom styles for a more professional look
    styles.add(ParagraphStyle(
        name='ReportTitle',
        parent=styles['Title'],
        fontSize=24,
        spaceAfter=12,
        textColor=brand_colors['primary'],
        alignment=1  # Center alignment
    ))
    
    styles.add(ParagraphStyle(
        name='SectionHeading',
        parent=styles['Heading1'],
        fontSize=16,
        spaceAfter=10,
        textColor=brand_colors['primary'],
        borderWidth=1,
        borderColor=brand_colors['primary'],
        borderPadding=5,
        borderRadius=5
    ))
    
    styles.add(ParagraphStyle(
        name='SubsectionHeading',
        parent=styles['Heading2'],
        fontSize=14,
        spaceAfter=8,
        textColor=brand_colors['secondary']
    ))
    
    styles.add(ParagraphStyle(
        name='QuestionHeading',
        parent=styles['Heading3'],
        fontSize=12,
        spaceAfter=6,
        textColor=brand_colors['tertiary']
    ))
    
    styles.add(ParagraphStyle(
        name='InsightText',
        parent=styles['Normal'],
        fontSize=10,
        spaceAfter=6,
        backColor=brand_colors['background'],
        borderWidth=1,
        borderColor=brand_colors['background'],
        borderPadding=5,
        borderRadius=5
    ))
    
    styles.add(ParagraphStyle(
        name='NormalBold',
        parent=styles['Normal'],
        fontName='Helvetica-Bold'
    ))
    
    # Start building the document content
    content = []
    
    # Create a cover page
    content.append(Paragraph(f"Analytics Report", styles['ReportTitle']))
    content.append(Spacer(1, 30))
    content.append(Paragraph(f"<b>{dataset.title}</b>", styles['SectionHeading']))
    content.append(Spacer(1, 40))
    content.append(Paragraph(f"Generated on: {datetime.now().strftime('%B %d, %Y %H:%M')}", styles['Normal']))
    content.append(Paragraph(f"Total Respondents: {df['user_id'].nunique()}", styles['Normal']))
    
    # Add dataset metadata if available
    if hasattr(dataset, 'description') and dataset.description:
        content.append(Spacer(1, 20))
        content.append(Paragraph("Description:", styles['NormalBold']))
        content.append(Paragraph(dataset.description, styles['Normal']))
    
    if hasattr(dataset, 'date_created') and dataset.date_created:
        content.append(Spacer(1, 10))
        content.append(Paragraph(f"Dataset Created: {dataset.date_created.strftime('%B %d, %Y')}", styles['Normal']))
    
    content.append(PageBreak())
    
    # Add Table of Contents
    content.append(Paragraph("Table of Contents", styles['SectionHeading']))
    content.append(Spacer(1, 10))
    
    toc_data = [["Section", "Page"]]
    toc_data.append(["Executive Summary", "3"])
    toc_data.append(["Methodology", "4"])
    page_counter = 5  # Starting page after fixed sections
    
    # Add poll titles to TOC
    for poll in dataset.data:
        poll_title = poll.get('poll_title', 'Untitled Poll')
        toc_data.append([f"Poll: {poll_title}", str(page_counter)])
        page_counter += len(poll.get('questions', [])) + 1  # Estimate one page per question plus poll intro
    
    toc_table = Table(toc_data, colWidths=[4.5*inch, 1*inch])
    toc_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), brand_colors['primary']),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, brand_colors['background']])
    ]))
    content.append(toc_table)
    content.append(PageBreak())
    
    # Executive Summary
    content.append(Paragraph("Executive Summary", styles['SectionHeading']))
    content.append(Spacer(1, 10))
    
    # Calculate key overall metrics
    total_responses = df['user_id'].nunique()
    total_questions = len(df['question_id'].unique())
    completion_rate = calculate_completion_rate(df)
    avg_time_spent = calculate_average_time_spent(df) if 'timestamp' in df.columns else "N/A"
    
    summary_text = f"""
    This report provides a comprehensive analysis of the "{dataset.title}" dataset, comprising {total_responses} 
    respondents across {total_questions} questions. The overall completion rate was {completion_rate:.1f}%, 
    with participants spending an average of {avg_time_spent} minutes on the poll.
    
    Key findings from the analysis include:
    """
    content.append(Paragraph(summary_text, styles['Normal']))
    
    # Generate key insights from the dataset
    insights = generate_key_insights(df, dataset.data)
    insight_items = []
    for insight in insights:
        insight_items.append(ListItem(Paragraph(insight, styles['Normal'])))
    content.append(ListFlowable(insight_items, bulletType='bullet'))
    
    content.append(Spacer(1, 20))
    content.append(Paragraph("The following pages provide detailed question-by-question analysis with visualizations and trend identification.", styles['Normal']))
    content.append(PageBreak())
    
    # Methodology Section
    content.append(Paragraph("Methodology", styles['SectionHeading']))
    content.append(Spacer(1, 10))
    
    methodology_text = f"""
    <b>Data Collection:</b> This dataset contains poll responses collected through our platform.
    
    <b>Analysis Approach:</b> The analysis employs descriptive statistics, trend analysis, and comparative evaluation
    to identify patterns and insights within the response data.
    
    <b>Data Processing:</b> Responses were processed to remove duplicates and handle missing values. 
    Text responses were analyzed for sentiment and common themes where applicable.
    
    <b>Visualization Methods:</b> The report uses various visualization techniques including pie charts, 
    bar graphs, and distribution plots to represent the data effectively.
    """
    content.append(Paragraph(methodology_text, styles['Normal']))
    content.append(PageBreak())
    
    # Process each poll
    for poll_index, poll in enumerate(dataset.data):
        poll_id = poll.get('poll_id')
        poll_title = poll.get('poll_title', 'Untitled Poll')
        
        # Add poll section header
        content.append(Paragraph(f"Poll: {poll_title}", styles['SectionHeading']))
        
        # Filter data for this poll
        poll_df = df[df['poll_id'] == poll_id]
        
        # Add poll overview statistics
        poll_responses = poll_df['user_id'].nunique()
        poll_completion_rate = (poll_df['question_id'].nunique() / len(poll.get('questions', []))) * 100 if poll.get('questions') else 0
        
        overview_text = f"""
        <b>Total Responses:</b> {poll_responses}
        <b>Completion Rate:</b> {poll_completion_rate:.1f}%
        """
        content.append(Paragraph(overview_text, styles['Normal']))
        
        # Add poll-specific insights
        poll_insights = generate_poll_insights(poll_df, poll)
        if poll_insights:
            content.append(Spacer(1, 10))
            content.append(Paragraph("Key Insights:", styles['NormalBold']))
            poll_insight_items = []
            for insight in poll_insights:
                poll_insight_items.append(ListItem(Paragraph(insight, styles['InsightText'])))
            content.append(ListFlowable(poll_insight_items, bulletType='bullet'))
        
        content.append(Spacer(1, 15))
        
        # Process each question in this poll
        for question_index, question in enumerate(poll.get('questions', [])):
            question_id = question.get('question_id')
            question_text = question.get('text', 'Untitled Question')
            question_type = question.get('type', 'unknown')
            
            # Filter DataFrame for this specific question
            q_df = df[(df['poll_id'] == poll_id) & (df['question_id'] == question_id)]
            
            # Skip if no responses
            if q_df.empty:
                continue
            
            # Add question header with numbering
            content.append(Paragraph(f"Q{question_index+1}: {question_text}", styles['SubsectionHeading']))
            content.append(Paragraph(f"<i>Question Type: {question_type.replace('_', ' ').title()}</i>", styles['Normal']))
            content.append(Spacer(1, 5))
            
            # Generate question-specific analysis based on question type
            if question_type in ['single_choice', 'multiple_choice', 'true_false']:
                analyze_choice_question(content, q_df, question, styles, brand_colors)
            
            elif question_type in ['rating_scale', 'likert_scale']:
                analyze_scale_question(content, q_df, question, styles, brand_colors)
            
            elif question_type in ['open_ended', 'short_answer', 'essay']:
                analyze_text_question(content, q_df, question, styles, brand_colors)
            
            else:
                content.append(Paragraph(f"Analysis not available for question type: {question_type}", styles['Normal']))
            
            # Add space after each question's analysis
            content.append(Spacer(1, 20))
            
            # Only add page break if not the last question
            if question_index < len(poll.get('questions', [])) - 1:
                content.append(PageBreak())
        
        # Add page break after each poll (if not the last poll)
        if poll_index < len(dataset.data) - 1:
            content.append(PageBreak())
    
    # Build the PDF document
    try:
        doc.build(content)
    except Exception as e:
        # If PDF creation fails, create a simple error report
        error_doc = SimpleDocTemplate(output_stream, pagesize=letter)
        error_content = [
            Paragraph(f"Error generating detailed report: {str(e)}", styles['Heading1']),
            Paragraph("Please contact support with this error message.", styles['Normal'])
        ]
        error_doc.build(error_content)


def analyze_choice_question(content, q_df, question, styles, brand_colors):
    """
    Analyze and add visualizations for choice-based questions
    """
    from reportlab.graphics.shapes import Drawing
    from reportlab.graphics.charts.piecharts import Pie
    from reportlab.graphics.charts.barcharts import VerticalBarChart
    from reportlab.graphics.charts.legends import Legend
    from reportlab.lib import colors
    from reportlab.platypus import Table, TableStyle, Paragraph, Spacer
    
    if 'response' in q_df.columns and not q_df['response'].empty:
        response_counts = q_df['response'].value_counts()
        
        # Create a table for the response distribution
        data = [['Response', 'Count', 'Percentage']]
        total_responses = len(q_df)
        
        for response, count in response_counts.items():
            percentage = (count / total_responses) * 100
            data.append([str(response), int(count), f"{percentage:.1f}%"])
        
        # Add summary table
        table = Table(data, colWidths=[250, 60, 80])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), brand_colors['primary']),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), brand_colors['background']),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        content.append(table)
        
        # Add visualization using reportlab
        if len(response_counts) > 0:
            try:
                # For few options (<=5), use pie chart
                if len(response_counts) <= 5:
                    drawing = Drawing(400, 200)
                    pie = Pie()
                    pie.x = 150
                    pie.y = 50
                    pie.width = 150
                    pie.height = 150
                    pie.data = response_counts.values.tolist()
                    pie.labels = [str(label) for label in response_counts.index.tolist()]
                    
                    # Set custom slice colors
                    color_list = [
                        brand_colors['primary'], 
                        brand_colors['secondary'],
                        brand_colors['tertiary'],
                        brand_colors['quaternary'],
                        brand_colors['quinary']
                    ]
                    for i, _ in enumerate(pie.data):
                        if i < len(color_list):
                            pie.slices[i].fillColor = color_list[i]
                    
                    pie.slices.strokeWidth = 0.5
                    pie.sideLabels = True
                    
                    # Create legend
                    legend = Legend()
                    legend.alignment = 'right'
                    legend.x = 330
                    legend.y = 150
                    legend.colorNamePairs = [(color_list[i % len(color_list)], 
                                           str(label)) for i, label in 
                                          enumerate(response_counts.index.tolist())]
                    
                    drawing.add(pie)
                    drawing.add(legend)
                    content.append(drawing)
                else:
                    # For many options, use horizontal bar chart
                    drawing = Drawing(500, 250)
                    bc = VerticalBarChart()
                    bc.x = 50
                    bc.y = 50
                    bc.height = 150
                    bc.width = 350
                    
                    # Sort by count for better visualization
                    sorted_counts = response_counts.sort_values(ascending=False)
                    bc.data = [sorted_counts.values.tolist()]
                    
                    # Truncate long labels
                    cat_names = []
                    for name in sorted_counts.index.tolist():
                        if len(str(name)) > 20:
                            cat_names.append(str(name)[:17] + "...")
                        else:
                            cat_names.append(str(name))
                    
                    bc.categoryAxis.categoryNames = cat_names
                    bc.categoryAxis.labels.angle = 30
                    bc.categoryAxis.labels.boxAnchor = 'ne'
                    bc.categoryAxis.labels.dx = -8
                    bc.categoryAxis.labels.dy = -2
                    
                    bc.valueAxis.valueMin = 0
                    bc.valueAxis.valueMax = max(sorted_counts.values) * 1.1
                    bc.valueAxis.valueStep = max(1, int(max(sorted_counts.values) / 5))
                    
                    bc.bars[0].fillColor = brand_colors['primary']
                    drawing.add(bc)
                    content.append(drawing)
                
                # Add insights
                add_choice_question_insights(content, response_counts, total_responses, styles)
                
            except Exception as e:
                content.append(Paragraph(f"Could not generate visualization: {str(e)}", styles['Normal']))
    else:
        content.append(Paragraph("No response data available for this question.", styles['Normal']))


def analyze_scale_question(content, q_df, question, styles, brand_colors):
    """
    Analyze and add visualizations for scale-based questions
    """
    from reportlab.graphics.shapes import Drawing
    from reportlab.graphics.charts.barcharts import VerticalBarChart
    from reportlab.platypus import Table, TableStyle, Paragraph, Spacer
    from reportlab.lib import colors
    
    if 'response' in q_df.columns and q_df['response'].notna().any():
        # Try to convert responses to numeric
        try:
            q_df['response_numeric'] = pd.to_numeric(q_df['response'])
            
            # Calculate statistics
            avg_rating = q_df['response_numeric'].mean()
            median_rating = q_df['response_numeric'].median()
            std_dev = q_df['response_numeric'].std()
            min_rating = q_df['response_numeric'].min()
            max_rating = q_df['response_numeric'].max()
            q1 = q_df['response_numeric'].quantile(0.25)
            q3 = q_df['response_numeric'].quantile(0.75)
            
            # Create statistics table
            stats_data = [
                ['Metric', 'Value', 'Description'],
                ['Average Rating', f"{avg_rating:.2f}", 'Mean of all responses'],
                ['Median Rating', f"{median_rating:.2f}", 'Middle value of sorted responses'],
                ['Standard Deviation', f"{std_dev:.2f}", 'Measure of response variation'],
                ['Minimum', f"{min_rating:.2f}", 'Lowest rating given'],
                ['Maximum', f"{max_rating:.2f}", 'Highest rating given'],
                ['Q1 (25th Percentile)', f"{q1:.2f}", '25% of responses are below this value'],
                ['Q3 (75th Percentile)', f"{q3:.2f}", '75% of responses are below this value'],
                ['Response Count', len(q_df), 'Total number of responses']
            ]
            
            stats_table = Table(stats_data, colWidths=[150, 70, 200])
            stats_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), brand_colors['primary']),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('ALIGN', (1, 0), (1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('BACKGROUND', (0, 1), (-1, -1), brand_colors['background']),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            content.append(stats_table)
            content.append(Spacer(1, 10))
            
            # Add distribution information
            rating_counts = q_df['response_numeric'].value_counts().sort_index()
            
            # Create bar chart for distribution
            try:
                drawing = Drawing(400, 200)
                bc = VerticalBarChart()
                bc.x = 50
                bc.y = 50
                bc.height = 125
                bc.width = 300
                bc.data = [rating_counts.values.tolist()]
                bc.categoryAxis.categoryNames = [str(x) for x in rating_counts.index.tolist()]
                bc.valueAxis.valueMin = 0
                bc.valueAxis.valueMax = max(rating_counts.values) * 1.1
                bc.valueAxis.valueStep = max(1, int(max(rating_counts.values) / 5))
                bc.bars[0].fillColor = brand_colors['primary']
                
                # Add labels and title
                bc.categoryAxis.labels.fontName = 'Helvetica'
                bc.valueAxis.labels.fontName = 'Helvetica'
                bc.categoryAxis.title = "Rating"
                bc.valueAxis.title = "Number of Responses"
                
                drawing.add(bc)
                content.append(drawing)
                
                # Add insights based on distribution
                add_scale_question_insights(content, q_df['response_numeric'], styles)
                
            except Exception as e:
                content.append(Paragraph(f"Could not generate bar chart: {str(e)}", styles['Normal']))
        
        except Exception as e:
            content.append(Paragraph(f"Could not convert scale responses to numeric values: {str(e)}", styles['Normal']))
    else:
        content.append(Paragraph("No response data available for this question.", styles['Normal']))


def analyze_text_question(content, q_df, question, styles, brand_colors):
    """
    Analyze and add visualizations for text-based questions
    """
    from reportlab.platypus import Paragraph, Spacer, Table, TableStyle, ListFlowable, ListItem
    from reportlab.graphics.shapes import Drawing
    from reportlab.graphics.charts.barcharts import VerticalBarChart
    from reportlab.lib import colors
    from collections import Counter
    import re
    
    if 'response' in q_df.columns:
        text_responses = q_df['response'].dropna().tolist()
        
        # Calculate text statistics
        if text_responses:
            try:
                word_counts = [len(str(resp).split()) for resp in text_responses]
                avg_words = sum(word_counts) / len(word_counts) if word_counts else 0
                max_words = max(word_counts) if word_counts else 0
                min_words = min(word_counts) if word_counts else 0
                
                # Calculate character statistics
                char_counts = [len(str(resp)) for resp in text_responses]
                avg_chars = sum(char_counts) / len(char_counts) if char_counts else 0
                
                # Create text statistics table
                stats_data = [
                    ['Metric', 'Value'],
                    ['Number of responses', len(text_responses)],
                    ['Average response length', f"{avg_words:.1f} words ({avg_chars:.1f} characters)"],
                    ['Longest response', f"{max_words} words"],
                    ['Shortest response', f"{min_words} words"]
                ]
                
                stats_table = Table(stats_data, colWidths=[200, 200])
                stats_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), brand_colors['primary']),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('BACKGROUND', (0, 1), (-1, -1), brand_colors['background']),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black)
                ]))
                content.append(stats_table)
                content.append(Spacer(1, 10))
                
                # Perform word frequency analysis
                content.append(Paragraph("Word Frequency Analysis:", styles['NormalBold']))
                
                # Combine all text and extract word frequency
                all_text = ' '.join([str(resp) for resp in text_responses])
                words = re.findall(r'\b[a-zA-Z]{3,}\b', all_text.lower())  # Only words with 3+ chars
                
                # Remove common stop words
                stop_words = ['the', 'and', 'for', 'with', 'was', 'that', 'this', 'are', 'not', 'from']
                filtered_words = [word for word in words if word not in stop_words]
                
                # Get most common words
                word_freq = Counter(filtered_words).most_common(10)
                
                if word_freq:
                    # Create word frequency table and chart
                    freq_data = [['Word', 'Frequency']]
                    freq_data.extend(word_freq)
                    
                    freq_table = Table(freq_data, colWidths=[150, 70])
                    freq_table.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (-1, 0), brand_colors['secondary']),
                        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                        ('ALIGN', (1, 0), (1, -1), 'CENTER'),
                        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
                        ('GRID', (0, 0), (-1, -1), 1, colors.black)
                    ]))
                    content.append(freq_table)
                    content.append(Spacer(1, 10))
                    
                    # Create word frequency chart
                    try:
                        drawing = Drawing(400, 200)
                        bc = VerticalBarChart()
                        bc.x = 50
                        bc.y = 50
                        bc.height = 125
                        bc.width = 300
                        
                        # Sort by frequency for better visualization
                        bc.data = [[freq for _, freq in word_freq]]
                        bc.categoryAxis.categoryNames = [word for word, _ in word_freq]
                        bc.valueAxis.valueMin = 0
                        bc.valueAxis.valueMax = max([freq for _, freq in word_freq]) * 1.1
                        bc.valueAxis.valueStep = max(1, int(max([freq for _, freq in word_freq]) / 5))
                        bc.bars[0].fillColor = brand_colors['secondary']
                        
                        # Add labels and title
                        bc.categoryAxis.labels.fontName = 'Helvetica'
                        bc.categoryAxis.labels.angle = 45
                        bc.categoryAxis.labels.boxAnchor = 'ne'
                        bc.valueAxis.labels.fontName = 'Helvetica'
                        
                        drawing.add(bc)
                        content.append(drawing)
                    except Exception as e:
                        content.append(Paragraph(f"Could not generate word frequency chart: {str(e)}", styles['Normal']))
                
                # Add theme and sentiment analysis
                content.append(Spacer(1, 10))
                content.append(Paragraph("Key Themes:", styles['NormalBold']))
                
                # Extract themes (Here we're simplifying by using most common word pairs)
                bigrams = extract_bigrams(text_responses)
                
                theme_items = []
                for theme, count in bigrams[:5]:
                    theme_items.append(ListItem(Paragraph(f"{theme} (mentioned in {count} responses)", styles['Normal'])))
                
                if theme_items:
                    content.append(ListFlowable(theme_items, bulletType='bullet'))
                else:
                    content.append(Paragraph("No clear themes identified.", styles['Normal']))
                
                # Show sample responses with analysis
                content.append(Spacer(1, 10))
                content.append(Paragraph("Sample Responses with Analysis:", styles['NormalBold']))
                
                # Get up to 3 representative responses (choose longest ones as they're typically more informative)
                sample_responses = sorted(text_responses, key=len, reverse=True)[:3]
                
                for i, resp in enumerate(sample_responses):
                    content.append(Paragraph(f"<b>Response {i+1}:</b> {str(resp)}", styles['Normal']))
                    
                    # Add simple sentiment and length analysis
                    word_count = len(str(resp).split())
                    sentiment = simple_sentiment_analysis(str(resp))
                    
                    content.append(Paragraph(
                        f"<i>Analysis: {word_count} words. Sentiment appears to be {sentiment}.</i>", 
                        styles['InsightText']
                    ))
                    content.append(Spacer(1, 5))
                
            except Exception as e:
                content.append(Paragraph(f"Error analyzing text responses: {str(e)}", styles['Normal']))
        else:
            content.append(Paragraph("No text responses available for analysis.", styles['Normal']))
    else:
        content.append(Paragraph("No response column found in the data.", styles['Normal']))
    
    return content


def extract_bigrams(responses):
    """
    Extract most common word pairs (bigrams) from text responses
    """
    from collections import Counter
    import re
    
    # Combine all responses
    all_text = ' '.join([str(resp) for resp in responses])
    
    # Clean text
    clean_text = re.sub(r'[^\w\s]', '', all_text.lower())
    words = clean_text.split()
    
    # Filter out stop words
    stop_words = ['the', 'and', 'for', 'with', 'was', 'that', 'this', 'are', 'not', 'from',
                 'a', 'to', 'in', 'of', 'is', 'it', 'on', 'at', 'by', 'an', 'as', 'be']
    filtered_words = [word for word in words if word not in stop_words and len(word) > 2]
    
    # Generate bigrams
    bigrams = []
    for i in range(len(filtered_words) - 1):
        bigrams.append(f"{filtered_words[i]} {filtered_words[i+1]}")
    
    # Count and return most common
    bigram_counts = Counter(bigrams)
    
    # Convert counts to response occurrences (approximate)
    response_counts = []
    total_responses = len(responses)
    
    for bigram, count in bigram_counts.most_common(10):
        # Estimate in how many responses this bigram appears
        est_responses = min(total_responses, max(1, int(count / 3)))
        response_counts.append((bigram, est_responses))
    
    return response_counts


def simple_sentiment_analysis(text):
    """
    Perform a simple sentiment analysis on text
    """
    # Define simple sentiment word lists
    positive_words = [
        'good', 'great', 'excellent', 'amazing', 'wonderful', 'fantastic', 'happy',
        'best', 'better', 'love', 'like', 'enjoy', 'helpful', 'positive', 'awesome',
        'easy', 'perfect', 'satisfied', 'recommend', 'quality'
    ]
    
    negative_words = [
        'bad', 'poor', 'terrible', 'awful', 'horrible', 'worst', 'worse', 'hate',
        'dislike', 'difficult', 'hard', 'disappointing', 'negative', 'problem',
        'issue', 'broken', 'complicated', 'confused', 'unhappy', 'dissatisfied'
    ]
    
    # Count occurrences
    text_lower = text.lower()
    pos_count = sum(1 for word in positive_words if f' {word} ' in f' {text_lower} ')
    neg_count = sum(1 for word in negative_words if f' {word} ' in f' {text_lower} ')
    
    # Determine sentiment
    if pos_count > neg_count * 2:
        return "very positive"
    elif pos_count > neg_count:
        return "somewhat positive"
    elif neg_count > pos_count * 2:
        return "very negative"
    elif neg_count > pos_count:
        return "somewhat negative"
    else:
        return "neutral"


def calculate_completion_rate(df):
    """
    Calculate the overall completion rate for the dataset
    
    Args:
        df: DataFrame containing the dataset records
    
    Returns:
        float: Completion rate as a percentage
    """
    # Count unique users
    total_users = df['user_id'].nunique()
    
    if total_users == 0:
        return 0.0
    
    # Count unique questions
    total_questions = df['question_id'].nunique()
    
    # Calculate questions per user
    questions_per_user = df.groupby('user_id')['question_id'].nunique().mean()
    
    # Calculate completion rate
    completion_rate = (questions_per_user / total_questions) * 100 if total_questions > 0 else 0
    
    return completion_rate

def calculate_average_time_spent(df):
    """
    Calculate the average time users spent on the poll
    
    Args:
        df: DataFrame containing the dataset records
    
    Returns:
        str: Formatted average time spent
    """
    import pandas as pd
    
    # Check if timestamp column exists and has data
    if 'timestamp' not in df.columns or df['timestamp'].isna().all():
        return "N/A"
    
    try:
        # Convert timestamps to datetime objects
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        # Group by user_id and calculate time difference between first and last response
        user_times = df.groupby('user_id')['timestamp'].agg(['min', 'max'])
        user_times['duration'] = (user_times['max'] - user_times['min']).dt.total_seconds() / 60  # in minutes
        
        # Calculate average duration
        avg_minutes = user_times['duration'].mean()
        
        # Format the result
        if avg_minutes < 1:
            return f"{avg_minutes * 60:.1f} seconds"
        elif avg_minutes < 60:
            return f"{avg_minutes:.1f} minutes"
        else:
            hours = int(avg_minutes // 60)
            minutes = int(avg_minutes % 60)
            return f"{hours} hour{'s' if hours != 1 else ''} {minutes} minute{'s' if minutes != 1 else ''}"
    
    except Exception:
        return "N/A"

def generate_key_insights(df, poll_data):
    """
    Generate key insights from the overall dataset
    
    Args:
        df: DataFrame containing the dataset records
        poll_data: List of poll dictionaries
    
    Returns:
        list: List of insight strings
    """
    insights = []
    
    # Check if we have data to analyze
    if df.empty:
        return ["No data available for analysis."]
    
    # Get overall response count
    total_responses = df['user_id'].nunique()
    insights.append(f"The dataset contains responses from {total_responses} participants across {len(poll_data)} polls.")
    
    # Identify most and least responded-to questions
    question_response_counts = df.groupby(['question_text'])['user_id'].nunique().sort_values(ascending=False)
    
    if not question_response_counts.empty:
        most_responded = question_response_counts.index[0]
        most_responded_count = question_response_counts.iloc[0]
        insights.append(f"The question with highest engagement was '{most_responded}' with {most_responded_count} responses.")
        
        # Only add least responded if we have more than one question
        if len(question_response_counts) > 1:
            least_responded = question_response_counts.index[-1]
            least_responded_count = question_response_counts.iloc[-1]
            insights.append(f"The question with lowest engagement was '{least_responded}' with {least_responded_count} responses.")
    
    # Identify trends in rating questions if applicable
    rating_questions = df[df['question_type'].isin(['rating_scale', 'likert_scale'])]
    if not rating_questions.empty:
        try:
            # Convert to numeric for analysis
            rating_questions['response_numeric'] = pd.to_numeric(rating_questions['response'], errors='coerce')
            
            # Group by question and calculate average rating
            avg_ratings = rating_questions.groupby('question_text')['response_numeric'].mean().sort_values(ascending=False)
            
            if not avg_ratings.empty:
                highest_rated = avg_ratings.index[0]
                highest_rating = avg_ratings.iloc[0]
                insights.append(f"The highest rated item was '{highest_rated}' with an average score of {highest_rating:.2f}.")
                
                if len(avg_ratings) > 1:
                    lowest_rated = avg_ratings.index[-1]
                    lowest_rating = avg_ratings.iloc[-1]
                    insights.append(f"The lowest rated item was '{lowest_rated}' with an average score of {lowest_rating:.2f}.")
        except:
            # Skip this analysis if conversion to numeric fails
            pass
    
    # Add completion time insight if available
    if 'timestamp' in df.columns and not df['timestamp'].isna().all():
        avg_time = calculate_average_time_spent(df)
        if avg_time != "N/A":
            insights.append(f"Participants spent an average of {avg_time} completing the polls.")
    
    return insights

def generate_poll_insights(poll_df, poll):
    """
    Generate insights specific to a single poll
    
    Args:
        poll_df: DataFrame filtered for a specific poll
        poll: Dictionary containing poll data
    
    Returns:
        list: List of insight strings
    """
    insights = []
    
    # Check if we have data to analyze
    if poll_df.empty:
        return ["No data available for this poll."]
    
    # Get response count for this poll
    poll_responses = poll_df['user_id'].nunique()
    
    # Check if this poll has multiple questions
    question_count = len(poll.get('questions', []))
    if question_count > 1:
        # Calculate average responses per question
        avg_responses_per_question = poll_df.groupby('question_id')['user_id'].nunique().mean()
        
        # Calculate drop-off rate
        first_question_responses = poll_df[poll_df['question_id'] == poll.get('questions', [{}])[0].get('question_id')]['user_id'].nunique()
        last_question_responses = poll_df[poll_df['question_id'] == poll.get('questions', [{}])[-1].get('question_id')]['user_id'].nunique()
        
        if first_question_responses > 0:
            drop_off_rate = ((first_question_responses - last_question_responses) / first_question_responses) * 100
            insights.append(f"Poll completion drop-off rate: {drop_off_rate:.1f}% (started: {first_question_responses}, completed: {last_question_responses})")
    
    # Find most common responses for single/multiple choice questions
    choice_questions = poll_df[poll_df['question_type'].isin(['single_choice', 'multiple_choice'])]
    if not choice_questions.empty:
        # Group by question and find most common response
        common_responses = choice_questions.groupby('question_text')['response'].agg(
            lambda x: x.value_counts().index[0] if len(x.value_counts()) > 0 else None
        )
        
        # Add insights for up to 2 questions
        for i, (question, response) in enumerate(common_responses.items()):
            if i >= 2:  # Limit to 2 questions to avoid overwhelming
                break
            if response:
                insights.append(f"For '{question}', the most common response was '{response}'.")
    
    # Analyze rating questions
    rating_questions = poll_df[poll_df['question_type'].isin(['rating_scale', 'likert_scale'])]
    if not rating_questions.empty:
        try:
            # Convert to numeric for analysis
            rating_questions['response_numeric'] = pd.to_numeric(rating_questions['response'], errors='coerce')
            
            # Find highest and lowest rated items
            avg_ratings = rating_questions.groupby('question_text')['response_numeric'].mean().sort_values(ascending=False)
            
            if len(avg_ratings) > 0:
                highest_question = avg_ratings.index[0]
                highest_rating = avg_ratings.iloc[0]
                insights.append(f"Highest rated item: '{highest_question}' ({highest_rating:.2f}/5)")
                
                if len(avg_ratings) > 1:
                    lowest_question = avg_ratings.index[-1]
                    lowest_rating = avg_ratings.iloc[-1]
                    insights.append(f"Lowest rated item: '{lowest_question}' ({lowest_rating:.2f}/5)")
        except:
            pass
    
    return insights

def add_choice_question_insights(content, response_counts, total_responses, styles):
    """
    Add insights for choice questions
    
    Args:
        content: List to append content to
        response_counts: Series containing response counts
        total_responses: Total number of responses
        styles: ReportLab style sheet
    """
    from reportlab.platypus import Paragraph, Spacer
    
    # Calculate percentages
    percentages = (response_counts / total_responses * 100).sort_values(ascending=False)
    
    # Generate insights based on distribution
    insights = []
    
    # Most common response
    if not percentages.empty:
        top_response = percentages.index[0]
        top_percentage = percentages.iloc[0]
        insights.append(f"The most common response was '{top_response}' selected by {top_percentage:.1f}% of respondents.")
        
        # Check for strong consensus (>70%)
        if top_percentage > 70:
            insights.append(f"There is a strong consensus around the '{top_response}' option.")
        
        # Check for close top choices
        if len(percentages) > 1 and (top_percentage - percentages.iloc[1]) < 10:
            second_response = percentages.index[1]
            second_percentage = percentages.iloc[1]
            insights.append(f"'{top_response}' ({top_percentage:.1f}%) and '{second_response}' ({second_percentage:.1f}%) received similar levels of support.")
        
        # Check for polarized responses (bimodal distribution)
        if len(percentages) > 2 and percentages.iloc[0] > 30 and percentages.iloc[1] > 30 and (percentages.iloc[1] - percentages.iloc[2]) > 20:
            insights.append("Responses show a polarized opinion with two dominant choices.")
    
    # Add insights to content
    if insights:
        content.append(Spacer(1, 10))
        content.append(Paragraph("Analysis:", styles['NormalBold']))
        for insight in insights:
            content.append(Paragraph(f"• {insight}", styles['InsightText']))

def add_scale_question_insights(content, response_numeric, styles):
    """
    Add insights for scale questions
    
    Args:
        content: List to append content to
        response_numeric: Series containing numeric responses
        styles: ReportLab style sheet
    """
    from reportlab.platypus import Paragraph, Spacer
    
    # Generate insights based on distribution
    insights = []
    
    # Basic statistics
    mean = response_numeric.mean()
    median = response_numeric.median()
    std_dev = response_numeric.std()
    
    # Interpret mean score
    if mean > 4:
        insights.append(f"Very positive rating with an average of {mean:.2f} out of 5.")
    elif mean > 3:
        insights.append(f"Generally positive rating with an average of {mean:.2f} out of 5.")
    elif mean > 2:
        insights.append(f"Neutral to slightly positive rating with an average of {mean:.2f} out of 5.")
    else:
        insights.append(f"Below average rating with a score of {mean:.2f} out of 5.")
    
    # Check for consensus vs. divergence
    if std_dev < 0.8:
        insights.append(f"Responses show strong consensus (standard deviation: {std_dev:.2f}).")
    elif std_dev > 1.5:
        insights.append(f"Responses show significant variability (standard deviation: {std_dev:.2f}), indicating divergent opinions.")
    
    # Check for skewness (difference between mean and median)
    if abs(mean - median) > 0.3:
        if mean > median:
            insights.append("The distribution is positively skewed with a few high ratings pulling up the average.")
        else:
            insights.append("The distribution is negatively skewed with a few low ratings pulling down the average.")
    
    # Add insights to content
    if insights:
        content.append(Spacer(1, 10))
        content.append(Paragraph("Analysis:", styles['NormalBold']))
        for insight in insights:
            content.append(Paragraph(f"• {insight}", styles['InsightText']))

def extract_bigrams(text_responses):
    """
    Extract common bigrams (word pairs) from text responses
    
    Args:
        text_responses: List of text responses
    
    Returns:
        list: List of (bigram, count) tuples
    """
    from collections import Counter
    import re
    
    # Combine all responses
    all_text = ' '.join([str(resp).lower() for resp in text_responses])
    
    # Clean text and split into words
    words = re.findall(r'\b[a-zA-Z]{3,}\b', all_text)
    
    # Skip if not enough words
    if len(words) < 2:
        return []
    
    # Create bigrams
    bigrams = [f"{words[i]} {words[i+1]}" for i in range(len(words)-1)]
    
    # Count and return top bigrams with a count
    bigram_counts = Counter(bigrams).most_common(5)
    
    # Add a count indicator to each bigram
    return [(bigram, count) for bigram, count in bigram_counts]

def simple_sentiment_analysis(text):
    """
    Perform very simple sentiment analysis on text
    
    Args:
        text: Text to analyze
    
    Returns:
        str: Sentiment description
    """
    # Lists of positive and negative words
    positive_words = [
        'good', 'great', 'excellent', 'wonderful', 'amazing', 'fantastic', 'terrific', 
        'outstanding', 'exceptional', 'impressive', 'remarkable', 'like', 'love', 'best',
        'happy', 'pleased', 'satisfied', 'enjoy', 'positive', 'recommend', 'helpful',
        'useful', 'beneficial', 'valuable', 'favorable'
    ]
    
    negative_words = [
        'bad', 'poor', 'terrible', 'horrible', 'awful', 'disappointing', 'dreadful',
        'dislike', 'hate', 'worst', 'unhappy', 'frustrated', 'dissatisfied', 'negative',
        'useless', 'waste', 'problem', 'difficult', 'hard', 'complicated', 'confusing',
        'expensive', 'overpriced', 'unreliable'
    ]
    
    # Normalize text
    text_lower = text.lower()
    
    # Count occurrences
    pos_count = sum(1 for word in positive_words if word in text_lower)
    neg_count = sum(1 for word in negative_words if word in text_lower)
    
    # Determine sentiment
    if pos_count > neg_count * 2:
        return "strongly positive"
    elif pos_count > neg_count:
        return "somewhat positive"
    elif neg_count > pos_count * 2:
        return "strongly negative"
    elif neg_count > pos_count:
        return "somewhat negative"
    else:
        return "neutral or mixed"

def dataset_to_dataframe(dataset):
    """Convert dataset JSON to pandas DataFrame with proper handling of different question types"""
    rows = []
    
    for poll in dataset.data:
        poll_id = poll.get('poll_id')
        poll_title = poll.get('poll_title')
        
        for question in poll.get('questions', []):
            question_id = question.get('question_id')
            question_text = question.get('text')
            question_type = question.get('type')
            
            # Process responses based on question type
            for response in question.get('responses', []):
                row = {
                    'poll_id': poll_id,
                    'poll_title': poll_title,
                    'question_id': question_id,
                    'question_text': question_text,
                    'question_type': question_type,
                    'user_id': response.get('user_id'),
                    'timestamp': response.get('timestamp')
                }
                
                # Handle different question types and their specific response formats
                if question_type in ['single_choice', 'multiple_choice']:
                    # For choice questions, extract the selected option(s)
                    row['response_type'] = 'choice'
                    row['response'] = response.get('response')
                    
                    # For multiple choice, response might be a list
                    if question_type == 'multiple_choice' and isinstance(row['response'], list):
                        row['response'] = ', '.join(str(item) for item in row['response'])
                
                elif question_type in ['rating_scale', 'likert_scale']:
                    # For scale questions, ensure response is numeric
                    row['response_type'] = 'scale'
                    row['response'] = response.get('response')
                    row['scale_min'] = question.get('scale_min', 1)
                    row['scale_max'] = question.get('scale_max', 5)
                
                elif question_type in ['open_ended', 'short_answer', 'essay']:
                    # For text-based questions
                    row['response_type'] = 'text'
                    row['response'] = response.get('response')
                    
                    # Add word count for text responses
                    if response.get('response'):
                        row['word_count'] = len(str(response.get('response')).split())
                
                elif question_type == 'true_false':
                    # For true/false questions
                    row['response_type'] = 'basic'
                    row['response'] = response.get('response')
                    
                else:
                    # Default handling for any other question types
                    row['response_type'] = 'other'
                    row['response'] = response.get('response')
                
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

@method_decorator(login_required, name='dispatch')
class VisualizationDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Visualization
    template_name = 'analytics/visualization_confirm_delete.html'
    
    def test_func(self):
        visualization = self.get_object()
        return self.request.user == visualization.creator

    def get_success_url(self):
        messages.success(self.request, _('Visualization deleted successfully!'))
        return reverse_lazy('analytics:visualization_list')

@method_decorator(login_required, name='dispatch')
class VisualizationUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Visualization
    form_class = VisualizationForm
    template_name = 'analytics/visualization_form.html'
    # Removed slug_field and slug_url_kwarg since we're using pk
    
    def test_func(self):
        visualization = self.get_object()
        return self.request.user == visualization.creator

    def form_valid(self, form):
        messages.success(self.request, _('Visualization updated successfully!'))
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('analytics:visualization_detail', kwargs={'pk': self.object.pk})
    

@login_required
def visualization_export(request, pk):
    """Export a visualization in JSON format."""
    visualization = get_object_or_404(Visualization, pk=pk)

    # Check if the user has access to the visualization
    if visualization.creator != request.user and not visualization.dataset.is_public:
        return HttpResponseForbidden()

    # Prepare the response data
    response_data = {
        'title': visualization.title,
        'data': visualization.data,
        'config': visualization.config,
    }

    # Return the response as JSON
    response = HttpResponse(json.dumps(response_data, indent=2), content_type='application/json')
    response['Content-Disposition'] = f'attachment; filename="{visualization.title}.json"'
    return response


class VisualizationDetailView(LoginRequiredMixin, DetailView):
    model = Visualization
    template_name = 'analytics/visualization_detail.html'
    context_object_name = 'visualization'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        visualization = self.get_object()
        
        # Add dataset to context
        context['dataset'] = visualization.dataset
        
        # Add visualization config for rendering
        context['viz_config'] = {
            'type': visualization.visualization_type,
            'data': visualization.data,  # The pre-processed data
            'config': visualization.config
        }
        
        # Add creator information
        context['is_creator'] = (self.request.user == visualization.creator)
        
        return context
    
    def dispatch(self, request, *args, **kwargs):
        # Get the visualization
        self.object = self.get_object()
        visualization = self.object
        user = request.user
        dataset = visualization.dataset
        
        # Check if user has access to the dataset
        has_access = (dataset.creator == user or 
                      user in dataset.collaborators.all() or 
                      dataset.is_public)
        
        if not has_access:
            return self.handle_no_permission()
        
        return super().dispatch(request, *args, **kwargs)


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
        # Filter jobs created by the logged-in user and order by created_at
        return AnalyticsJob.objects.filter(creator=self.request.user).order_by('-created_at')

    def get_context_data(self, **kwargs):
        # Get the default context
        context = super().get_context_data(**kwargs)
        # Add filtered jobs to the context using the correct status values
        context['active_jobs'] = self.get_queryset().filter(status='active')  # Adjust 'active' as needed
        context['completed_jobs'] = self.get_queryset().filter(status='completed')  # Adjust as needed
        return context


@login_required
def job_detail(request, pk):
    """View details of an analytics job"""
    job = get_object_or_404(AnalyticsJob, pk=pk, creator=request.user)
    return render(request, 'analytics/job_detail.html', {'job': job})