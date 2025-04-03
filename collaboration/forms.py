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
            'title': forms.TextInput(attrs={
                'placeholder': 'Enter task title',
                'autocomplete': 'off'
            }),
            'description': forms.Textarea(attrs={
                'rows': 3,
                'placeholder': 'Enter task description',
                'style': 'resize: vertical; min-height: 80px;'
            }),
            'due_date': forms.DateInput(attrs={
                'type': 'date',
                'data-toggle': 'datepicker'
            }),
            'status': forms.Select(attrs={
                'class': 'form-select'  # Bootstrap select styling
            }),
            'priority': forms.Select(attrs={
                'class': 'form-select'  # Bootstrap select styling
            }),
            'assigned_to': forms.Select(attrs={
                'class': 'form-select'  # Bootstrap select styling
            })
        }
        
        help_texts = {
            'title': 'Give your task a clear and concise title',
            'description': 'Provide detailed information about the task',
            'due_date': 'When should this task be completed?',
            'priority': 'Set the importance level of this task',
            'assigned_to': 'Choose team member responsible for this task'
        }
        
        error_messages = {
            'title': {
                'required': 'Please enter a task title',
                'max_length': 'Title is too long (maximum 200 characters)'
            },
            'due_date': {
                'invalid': 'Please enter a valid date'
            }
        }

    def __init__(self, *args, **kwargs):
        self.project = kwargs.pop('project', None)
        super().__init__(*args, **kwargs)
        
        # Common attributes for all fields
        for field_name, field in self.fields.items():
            # Add form-control class but preserve existing classes
            existing_class = field.widget.attrs.get('class', '')
            if 'form-select' not in existing_class:  # Don't add form-control to select fields
                classes = ['form-control']
                if existing_class:
                    classes.append(existing_class)
                field.widget.attrs['class'] = ' '.join(classes)

            # Add custom styling
            field.widget.attrs.update({
                'data-field': field_name,  # For custom JS targeting
            })

        # Customize specific fields
        self.fields['title'].widget.attrs.update({
            'autofocus': True,
            'maxlength': 200
        })

        self.fields['description'].widget.attrs.update({
            'maxlength': 2000,
            'data-auto-resize': 'true'  # For auto-resizing textarea
        })

        # Filter assigned_to to only include project members
        if self.project:
            self.fields['assigned_to'].queryset = self.project.members.all()
            self.fields['assigned_to'].empty_label = "-- Select Assignee --"

        # Status field customization
        self.fields['status'].widget.attrs.update({
            'data-status-field': 'true'  # For custom status handling
        })

        # Priority field customization
        self.fields['priority'].widget.attrs.update({
            'data-priority-field': 'true'  # For custom priority handling
        })

        # Add custom classes for styling
        self.fields['priority'].widget.attrs['class'] += ' priority-select'
        self.fields['status'].widget.attrs['class'] += ' status-select'
        self.fields['assigned_to'].widget.attrs['class'] += ' assignee-select'

    def clean_due_date(self):
        """Validate that due date is not in the past"""
        due_date = self.cleaned_data.get('due_date')
        if due_date and due_date < timezone.now().date():
            raise forms.ValidationError("Due date cannot be in the past")
        return due_date

    def clean(self):
        """Custom form validation"""
        cleaned_data = super().clean()
        status = cleaned_data.get('status')
        assigned_to = cleaned_data.get('assigned_to')

        # If status is completed, ensure there's an assignee
        if status == 'completed' and not assigned_to:
            self.add_error('assigned_to', 'Completed tasks must have an assignee')

        return cleaned_data

    class Media:
        css = {
            'all': (
                # Add any additional CSS files here
            )
        }
        js = (
            # Add any additional JS files here
        )


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