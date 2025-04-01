from django.urls import path
from . import views

app_name = 'analytics'

urlpatterns = [
    # Dashboard
    path('', views.DashboardView.as_view(), name='dashboard'),
    
    # Datasets
    path('datasets/', views.DataSetListView.as_view(), name='dataset_list'),
    path('datasets/create/', views.DataSetCreateView.as_view(), name='dataset_create'),
    path('datasets/<uuid:uuid>/', views.DataSetDetailView.as_view(), name='dataset_detail'),
    path('datasets/<uuid:uuid>/update/', views.DataSetUpdateView.as_view(), name='dataset_update'),
    path('datasets/<uuid:uuid>/delete/', views.DataSetDeleteView.as_view(), name='dataset_delete'),
    path('datasets/<uuid:uuid>/collaborators/add/', views.add_dataset_collaborator, name='add_dataset_collaborator'),
    path('datasets/<uuid:uuid>/collaborators/<int:user_id>/remove/', views.remove_dataset_collaborator, name='remove_dataset_collaborator'),
    path('datasets/<uuid:uuid>/export/', views.export_dataset, name='export_dataset'),
    
    # Reports
    path('reports/', views.AnalysisReportListView.as_view(), name='report_list'),
    path('reports/create/', views.AnalysisReportCreateView.as_view(), name='report_create'),
    path('reports/<uuid:uuid>/', views.AnalysisReportDetailView.as_view(), name='report_detail'),
    path('reports/<uuid:uuid>/edit/', views.edit_report, name='report_edit'),
    path('reports/<uuid:uuid>/collaborators/add/', views.add_report_collaborator, name='add_report_collaborator'),
    path('reports/<uuid:uuid>/collaborators/<int:user_id>/remove/', views.remove_report_collaborator, name='remove_report_collaborator'),
    
    # Visualizations
    path('visualizations/', views.VisualizationListView.as_view(), name='visualization_list'),
    path('visualizations/create/', views.VisualizationCreateView.as_view(), name='visualization_create'),
    path('visualizations/<int:pk>/', views.VisualizationDetailView.as_view(), name='visualization_detail'),
    
    # Data import/export
    path('import/', views.data_import, name='data_import'),
    
    # Jobs
    path('jobs/', views.AnalyticsJobListView.as_view(), name='job_list'),
    path('jobs/<int:pk>/', views.job_detail, name='job_detail'),
]