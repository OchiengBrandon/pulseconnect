from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm, PasswordChangeForm
from django.utils.translation import gettext_lazy as _
from .models import User, InstitutionProfile

class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(required=True)
    user_type = forms.ChoiceField(choices=User.USER_TYPE_CHOICES)
    
    class Meta:
        model = User
        fields = ('username', 'email', 'user_type', 'password1', 'password2')
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name in self.fields:
            self.fields[field_name].widget.attrs.update({'class': 'form-control'})
    
    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.user_type = self.cleaned_data['user_type']
        if commit:
            user.save()
        return user

# Add this to your forms.py file
from allauth.socialaccount.forms import SignupForm as AllauthSignupForm

class SocialSignupForm(AllauthSignupForm):
    user_type = forms.ChoiceField(
        choices=User.USER_TYPE_CHOICES,
        label=_('User Type'),
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    def save(self, request):
        # The actual save happens in the view
        user = super(SocialSignupForm, self).save(request)
        return user
    
class CustomAuthenticationForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name in self.fields:
            self.fields[field_name].widget.attrs.update({'class': 'form-control'})


class UserProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'email', 'bio', 'profile_picture', 'institution', 
                 'field_of_study', 'location', 'website', 'social_linkedin', 
                 'social_twitter', 'social_github', 'email_notifications', 
                 'poll_notifications', 'comment_notifications', 'public_profile', 'show_email')
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name in self.fields:
            self.fields[field_name].widget.attrs.update({'class': 'form-control'})
        
        # Set boolean fields to use checkboxes
        for field_name in ('email_notifications', 'poll_notifications', 'comment_notifications', 
                          'public_profile', 'show_email'):
            self.fields[field_name].widget = forms.CheckboxInput(attrs={'class': 'form-check-input'})


class InstitutionProfileForm(forms.ModelForm):
    class Meta:
        model = InstitutionProfile
        fields = ('institution_name', 'institution_type', 'address', 'phone', 
                 'established_year', 'description', 'logo')
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name in self.fields:
            self.fields[field_name].widget.attrs.update({'class': 'form-control'})


class AccessibilitySettingsForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ('high_contrast', 'large_text')
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name in self.fields:
            self.fields[field_name].widget = forms.CheckboxInput(attrs={'class': 'form-check-input'})