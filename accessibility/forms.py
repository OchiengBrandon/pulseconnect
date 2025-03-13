from django import forms
from .models import AccessibilitySetting

class AccessibilitySettingForm(forms.ModelForm):
    class Meta:
        model = AccessibilitySetting
        fields = ['high_contrast_mode', 'text_size']