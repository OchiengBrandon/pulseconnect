from django.urls import path
from . import views

app_name = 'notifications'  

urlpatterns = [
    # Main list view
    path('', views.NotificationListView.as_view(), name='list'),
    
    # Detail view
    path('<int:pk>/', views.notification_detail, name='detail'),
    
    # Actions for individual notifications
    path('<int:pk>/mark-read/', views.mark_notification_read, name='mark_read'),
    path('<int:pk>/delete/', views.delete_notification, name='delete'),
    
    # Bulk actions
    path('mark-all-read/', views.mark_all_notifications_read, name='mark_all_read'),
    
    # Preferences
    path('preferences/', views.NotificationPreferenceView.as_view(), name='preferences'),
    
    # JSON endpoints for AJAX
    path('api/recent/', views.get_notifications_json, name='recent_json'),
]