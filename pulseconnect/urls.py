from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', TemplateView.as_view(template_name="home.html"), name='home'),
    path('accounts/', include('accounts.urls')),  # Custom accounts URLs
    path('accounts/', include('allauth.urls')),  # Django Allauth URLs for authentication
    path('polls/', include('polls.urls')),
    path('analytics/', include('analytics.urls')),
    path('calendar/', include('calendar_view.urls')),
    path('community/', include('community.urls')),
    path('collaborate/', include('collaboration.urls')),
    path('rewards/', include('gamification.urls')),
    # path('api/', include('api.urls')),
    path('dashboard/', TemplateView.as_view(template_name="home.html"), name='dashboard'),
    path('ckeditor/', include('ckeditor_uploader.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)