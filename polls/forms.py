from django import forms
from django.utils.translation import gettext_lazy as _
from django.forms import inlineformset_factory
from taggit.forms import TagField
import json

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
    tags = TagField(required=False, help_text=_("Comma-separated tags"))

    class Meta:
        model = Poll
        fields = [
            'title', 'description', 'category', 'poll_type', 
            'status', 'start_date', 'end_date', 'is_featured',
            'allow_comments', 'allow_sharing', 'restricted_to_institution',
            'tags'
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
            'start_date': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'end_date': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        }
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('creator', None)  # Change 'creator' to 'user' here
        super().__init__(*args, **kwargs)

        # Populate the restricted_to_institution field with institutions
        self.fields['restricted_to_institution'].queryset = InstitutionProfile.objects.all()

        # Conditionally show/hide restricted_to_institution based on poll_type
        self.fields['restricted_to_institution'].widget.attrs['data-show-if-poll-type'] = 'institution'

        # Autofill the restricted_to_institution if the user is associated with one
        if self.user:
            try:
                institution = InstitutionProfile.objects.get(user=self.user)
                self.initial['restricted_to_institution'] = institution.pk  # Autofill if applicable
            except InstitutionProfile.DoesNotExist:
                pass  # User does not have an associated InstitutionProfile
    
    def clean(self):
        cleaned_data = super().clean()
        poll_type = cleaned_data.get('poll_type')
        restricted_to_institution = cleaned_data.get('restricted_to_institution')
        
        if poll_type == 'institution' and not restricted_to_institution:
            raise forms.ValidationError(
                _("Institution name is required for institution-specific polls")
            )
        
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        
        if end_date and start_date and end_date < start_date:
            raise forms.ValidationError(
                _("End date must be after start date")
            )
        
        return cleaned_data
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.user and not instance.pk:  # Only set user on new polls
            instance.creator = self.user  # Assuming 'creator' field exists
         
        if commit:
            instance.save()
            self.save_m2m()  # Required for tags
            
        return instance


class QuestionForm(forms.ModelForm):
    class Meta:
        model = Question
        fields = [
            'text', 'question_type', 'is_required', 'order',
            'min_value', 'max_value', 'step_value', 'settings'
        ]
        widgets = {
            'text': forms.Textarea(attrs={'rows': 3}),
            'settings': forms.Textarea(attrs={'rows': 3, 'class': 'json-settings'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Make these fields optional by default, they'll be required conditionally via JS
        self.fields['min_value'].required = False
        self.fields['max_value'].required = False
        self.fields['step_value'].required = False
        
        # Add data attributes for JS to know which fields to show for each question type
        self.fields['min_value'].widget.attrs['data-show-for-types'] = 'rating,slider'
        self.fields['max_value'].widget.attrs['data-show-for-types'] = 'rating,slider'
        self.fields['step_value'].widget.attrs['data-show-for-types'] = 'slider'
    
    def clean(self):
        cleaned_data = super().clean()
        question_type = cleaned_data.get('question_type')
        
        if question_type:
            # Convert ID to model instance if needed
            if isinstance(question_type, int):
                try:
                    question_type = QuestionType.objects.get(id=question_type)
                except QuestionType.DoesNotExist:
                    self.add_error('question_type', _('Invalid question type selected'))
                    return cleaned_data
            
            # Type-specific validation
            type_slug = getattr(question_type, 'slug', '')
            
            if type_slug in ['rating', 'slider']:
                min_value = cleaned_data.get('min_value')
                max_value = cleaned_data.get('max_value')
                
                if min_value is None:
                    self.add_error('min_value', _('Required for this question type'))
                
                if max_value is None:
                    self.add_error('max_value', _('Required for this question type'))
                
                if min_value is not None and max_value is not None:
                    if min_value >= max_value:
                        self.add_error('max_value', _('Maximum value must be greater than minimum value'))
                
                # For slider, ensure step is provided
                if type_slug == 'slider' and not cleaned_data.get('step_value'):
                    self.add_error('step_value', _('Required for slider questions'))
        
        return cleaned_data


class ChoiceForm(forms.ModelForm):
    class Meta:
        model = Choice
        fields = ['text', 'order']


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

        for question in self.poll.questions.all().order_by('order'):
            field_name = f'question_{question.id}'
            question_type = question.question_type.slug
            
            if question_type == 'single_choice':
                choices = [(choice.id, choice.text) for choice in question.choices.all()]
                self.fields[field_name] = forms.ChoiceField(
                    label=question.text,
                    choices=choices,
                    widget=forms.RadioSelect,
                    required=question.is_required
                )
            
            elif question_type == 'multiple_choice':
                choices = [(choice.id, choice.text) for choice in question.choices.all()]
                self.fields[field_name] = forms.MultipleChoiceField(
                    label=question.text,
                    choices=choices,
                    widget=forms.CheckboxSelectMultiple,
                    required=question.is_required
                )
            
            elif question_type == 'open_ended':
                self.fields[field_name] = forms.CharField(
                    label=question.text,
                    widget=forms.Textarea(attrs={'rows': 3}),
                    required=question.is_required
                )
            
            elif question_type == 'rating':
                choices = [(i, str(i)) for i in range(question.min_value, question.max_value + 1)]
                self.fields[field_name] = forms.ChoiceField(
                    label=question.text,
                    choices=choices,
                    widget=forms.RadioSelect(attrs={'class': 'rating-select'}),
                    required=question.is_required
                )
            
            elif question_type == 'likert':
                choices = [
                    ('strongly_disagree', _('Strongly Disagree')),
                    ('disagree', _('Disagree')),
                    ('neutral', _('Neutral')),
                    ('agree', _('Agree')),
                    ('strongly_agree', _('Strongly Agree')),
                ]
                self.fields[field_name] = forms.ChoiceField(
                    label=question.text,
                    choices=choices,
                    widget=forms.RadioSelect,
                    required=question.is_required
                )
            
            elif question_type == 'slider':
                self.fields[field_name] = forms.FloatField(
                    label=question.text,
                    min_value=question.min_value,
                    max_value=question.max_value,
                    widget=forms.NumberInput(attrs={
                        'type': 'range',
                        'step': question.step_value or 1,
                        'class': 'form-range'
                    }),
                    required=question.is_required
                )

    def save(self):
        """Save user responses to all questions in this poll."""
        if not self.is_valid():
            raise ValueError("Form must be valid before saving")
        
        saved_responses = []
        for field_name, response_value in self.cleaned_data.items():
            if field_name.startswith('question_'):
                question_id = int(field_name.split('_')[1])
                question = Question.objects.get(id=question_id)
                
                if question.question_type.slug == 'multiple_choice':
                    response_data = json.dumps(list(response_value))  # Save as JSON
                else:
                    response_data = str(response_value)
                
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