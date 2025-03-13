from django.urls import path
from . import views

app_name = 'community'

urlpatterns = [
    # Dashboard
    path('', views.CommunityDashboardView.as_view(), name='dashboard'),
    
    # Discussions
    path('discussions/', views.DiscussionListView.as_view(), name='discussion_list'),
    path('discussions/create/', views.DiscussionCreateView.as_view(), name='discussion_create'),
    path('discussions/<slug:slug>/', views.DiscussionDetailView.as_view(), name='discussion_detail'),
    path('discussions/<slug:slug>/update/', views.DiscussionUpdateView.as_view(), name='discussion_update'),
    path('discussions/<slug:slug>/delete/', views.DiscussionDeleteView.as_view(), name='discussion_delete'),
    
    # Comments
    path('comments/add/<int:content_type_id>/<int:object_id>/', views.add_comment, name='add_comment'),
    path('comments/<int:comment_id>/delete/', views.delete_comment, name='delete_comment'),
    
    # Events
    path('events/', views.EventListView.as_view(), name='event_list'),
    path('events/create/', views.EventCreateView.as_view(), name='event_create'),
    path('events/<slug:slug>/', views.EventDetailView.as_view(), name='event_detail'),
    path('events/<slug:slug>/update/', views.EventUpdateView.as_view(), name='event_update'),
    path('events/<slug:slug>/delete/', views.EventDeleteView.as_view(), name='event_delete'),
    path('events/<int:pk>/attend/', views.toggle_event_attendance, name='toggle_attendance'),
    
    # Volunteer opportunities
    path('opportunities/', views.VolunteerOpportunityListView.as_view(), name='opportunity_list'),
    path('opportunities/create/', views.VolunteerOpportunityCreateView.as_view(), name='opportunity_create'),
    path('opportunities/<slug:slug>/', views.VolunteerOpportunityDetailView.as_view(), name='opportunity_detail'),
    path('opportunities/<slug:slug>/update/', views.VolunteerOpportunityUpdateView.as_view(), name='opportunity_update'),
    path('opportunities/<slug:slug>/delete/', views.VolunteerOpportunityDeleteView.as_view(), name='opportunity_delete'),
    path('opportunities/<int:pk>/interest/', views.toggle_opportunity_interest, name='toggle_interest'),
    
    # Impact reports
    path('impacts/', views.ImpactListView.as_view(), name='impact_list'),
    path('impacts/create/', views.ImpactCreateView.as_view(), name='impact_create'),
    path('impacts/<int:pk>/', views.ImpactDetailView.as_view(), name='impact_detail'),
    path('impacts/<int:pk>/verify/', views.verify_impact, name='verify_impact'),
]