from django import forms
from django.utils.translation import gettext_lazy as _

from .models import CalendarPreference

class CalendarPreferenceForm(forms.ModelForm):
    """Form for updating calendar preferences"""
    class Meta:
        model = CalendarPreference
        fields = [
            'show_community_events', 
            'show_volunteer_opportunities', 
            'show_polls',
            'event_color', 
            'opportunity_color', 
            'poll_color',
            'notify_upcoming_events', 
            'notify_days_before'
        ]
        widgets = {
            'event_color': forms.TextInput(attrs={'type': 'color'}),
            'opportunity_color': forms.TextInput(attrs={'type': 'color'}),
            'poll_color': forms.TextInput(attrs={'type': 'color'}),
        }