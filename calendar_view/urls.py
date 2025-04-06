from django.urls import path
from . import views

app_name = 'calendar_view'

urlpatterns = [
    path('', views.CalendarView.as_view(), name='calendar'),
    path('events/', views.get_calendar_events, name='calendar_events'),
    path('preferences/', views.CalendarPreferenceView.as_view(), name='preferences'),
    path('event/<int:event_id>/toggle-attendance/', views.add_event_to_calendar, name='toggle_attendance'),
]