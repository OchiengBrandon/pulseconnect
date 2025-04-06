from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class CalendarViewConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'calendar_view'
    verbose_name = _('Calendar')
    
    def ready(self):
        # Import signals when app is ready
        pass