# accessibility/context_processors.py

from .models import AccessibilitySetting

def accessibility_settings(request):
    if request.user.is_authenticated:
        try:
            settings = request.user.accessibilitysetting
            return {
                'high_contrast_mode': settings.high_contrast_mode,
                'text_size': settings.text_size,
            }
        except AccessibilitySetting.DoesNotExist:
            return {
                'high_contrast_mode': False,
                'text_size': 'medium',
            }
    else:
        return {
            'high_contrast_mode': False,
            'text_size': 'medium',
        }