from django.urls import path
from . import views

app_name = 'polls'

urlpatterns = [
    # Poll listing and filtering
    path('', views.PollListView.as_view(), name='list'),
    path('category/<slug:category_slug>/', views.PollListView.as_view(), name='category'),
    
    # Poll CRUD
    path('create/', views.PollCreateView.as_view(), name='create'),
    path('<slug:slug>/', views.PollDetailView.as_view(), name='detail'),
    path('<slug:slug>/update/', views.PollUpdateView.as_view(), name='update'),
    path('<slug:slug>/delete/', views.PollDeleteView.as_view(), name='delete'),
    
    # Poll responses
    path('<slug:slug>/respond/', views.submit_poll_response, name='respond'),
    path('<slug:slug>/results/', views.PollResultsView.as_view(), name='results'),
    path('<slug:slug>/analytics/', views.PollAnalyticsView.as_view(), name='analytics'),
    path('<slug:slug>/export/', views.export_poll_data, name='export'),
    
    # User polls and responses
    path('my/polls/', views.my_polls, name='my_polls'),
    path('my/responses/', views.my_responses, name='my_responses'),
    path('poll/<int:pk>/status/', views.change_poll_status, name='change_status'),
    
    # Templates
    path('templates/', views.TemplateListView.as_view(), name='template_list'),
    path('poll/<int:pk>/save-template/', views.save_as_template, name='save_as_template'),
    path('template/<int:pk>/create-poll/', views.create_from_template, name='create_from_template'),
    
    # Categories
    path('categories/', views.CategoryListView.as_view(), name='category_list'),
    path('categories/create/', views.create_category, name='create_category'),
    path('categories/<int:pk>/update/', views.update_category, name='update_category'),
    path('categories/<int:pk>/delete/', views.delete_category, name='delete_category'),
    
    # Question types
    path('question-types/', views.question_types, name='question_types'),
    path('question-types/<int:pk>/delete/', views.delete_question_type, name='delete_question_type'),
]