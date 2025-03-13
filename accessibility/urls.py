from django.urls import path
from . import views

app_name = 'accessibility'

urlpatterns = [
    path('settings/', views.accessibility_settings, name='settings'),
]