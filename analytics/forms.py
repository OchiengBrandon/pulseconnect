from django import forms
from django.utils.translation import gettext_lazy as _
from .models import DataSet, AnalysisReport, Visualization, AnalyticsJob
from polls.models import Poll
from django.db import models
import json

class DataSetForm(forms.ModelForm):
    class Meta:
        model = DataSet
        fields = ['title', 'description', 'is_public', 'source_polls']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
            'source_polls': forms.CheckboxSelectMultiple(),
        }
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        for field_name in self.fields:
            if field_name != 'source_polls':
                self.fields[field_name].widget.attrs.update({'class': 'form-control'})
        
        self.fields['is_public'].widget = forms.CheckboxInput(attrs={'class': 'form-check-input'})
        
        # Filter polls based on user access
        if self.user:
            if self.user.user_type == 'researcher':
                # Researchers can access all public polls and their own polls
                self.fields['source_polls'].queryset = Poll.objects.filter(
                    models.Q(poll_type='public') | 
                    models.Q(creator=self.user)
                ).distinct()
            else:
                # Other users can only access their own polls
                self.fields['source_polls'].queryset = Poll.objects.filter(creator=self.user)


class CollaboratorForm(forms.Form):
    """Form for adding collaborators to a dataset or report"""
    collaborators = forms.CharField(
        label=_('Collaborators'),
        help_text=_('Enter usernames separated by commas'),
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )


class AnalysisReportForm(forms.ModelForm):
    class Meta:
        model = AnalysisReport
        fields = ['title', 'description', 'is_public', 'datasets']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
            'datasets': forms.CheckboxSelectMultiple(),
        }
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        for field_name in self.fields:
            if field_name != 'datasets':
                self.fields[field_name].widget.attrs.update({'class': 'form-control'})
        
        self.fields['is_public'].widget = forms.CheckboxInput(attrs={'class': 'form-check-input'})
        
        # Filter datasets based on user access
        if self.user:
            self.fields['datasets'].queryset = DataSet.objects.filter(
                models.Q(creator=self.user) | 
                models.Q(collaborators=self.user) |
                models.Q(is_public=True)
            ).distinct()



class VisualizationForm(forms.ModelForm):
    class Meta:
        model = Visualization
        fields = ['title', 'description', 'dataset', 'visualization_type', 'config']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'config': forms.HiddenInput(),  # Will be populated via JavaScript
        }
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Limit dataset choices to those accessible by the user
        if self.user:
            self.fields['dataset'].queryset = DataSet.objects.filter(
                models.Q(creator=self.user) | 
                models.Q(is_public=True)
            )

        # Add UUID data attributes to dataset choices
        self.fields['dataset'].widget.attrs['class'] = 'form-control dataset-selector'
        
        # Create a list of dataset UUIDs for JavaScript
        dataset_uuids = {
            str(dataset.id): str(dataset.uuid) 
            for dataset in self.fields['dataset'].queryset
        }
        
        # Store UUIDs as data attribute
        self.fields['dataset'].widget.attrs['data-uuids'] = json.dumps(dataset_uuids)
        
        # Visualization type choices
        self.fields['visualization_type'] = forms.ChoiceField(
            choices=[
                ('bar', _('Bar Chart')),
                ('pie', _('Pie Chart')),
                ('line', _('Line Chart')),
                ('scatter', _('Scatter Plot')),
                ('wordcloud', _('Word Cloud')),
            ],
            widget=forms.Select(attrs={'class': 'form-control'})
        )
        
        # Fields for different viz types (will be shown/hidden via JS)
        self.fields['category_field'] = forms.CharField(
            required=False, 
            label=_('Category Field'),
            widget=forms.Select(attrs={'class': 'form-control field-selector'})
        )
        
        self.fields['value_field'] = forms.CharField(
            required=False, 
            label=_('Value Field'),
            widget=forms.Select(attrs={'class': 'form-control field-selector'})
        )
        
        self.fields['time_field'] = forms.CharField(
            required=False, 
            label=_('Time Field'),
            widget=forms.Select(attrs={'class': 'form-control field-selector'})
        )
        
        self.fields['x_field'] = forms.CharField(
            required=False, 
            label=_('X-Axis Field'),
            widget=forms.Select(attrs={'class': 'form-control field-selector'})
        )
        
        self.fields['y_field'] = forms.CharField(
            required=False, 
            label=_('Y-Axis Field'),
            widget=forms.Select(attrs={'class': 'form-control field-selector'})
        )
        
        self.fields['series_field'] = forms.CharField(
            required=False, 
            label=_('Series Field (Optional)'),
            widget=forms.Select(attrs={'class': 'form-control field-selector'})
        )
        
        self.fields['text_field'] = forms.CharField(
            required=False, 
            label=_('Text Field'),
            widget=forms.Select(attrs={'class': 'form-control field-selector'})
        )
        
        self.fields['limit'] = forms.IntegerField(
            required=False,
            initial=10,
            min_value=1,
            max_value=100,
            label=_('Limit'),
            help_text=_('Maximum number of items to display')
        )
        
        self.fields['chart_title'] = forms.CharField(
            required=False,
            label=_('Chart Title')
        )
    
    def clean(self):
        cleaned_data = super().clean()
        viz_type = cleaned_data.get('visualization_type')
        
        # Build configuration object based on visualization type
        config = {}
        
        if viz_type == 'bar' or viz_type == 'pie':
            category_field = cleaned_data.get('category_field')
            value_field = cleaned_data.get('value_field')
            
            if not category_field:
                self.add_error('category_field', _('Category field is required for this visualization type'))
            if not value_field:
                self.add_error('value_field', _('Value field is required for this visualization type'))
                
            config.update({
                'category_field': category_field,
                'value_field': value_field,
                'sort_desc': True,
                'limit': cleaned_data.get('limit', 10)
            })
            
        elif viz_type == 'line':
            time_field = cleaned_data.get('time_field')
            value_field = cleaned_data.get('value_field')
            
            if not time_field:
                self.add_error('time_field', _('Time field is required for line charts'))
            if not value_field:
                self.add_error('value_field', _('Value field is required for line charts'))
                
            config.update({
                'time_field': time_field,
                'value_field': value_field,
                'series_field': cleaned_data.get('series_field'),
                'chart_title': cleaned_data.get('chart_title'),
                'fill': False
            })
            
        elif viz_type == 'scatter':
            x_field = cleaned_data.get('x_field')
            y_field = cleaned_data.get('y_field')
            
            if not x_field:
                self.add_error('x_field', _('X-axis field is required for scatter plots'))
            if not y_field:
                self.add_error('y_field', _('Y-axis field is required for scatter plots'))
                
            config.update({
                'x_field': x_field,
                'y_field': y_field,
                'series_field': cleaned_data.get('series_field'),
                'chart_title': cleaned_data.get('chart_title')
            })
            
        elif viz_type == 'wordcloud':
            text_field = cleaned_data.get('text_field')
            
            if not text_field:
                self.add_error('text_field', _('Text field is required for word clouds'))
                
            config.update({
                'text_field': text_field,
                'limit': cleaned_data.get('limit', 100),
                'stopwords': ['and', 'the', 'to', 'a', 'of', 'for', 'in', 'is', 'on', 'that', 'by']
            })
        
        # Store configuration
        cleaned_data['config'] = config
        
        return cleaned_data


class DataImportForm(forms.Form):
    """Form for importing external data"""
    title = forms.CharField(
        max_length=255,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    description = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3})
    )
    file = forms.FileField(
        widget=forms.FileInput(attrs={'class': 'form-control'})
    )
    file_format = forms.ChoiceField(
        choices=[
            ('csv', _('CSV')),
            ('json', _('JSON')),
            ('excel', _('Excel')),
        ],
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    is_public = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )


class AnalyticsJobForm(forms.ModelForm):
    class Meta:
        model = AnalyticsJob
        fields = ['job_type', 'parameters']
        widgets = {
            'parameters': forms.HiddenInput(),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name in self.fields:
            self.fields[field_name].widget.attrs.update({'class': 'form-control'})