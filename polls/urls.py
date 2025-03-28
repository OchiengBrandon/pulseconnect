# polls/urls.py
from django.urls import path
from . import views

app_name = 'polls'

urlpatterns = [
    # Poll listing and detail views
    path('', views.PollListView.as_view(), name='poll_list'),
    path('poll/<slug:slug>/', views.PollDetailWithCommentsView.as_view(), name='detail'),
    path('poll/<slug:slug>/results/', views.PollResultsView.as_view(), name='results'),
    path('poll/<slug:slug>/analytics/', views.PollAnalyticsView.as_view(), name='analytics'),
    
    # Poll management
    path('create/', views.PollCreateView.as_view(), name='create'),
    path('poll/<slug:slug>/edit/', views.PollUpdateView.as_view(), name='update'),
    path('poll/<slug:slug>/delete/', views.PollDeleteView.as_view(), name='delete'),
    path('poll/<int:pk>/status/', views.change_poll_status, name='change_status'),
    path('poll/<slug:slug>/export/', views.export_poll_data, name='export_data'),
    
    # Poll responses
    path('poll/<slug:slug>/respond/', views.submit_poll_response, name='respond'),
    path('poll/<slug:slug>/comment/', views.add_comment, name='add_comment'),
    
    # User-specific views
    path('my-polls/', views.my_polls, name='my_polls'),
    path('my-responses/', views.my_responses, name='my_responses'),
    
    # Templates
    path('templates/', views.TemplateListView.as_view(), name='template_list'),
    path('poll/<slug:slug>/save-template/', views.save_as_template, name='save_template'),
    path('template/<int:pk>/create/', views.create_from_template, name='create_from_template'),
    
    # Categories
    path('categories/', views.CategoryListView.as_view(), name='category_list'),
    path('category/create/', views.create_category, name='create_category'),
    path('category/<int:pk>/edit/', views.update_category, name='update_category'),
    path('category/<int:pk>/delete/', views.delete_category, name='delete_category'),
    path('category/<slug:category_slug>/', views.PollListView.as_view(), name='category'),
    
    # Question types
    path('question-types/', views.question_types, name='question_types'),
    path('question-type/<int:pk>/delete/', views.delete_question_type, name='delete_question_type'),
]