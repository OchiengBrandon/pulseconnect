# accessibility/middleware.py

from django.utils.deprecation import MiddlewareMixin
from accessibility.models import AccessibilitySetting

class AccessibilityMiddleware(MiddlewareMixin):
    def process_request(self, request):
        # Check if the user is authenticated
        if request.user.is_authenticated:
            # Get user's accessibility settings
            try:
                settings = request.user.accessibilitysetting
                # Add accessibility settings to the request
                request.high_contrast_mode = settings.high_contrast_mode
                request.text_size = settings.text_size
            except AccessibilitySetting.DoesNotExist:
                # Default settings if not found
                request.high_contrast_mode = False
                request.text_size = 'medium'
        else:
            # Default settings for unauthenticated users
            request.high_contrast_mode = False
            request.text_size = 'medium'

    def process_response(self, request, response):
        # Add a class to the body tag based on accessibility settings
        if request.high_contrast_mode:
            response.setdefault('Content-Security-Policy', "default-src 'self'")
            response['HTML-Class'] = 'high-contrast'
        else:
            response['HTML-Class'] = 'normal'

        return response