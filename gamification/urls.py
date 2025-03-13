# URLs (gamification/urls.py)
from django.urls import path
from . import views

app_name = 'gamification'

urlpatterns = [
    path('', views.RewardsHomeView.as_view(), name='rewards_home'),
    path('leaderboard/', views.LeaderboardView.as_view(), name='leaderboard'),
    path('badges/', views.BadgeListView.as_view(), name='badge_list'),
    path('badges/<int:pk>/', views.BadgeDetailView.as_view(), name='badge_detail'),
    path('points/history/', views.UserPointsHistoryView.as_view(), name='points_history'),
    path('my-badges/', views.UserBadgesView.as_view(), name='user_badges'),
    path('api/points/', views.get_user_points, name='api_points'),
]