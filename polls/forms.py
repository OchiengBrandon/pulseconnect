from django import forms
from django.utils.translation import gettext_lazy as _
from django.forms import inlineformset_factory
from .models import Poll, PollComment, Question, Choice, PollResponse, PollTemplate, QuestionType, PollCategory
import json

class PollForm(forms.ModelForm):
    class Meta:
        model = Poll
        fields = ['title', 'description', 'category', 'poll_type', 'start_date', 
                 'end_date', 'allow_comments', 'allow_sharing', 'restricted_to_institution', 'tags']
        widgets = {
            'start_date': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'end_date': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'description': forms.Textarea(attrs={'rows': 4}),
        }
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        for field_name in self.fields:
            self.fields[field_name].widget.attrs.update({'class': 'form-control'})
        
        # Only show restricted_to_institution field for institution-specific polls
        self.fields['restricted_to_institution'].widget.attrs.update({'class': 'form-control d-none'})
        self.fields['restricted_to_institution'].required = False
        
        # For the tags field
        self.fields['tags'].widget.attrs.update({'class': 'form-control select2-tags'})
    
    def clean(self):
        cleaned_data = super().clean()
        poll_type = cleaned_data.get('poll_type')
        restricted_to = cleaned_data.get('restricted_to_institution')
        
        if poll_type == 'institution' and not restricted_to:
            self.add_error('restricted_to_institution', _('This field is required for institution-specific polls.'))
        
        return cleaned_data


class QuestionForm(forms.ModelForm):
    class Meta:
        model = Question
        fields = ['text', 'question_type', 'is_required', 'order', 
                 'min_value', 'max_value', 'step_value', 'settings']
        widgets = {
            'text': forms.Textarea(attrs={'rows': 3}),
            'settings': forms.HiddenInput(),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name in self.fields:
            self.fields[field_name].widget.attrs.update({'class': 'form-control'})
        
        self.fields['is_required'].widget = forms.CheckboxInput(attrs={'class': 'form-check-input'})
        
        # Hide fields that are only relevant for specific question types
        self.fields['min_value'].widget.attrs.update({'class': 'form-control numeric-field d-none'})
        self.fields['max_value'].widget.attrs.update({'class': 'form-control numeric-field d-none'})
        self.fields['step_value'].widget.attrs.update({'class': 'form-control numeric-field d-none'})


class ChoiceForm(forms.ModelForm):
    class Meta:
        model = Choice
        fields = ['text', 'order']
    
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


class PollResponseForm(forms.Form):
    """Dynamic form for responding to polls"""
    
    def __init__(self, *args, **kwargs):
        self.poll = kwargs.pop('poll')
        self.user = kwargs.pop('user')
        super().__init__(*args, **kwargs)
        
        # Get all questions for this poll
        questions = Question.objects.filter(poll=self.poll).order_by('order')
        
        for question in questions:
            question_type = question.question_type.slug
            field_name = f'question_{question.id}'
            
            if question_type == 'single_choice':
                choices = [(choice.id, choice.text) for choice in question.choices.all()]
                self.fields[field_name] = forms.ChoiceField(
                    label=question.text,
                    choices=choices,
                    required=question.is_required,
                    widget=forms.RadioSelect(attrs={'class': 'form-check-input'})
                )
            
            elif question_type == 'multiple_choice':
                choices = [(choice.id, choice.text) for choice in question.choices.all()]
                self.fields[field_name] = forms.MultipleChoiceField(
                    label=question.text,
                    choices=choices,
                    required=question.is_required,
                    widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'})
                )
            
            elif question_type == 'open_ended':
                self.fields[field_name] = forms.CharField(
                    label=question.text,
                    required=question.is_required,
                    widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3})
                )
            
            elif question_type == 'rating':
                min_val = question.min_value or 1
                max_val = question.max_value or 5
                choices = [(i, str(i)) for i in range(min_val, max_val + 1)]
                self.fields[field_name] = forms.ChoiceField(
                    label=question.text,
                    choices=choices,
                    required=question.is_required,
                    widget=forms.RadioSelect(attrs={'class': 'rating-input'})
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
                    required=question.is_required,
                    widget=forms.RadioSelect(attrs={'class': 'likert-input'})
                )
    
    def save(self):
        """Save the poll responses"""
        for field_name, value in self.cleaned_data.items():
            if field_name.startswith('question_'):
                question_id = int(field_name.split('_')[1])
                question = Question.objects.get(id=question_id)
                
                # Convert value to string for storage
                if isinstance(value, list):
                    response_data = json.dumps(value)
                else:
                    response_data = str(value)
                
                # Create or update response
                PollResponse.objects.update_or_create(
                    question=question,
                    user=self.user,
                    defaults={'response_data': response_data}
                )
        
        # Award points for participation
        from gamification.models import award_points
        award_points(self.user, 'poll_participation', self.poll)


class PollTemplateForm(forms.ModelForm):
    class Meta:
        model = PollTemplate
        fields = ['title', 'description', 'category', 'is_public', 'template_data']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
            'template_data': forms.HiddenInput(),
        }
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        for field_name in self.fields:
            self.fields[field_name].widget.attrs.update({'class': 'form-control'})
        
        self.fields['is_public'].widget = forms.CheckboxInput(attrs={'class': 'form-check-input'})


class PollCategoryForm(forms.ModelForm):
    class Meta:
        model = PollCategory
        fields = ['name', 'description', 'icon']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name in self.fields:
            self.fields[field_name].widget.attrs.update({'class': 'form-control'})


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
            
class PollCommentForm(forms.ModelForm):
    class Meta:
        model = PollComment
        fields = ['content']
        widgets = {
            'content': forms.Textarea(attrs={
                'rows': 3,
                'class': 'form-control',
                'placeholder': _('Write your comment...')
            })
        }