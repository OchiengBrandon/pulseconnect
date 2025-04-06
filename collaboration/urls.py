from django.urls import path
from . import views

app_name = 'collaboration'

urlpatterns = [
    # Projects
    path('projects/', views.ProjectListView.as_view(), name='project_list'),
    path('projects/create/', views.ProjectCreateView.as_view(), name='project_create'),
    path('projects/<int:pk>/', views.ProjectDetailView.as_view(), name='project_detail'),
    path('projects/<int:pk>/update/', views.ProjectUpdateView.as_view(), name='project_update'),
    path('projects/<int:pk>/delete/', views.ProjectDeleteView.as_view(), name='project_delete'),
    
    # Project members
    path('projects/<int:pk>/members/', views.project_members, name='project_members'),
    path('projects/<int:project_pk>/members/<int:user_pk>/update/', views.update_member_role, name='update_member_role'),
    path('projects/<int:project_pk>/members/<int:user_pk>/remove/', views.remove_member, name='remove_member'),
    path('projects/<int:pk>/leave/', views.leave_project, name='leave_project'),
    path('projects/<int:pk>/transfer-ownership/', views.transfer_ownership, name='transfer_ownership'),
    
    # Project tasks
    path('projects/<int:pk>/tasks/', views.project_tasks, name='project_tasks'),
    path('tasks/<int:task_pk>/status/', views.update_task_status, name='update_task_status'),
    path('tasks/<int:task_pk>/edit/', views.edit_task, name='edit_task'),
    path('tasks/<int:task_pk>/delete/', views.delete_task, name='delete_task'),
    
    # Project documents
    path('projects/<int:pk>/documents/', views.project_documents, name='project_documents'),
    path('documents/<int:doc_pk>/', views.view_document, name='view_document'),
    path('documents/<int:doc_pk>/edit/', views.edit_document, name='edit_document'),
    path('documents/<int:doc_pk>/delete/', views.delete_document, name='delete_document'),
    
    # Project invitations
    path('projects/<int:pk>/invitations/', views.project_invitations, name='project_invitations'),
    path('invitations/<int:invitation_pk>/cancel/', views.cancel_invitation, name='cancel_invitation'),
    path('invitations/<uuid:token>/accept/', views.accept_invitation, name='accept_invitation'),
    path('invitations/<uuid:token>/decline/', views.decline_invitation, name='decline_invitation'),
    path('invitations/', views.my_invitations, name='my_invitations'),
]