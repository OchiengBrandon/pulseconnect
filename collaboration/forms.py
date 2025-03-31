from django import forms
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.db import models
from .models import (
    ResearchProject, ProjectMembership, ProjectTask, 
    ProjectDocument, ProjectInvitation
)
from analytics.models import DataSet

class ResearchProjectForm(forms.ModelForm):
    class Meta:
        model = ResearchProject
        fields = ['title', 'description', 'status', 'is_public', 'start_date', 'end_date', 'datasets']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
        }
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        for field_name in self.fields:
            if field_name not in ['is_public', 'datasets']:
                self.fields[field_name].widget.attrs.update({'class': 'form-control'})
        
        self.fields['is_public'].widget = forms.CheckboxInput(attrs={'class': 'form-check-input'})
        
        # Filter datasets based on user access
        if self.user:
            self.fields['datasets'].queryset = DataSet.objects.filter(
                models.Q(creator=self.user) | 
                models.Q(collaborators=self.user) |
                models.Q(is_public=True)
            ).distinct()
            self.fields['datasets'].widget = forms.CheckboxSelectMultiple()
    
    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        
        if start_date and end_date and end_date < start_date:
            self.add_error('end_date', _('End date must be after start date.'))
        
        return cleaned_data


class ProjectMembershipForm(forms.ModelForm):
    class Meta:
        model = ProjectMembership
        fields = ['role', 'can_edit', 'can_invite']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.fields['role'].widget.attrs.update({'class': 'form-control'})
        self.fields['can_edit'].widget = forms.CheckboxInput(attrs={'class': 'form-check-input'})
        self.fields['can_invite'].widget = forms.CheckboxInput(attrs={'class': 'form-check-input'})


class ProjectTaskForm(forms.ModelForm):
    class Meta:
        model = ProjectTask
        fields = ['title', 'description', 'assigned_to', 'status', 'priority', 'due_date']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'due_date': forms.DateInput(attrs={'type': 'date'}),
        }
    
    def __init__(self, *args, **kwargs):
        self.project = kwargs.pop('project', None)
        super().__init__(*args, **kwargs)
        
        for field_name in self.fields:
            self.fields[field_name].widget.attrs.update({'class': 'form-control'})
        
        # Filter assigned_to to only include project members
        if self.project:
            self.fields['assigned_to'].queryset = self.project.members.all()


class ProjectDocumentForm(forms.ModelForm):
    class Meta:
        model = ProjectDocument
        fields = ['title', 'description', 'content', 'file']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 2}),
            'content': forms.Textarea(attrs={'rows': 10, 'class': 'markdown-editor'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        for field_name in self.fields:
            if field_name != 'content':  # Content field has special styling
                self.fields[field_name].widget.attrs.update({'class': 'form-control'})


class ProjectInvitationForm(forms.ModelForm):
    class Meta:
        model = ProjectInvitation
        fields = ['email', 'role']
    
    def __init__(self, *args, **kwargs):
        self.project = kwargs.pop('project', None)
        self.invited_by = kwargs.pop('invited_by', None)
        super().__init__(*args, **kwargs)
        
        for field_name in self.fields:
            self.fields[field_name].widget.attrs.update({'class': 'form-control'})
    
    def clean_email(self):
        email = self.cleaned_data['email']
        
        # Check if invitation already exists
        if self.project:
            if ProjectInvitation.objects.filter(
                project=self.project,
                email=email,
                status='pending'
            ).exists():
                raise forms.ValidationError(_('An invitation has already been sent to this email.'))
            
            # Check if user is already a member
            from django.contrib.auth import get_user_model
            User = get_user_model()
            try:
                user = User.objects.get(email=email)
                if self.project.members.filter(id=user.id).exists():
                    raise forms.ValidationError(_('This user is already a member of the project.'))
            except User.DoesNotExist:
                pass
        
        return email
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        
        if self.project:
            instance.project = self.project
        
        if self.invited_by:
            instance.invited_by = self.invited_by
        
        # Set expiration date (7 days from now)
        instance.expires_at = timezone.now() + timezone.timedelta(days=7)
        
        # Try to find user by email
        from django.contrib.auth import get_user_model
        User = get_user_model()
        try:
            user = User.objects.get(email=instance.email)
            instance.invited_user = user
        except User.DoesNotExist:
            pass
        
        if commit:
            instance.save()
        
        return instance