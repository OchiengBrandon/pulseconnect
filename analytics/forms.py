from django import forms
from django.utils.translation import gettext_lazy as _
from .models import DataSet, AnalysisReport, Visualization, AnalyticsJob
from polls.models import Poll

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
        fields = ['title', 'description', 'visualization_type', 'dataset', 'config']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'config': forms.HiddenInput(),
        }
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        for field_name in self.fields:
            self.fields[field_name].widget.attrs.update({'class': 'form-control'})
        
        # Filter datasets based on user access
        if self.user:
            self.fields['dataset'].queryset = DataSet.objects.filter(
                models.Q(creator=self.user) | 
                models.Q(collaborators=self.user) |
                models.Q(is_public=True)
            ).distinct()


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