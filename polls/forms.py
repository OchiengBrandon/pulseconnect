from django import forms
from django.utils.translation import gettext_lazy as _
from django.forms import inlineformset_factory
from taggit.forms import TagField
import json
from django.db import transaction

from accounts.models import InstitutionProfile

from .models import (
    Poll, 
    PollCategory, 
    Question, 
    Choice, 
    PollComment, 
    QuestionType,
    PollTemplate,
    PollResponse
)

class PollCategoryForm(forms.ModelForm):
    class Meta:
        model = PollCategory
        fields = ['name', 'description', 'icon']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
        }




class PollForm(forms.ModelForm):
    tags = TagField(required=False, help_text=_("Comma-separated tags (e.g., education, research, feedback)"))

    class Meta:
        model = Poll
        fields = [
            'title', 'description', 'category', 'poll_type', 
            'status', 'start_date', 'end_date', 'is_featured',
            'allow_comments', 'allow_sharing', 'restricted_to_institution',
            'tags'
        ]
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': _('Enter poll title')}),
            'description': forms.Textarea(attrs={
                'rows': 4, 
                'class': 'form-control', 
                'placeholder': _('Describe the purpose of your poll')
            }),
            'start_date': forms.DateTimeInput(attrs={
                'type': 'datetime-local',
                'class': 'form-control'
            }),
            'end_date': forms.DateTimeInput(attrs={
                'type': 'datetime-local',
                'class': 'form-control'
            }),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'poll_type': forms.Select(attrs={'class': 'form-select'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'restricted_to_institution': forms.Select(attrs={'class': 'form-select'}),
        }
        help_texts = {
            'title': _('Choose a clear, concise title for your poll'),
            'poll_type': _('Public polls are visible to everyone, while institution polls are restricted'),
            'status': _('Draft polls are only visible to you until published'),
            'start_date': _('When the poll will become available (leave blank for immediate availability)'),
            'end_date': _('When the poll will close (leave blank to keep it open indefinitely)'),
        }
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('creator', None)
        super().__init__(*args, **kwargs)

        # Style all fields with Bootstrap classes
        for field_name, field in self.fields.items():
            if 'class' not in field.widget.attrs:
                field.widget.attrs['class'] = 'form-control'
            
            # Ensure select fields use the correct class
            if isinstance(field.widget, forms.Select):
                field.widget.attrs['class'] = 'form-select'

        # Make description optional
        self.fields['description'].required = False
        
        # Default values
        if not self.instance.pk:  # New poll
            self.fields['status'].initial = 'draft'
            self.fields['poll_type'].initial = 'public'
            self.fields['allow_comments'].initial = True
            self.fields['allow_sharing'].initial = True

        # Populate the restricted_to_institution field with institutions
        self.fields['restricted_to_institution'].queryset = InstitutionProfile.objects.all()
        self.fields['restricted_to_institution'].widget.attrs['data-show-if-poll-type'] = 'institution'

        # Autofill the restricted_to_institution if the user is associated with one
        if self.user:
            try:
                institution = InstitutionProfile.objects.get(user=self.user)
                self.initial['restricted_to_institution'] = institution.pk
            except InstitutionProfile.DoesNotExist:
                pass

    def clean(self):
        cleaned_data = super().clean()
        
        # Ensure the status field is valid
        status = cleaned_data.get('status')
        if not status:
            self.add_error('status', _("Please select a valid status."))
            
        # Additional cross-field validations can be added here
        
        return cleaned_data

class QuestionForm(forms.ModelForm):
    class Meta:
        model = Question
        fields = [
            'text', 'question_type', 'is_required', 'order',
            'min_value', 'max_value', 'step_value', 'settings'
        ]
        widgets = {
            'text': forms.Textarea(attrs={
                'rows': 3, 
                'class': 'form-control question-text',
                'placeholder': _('Enter your question text here')
            }),
            'settings': forms.Textarea(attrs={
                'rows': 3, 
                'class': 'form-control json-settings', 
                'placeholder': '{"custom_setting": "value"}'
            }),
            'order': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'min_value': forms.NumberInput(attrs={'class': 'form-control'}),
            'max_value': forms.NumberInput(attrs={'class': 'form-control'}),
            'step_value': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1'}),
        }
        help_texts = {
            'text': _('Enter the question you want to ask'),
            'question_type': _('Select the type of response you want to collect'),
            'is_required': _('Should respondents be required to answer this question?'),
            'min_value': _('For rating/slider questions: the minimum value'),
            'max_value': _('For rating/slider questions: the maximum value'),
            'step_value': _('For slider questions: the increment between values'),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Make these fields optional by default, they'll be required conditionally via JS
        self.fields['min_value'].required = False
        self.fields['max_value'].required = False
        self.fields['step_value'].required = False
        self.fields['settings'].required = False
        
        # Default order if not provided
        if not self.instance.pk and not self.initial.get('order'):
            self.initial['order'] = 1
        
        # Add data attributes for JS to know which fields to show for each question type
        self.fields['min_value'].widget.attrs['data-show-for-types'] = 'rating,slider'
        self.fields['max_value'].widget.attrs['data-show-for-types'] = 'rating,slider'
        self.fields['step_value'].widget.attrs['data-show-for-types'] = 'slider'
        self.fields['settings'].widget.attrs['data-show-for-types'] = 'open_ended,multiple_choice,likert'


class ChoiceForm(forms.ModelForm):
    class Meta:
        model = Choice
        fields = ['text', 'order']
        widgets = {
            'text': forms.TextInput(attrs={
                'class': 'form-control choice-text',
                'placeholder': _('Enter choice text')
            }),
            'order': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
        }


# Create a formset for handling multiple choices per question
ChoiceFormSet = inlineformset_factory(
    Question, 
    Choice,
    form=ChoiceForm,
    extra=3,
    can_delete=True,
    min_num=2,
    validate_min=True
)


class PollCommentForm(forms.ModelForm):
    class Meta:
        model = PollComment
        fields = ['content']
        widgets = {
            'content': forms.Textarea(attrs={'rows': 3, 'placeholder': _('Add your comment...')}),
        }
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        self.poll = kwargs.pop('poll', None)
        super().__init__(*args, **kwargs)
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.user:
            instance.user = self.user
        if self.poll:
            instance.poll = self.poll
        if commit:
            instance.save()
        return instance



class PollResponseForm(forms.Form):
    def __init__(self, *args, **kwargs):
        self.poll = kwargs.pop('poll')
        self.user = kwargs.pop('user')
        super().__init__(*args, **kwargs)

        # Get all questions for this poll, respecting the order specified during creation
        questions = self.poll.questions.all().order_by('order')
        
        for question in questions:
            field_name = f'question_{question.id}'
            question_type = question.question_type.slug
            
            # Parse any custom settings defined during poll creation
            settings = {}
            if question.settings:
                try:
                    settings = json.loads(question.settings)
                except json.JSONDecodeError:
                    pass
            
            # Apply any field-level settings from the question settings
            field_attrs = {
                'class': f'question-field question-type-{question_type}',
                'data-question-id': question.id
            }
            
            # Handle each question type according to how it was defined in creation
            if question_type == 'single_choice':
                choices = [(choice.id, choice.text) for choice in question.choices.all().order_by('order')]
                self.fields[field_name] = forms.ChoiceField(
                    label=question.text,
                    choices=choices,
                    widget=forms.RadioSelect(attrs=field_attrs),
                    required=question.is_required,
                    help_text=settings.get('help_text', '')
                )
            
            elif question_type == 'multiple_choice':
                choices = [(choice.id, choice.text) for choice in question.choices.all().order_by('order')]
                self.fields[field_name] = forms.MultipleChoiceField(
                    label=question.text,
                    choices=choices,
                    widget=forms.CheckboxSelectMultiple(attrs=field_attrs),
                    required=question.is_required,
                    help_text=settings.get('help_text', '')
                )
            
            elif question_type == 'open_ended' or question_type == 'short_answer':
                # Apply any specific settings for open-ended questions
                rows = settings.get('rows', 3)
                placeholder = settings.get('placeholder', '')
                max_length = settings.get('max_length', None)
                
                widget_attrs = field_attrs.copy()
                widget_attrs.update({
                    'rows': rows,
                    'placeholder': placeholder,
                    'class': f"{field_attrs.get('class', '')} form-control"
                })
                
                widget = forms.Textarea if question_type == 'open_ended' else forms.TextInput
                
                self.fields[field_name] = forms.CharField(
                    label=question.text,
                    widget=widget(attrs=widget_attrs),
                    required=question.is_required,
                    max_length=max_length,
                    help_text=settings.get('help_text', '')
                )
            
            elif question_type == 'essay':
                # Apply any specific settings for essay questions
                rows = settings.get('rows', 6)
                placeholder = settings.get('placeholder', '')
                max_length = settings.get('max_length', None)
                
                widget_attrs = field_attrs.copy()
                widget_attrs.update({
                    'rows': rows,
                    'placeholder': placeholder,
                    'class': f"{field_attrs.get('class', '')} form-control"
                })
                
                self.fields[field_name] = forms.CharField(
                    label=question.text,
                    widget=forms.Textarea(attrs=widget_attrs),
                    required=question.is_required,
                    max_length=max_length,
                    help_text=settings.get('help_text', '')
                )
            
            elif question_type == 'rating_scale':
                # Use min_value and max_value as defined in question creation
                min_val = question.min_value if question.min_value is not None else 1
                max_val = question.max_value if question.max_value is not None else 5
                
                choices = [(i, str(i)) for i in range(min_val, max_val + 1)]
                
                widget_attrs = field_attrs.copy()
                widget_attrs['class'] = f"{field_attrs.get('class', '')} rating-select"
                
                self.fields[field_name] = forms.ChoiceField(
                    label=question.text,
                    choices=choices,
                    widget=forms.RadioSelect(attrs=widget_attrs),
                    required=question.is_required,
                    help_text=settings.get('help_text', '')
                )
            
            elif question_type == 'likert_scale':
                # Use choices defined during creation
                choices = [(choice.id, choice.text) for choice in question.choices.all().order_by('order')]
                
                # If no custom choices were created, use the default ones created in PollCreateView
                if not choices:
                    choices = [
                        (1, _('Strongly Disagree')),
                        (2, _('Disagree')),
                        (3, _('Neutral')),
                        (4, _('Agree')),
                        (5, _('Strongly Agree'))
                    ]
                
                self.fields[field_name] = forms.ChoiceField(
                    label=question.text,
                    choices=choices,
                    widget=forms.RadioSelect(attrs=field_attrs),
                    required=question.is_required,
                    help_text=settings.get('help_text', '')
                )
            
            elif question_type == 'true_false':
                # True/False questions use the choices created in PollCreateView
                choices = [(choice.id, choice.text) for choice in question.choices.all().order_by('order')]
                
                self.fields[field_name] = forms.ChoiceField(
                    label=question.text,
                    choices=choices,
                    widget=forms.RadioSelect(attrs=field_attrs),
                    required=question.is_required,
                    help_text=settings.get('help_text', '')
                )
            
            # Add support for any other question types defined in QuestionType model
            else:
                # Generic fallback for custom question types
                self.fields[field_name] = forms.CharField(
                    label=question.text,
                    required=question.is_required,
                    help_text=f"Question type '{question_type}' may not be fully supported"
                )

    def save(self):
        """Save user responses to all questions in this poll."""
        if not self.is_valid():
            raise ValueError("Form must be valid before saving")
        
        saved_responses = []
        
        # Begin a transaction to ensure all responses are saved atomically
        with transaction.atomic():
            for field_name, response_value in self.cleaned_data.items():
                if field_name.startswith('question_'):
                    question_id = int(field_name.split('_')[1])
                    
                    try:
                        question = Question.objects.get(id=question_id)
                    except Question.DoesNotExist:
                        continue  # Skip if question was deleted
                    
                    # Format response data based on question type
                    question_type = question.question_type.slug
                    
                    if question_type == 'multiple_choice':
                        # For multiple choice, store as JSON array
                        response_data = json.dumps(list(response_value))
                    elif question_type in ['rating_scale', 'likert_scale']:
                        # Store numeric values as numbers, not strings
                        try:
                            response_data = float(response_value)
                        except (ValueError, TypeError):
                            response_data = str(response_value)
                    else:
                        # For other types, store as string
                        response_data = str(response_value)
                    
                    # Create or update the response - don't include poll directly
                    response, created = PollResponse.objects.update_or_create(
                        question=question,
                        user=self.user,
                        defaults={'response_data': response_data}
                    )
                    
                    saved_responses.append(response)
        
        return saved_responses

class PollTemplateForm(forms.ModelForm):
    class Meta:
        model = PollTemplate
        fields = ['title', 'description', 'category', 'is_public', 'template_data']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'template_data': forms.Textarea(attrs={'rows': 5, 'class': 'json-editor'}),
        }
    
    def __init__(self, *args, **kwargs):
        self.creator = kwargs.pop('creator', None)
        super().__init__(*args, **kwargs)
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.creator and not instance.pk:
            instance.creator = self.creator
        if commit:
            instance.save()
        return instance


class PollSearchForm(forms.Form):
    """Form for searching and filtering polls"""
    query = forms.CharField(
        required=False, 
        label=_('Search'),
        widget=forms.TextInput(attrs={'placeholder': _('Search polls...')})
    )
    category = forms.ModelChoiceField(
        required=False,
        label=_('Category'),
        queryset=PollCategory.objects.all(),
        empty_label=_('All Categories')
    )
    status = forms.ChoiceField(
        required=False,
        label=_('Status'),
        choices=[('', _('All Statuses'))] + list(Poll.POLL_STATUS_CHOICES)
    )
    poll_type = forms.ChoiceField(
        required=False,
        label=_('Type'),
        choices=[('', _('All Types'))] + list(Poll.POLL_TYPE_CHOICES)
    )
    date_from = forms.DateField(
        required=False,
        label=_('From'),
        widget=forms.DateInput(attrs={'type': 'date'})
    )
    date_to = forms.DateField(
        required=False,
        label=_('To'),
        widget=forms.DateInput(attrs={'type': 'date'})
    )
    tags = forms.CharField(
        required=False,
        label=_('Tags'),
        widget=forms.TextInput(attrs={'placeholder': _('Enter tags...')})
    )

class QuestionTypeForm(forms.ModelForm):
    class Meta:
        model = QuestionType
        fields = ['name', 'description']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name in self.fields:
            self.fields[field_name].widget.attrs.update({'class': 'form-control'})


# Create formsets for questions and choices
QuestionFormSet = inlineformset_factory(
    Poll, Question, 
    form=QuestionForm, 
    extra=1, 
    can_delete=True
)

ChoiceFormSet = inlineformset_factory(
    Question, Choice, 
    form=ChoiceForm, 
    extra=3, 
    can_delete=True
)