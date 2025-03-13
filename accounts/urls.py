from django.urls import path
from django.contrib.auth.views import LogoutView
from . import views

app_name = 'accounts'

urlpatterns = [
    path('signup/', views.SignUpView.as_view(), name='signup'),
    path('login/', views.CustomLoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('verify/<str:token>/', views.verify_email, name='verify'),
    path('verification-sent/', views.verification_sent, name='verification_sent'),
    path('profile/<str:username>/', views.ProfileDetailView.as_view(), name='profile'),
    path('profile/edit/', views.ProfileUpdateView.as_view(), name='profile_edit'),
    path('follow/<str:username>/', views.follow_user, name='follow'),
    path('password-change/', views.CustomPasswordChangeView.as_view(), name='password_change'),
    path('password-change/done/', views.password_change_done, name='password_change_done'),
    path('researchers/', views.ResearcherDirectoryView.as_view(), name='researcher_directory'),
    path('institutions/', views.InstitutionDirectoryView.as_view(), name='institution_directory'),
    path('accessibility/toggle/', views.toggle_accessibility_setting, name='toggle_accessibility'),
]