from django import forms
from django.utils.translation import gettext_lazy as _
from django.contrib.contenttypes.models import ContentType
from .models import Discussion, Comment, Event, VolunteerOpportunity, Impact
from polls.models import Poll
from django.db import models

class DiscussionForm(forms.ModelForm):
    class Meta:
        model = Discussion
        fields = ['title', 'content', 'related_poll', 'tags']
        widgets = {
            'content': forms.Textarea(attrs={'rows': 6}),
        }
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        for field_name in self.fields:
            if field_name != 'tags':
                self.fields[field_name].widget.attrs.update({'class': 'form-control'})
        
        # Filter polls based on user access
        if self.user:
            self.fields['related_poll'].queryset = Poll.objects.filter(
                models.Q(creator=self.user) | models.Q(poll_type='public')
            ).distinct()
        
        # For the tags field
        self.fields['tags'].widget.attrs.update({'class': 'form-control select2-tags'})


class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ['content']
        widgets = {
            'content': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
        }


class EventForm(forms.ModelForm):
    class Meta:
        model = Event
        fields = ['title', 'description', 'location', 'is_virtual', 'virtual_link',
                 'start_datetime', 'end_datetime', 'related_poll', 'is_public']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
            'start_datetime': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'end_datetime': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        }
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        for field_name in self.fields:
            self.fields[field_name].widget.attrs.update({'class': 'form-control'})
        
        self.fields['is_virtual'].widget = forms.CheckboxInput(attrs={'class': 'form-check-input'})
        self.fields['is_public'].widget = forms.CheckboxInput(attrs={'class': 'form-check-input'})
        
        # Filter polls based on user access
        if self.user:
            self.fields['related_poll'].queryset = Poll.objects.filter(
                models.Q(creator=self.user) | models.Q(poll_type='public')
            ).distinct()
    
    def clean(self):
        cleaned_data = super().clean()
        start = cleaned_data.get('start_datetime')
        end = cleaned_data.get('end_datetime')
        
        if start and end and end <= start:
            self.add_error('end_datetime', _('End time must be after start time.'))
        
        is_virtual = cleaned_data.get('is_virtual')
        virtual_link = cleaned_data.get('virtual_link')
        
        if is_virtual and not virtual_link:
            self.add_error('virtual_link', _('Virtual link is required for virtual events.'))
        
        return cleaned_data


class VolunteerOpportunityForm(forms.ModelForm):
    class Meta:
        model = VolunteerOpportunity
        fields = ['title', 'description', 'organization', 'location', 'contact_email',
                 'contact_phone', 'start_date', 'end_date', 'related_poll', 'is_active', 'tags']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
        }
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        for field_name in self.fields:
            if field_name not in ['is_active', 'tags']:
                self.fields[field_name].widget.attrs.update({'class': 'form-control'})
        
        self.fields['is_active'].widget = forms.CheckboxInput(attrs={'class': 'form-check-input'})
        
        # For the tags field
        self.fields['tags'].widget.attrs.update({'class': 'form-control select2-tags'})
        
        # Filter polls based on user access
        if self.user:
            self.fields['related_poll'].queryset = Poll.objects.filter(
                models.Q(creator=self.user) | models.Q(poll_type='public')
            ).distinct()
    
    def clean(self):
        cleaned_data = super().clean()
        start = cleaned_data.get('start_date')
        end = cleaned_data.get('end_date')
        
        if start and end and end < start:
            self.add_error('end_date', _('End date must be after start date.'))
        
        return cleaned_data


class ImpactForm(forms.ModelForm):
    class Meta:
        model = Impact
        fields = ['title', 'description', 'poll', 'impact_type', 'outcome', 'evidence', 'evidence_url']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'outcome': forms.Textarea(attrs={'rows': 3}),
            'evidence': forms.Textarea(attrs={'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        for field_name in self.fields:
            self.fields[field_name].widget.attrs.update({'class': 'form-control'})
        
        # Filter polls based on user access
        if self.user:
            self.fields['poll'].queryset = Poll.objects.filter(
                models.Q(creator=self.user) | models.Q(poll_type='public')
            ).distinct()


class ImpactVerificationForm(forms.Form):
    """Form for verifying impact reports"""
    verify = forms.BooleanField(
        required=False,
        label=_('Verify this impact report'),
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    notes = forms.CharField(
        required=False,
        label=_('Verification Notes'),
        widget=forms.Textarea(attrs={'rows': 3, 'class': 'form-control'})
    )