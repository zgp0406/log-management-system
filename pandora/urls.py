"""
URL configuration for pandora project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView
from django.http import JsonResponse
import json

def manifest_view(request):
    """返回 PWA manifest JSON"""
    # 使用在线占位图标（临时方案，后续可替换为实际图标）
    manifest = {
        "name": "Pandora 工作平台",
        "short_name": "Pandora",
        "start_url": "/m/",
        "scope": "/",
        "display": "standalone",
        "background_color": "#ffffff",
        "theme_color": "#0d6efd",
        "orientation": "portrait",
        "icons": [
            {"src": "https://via.placeholder.com/192.png/0d6efd/ffffff?text=P", "sizes": "192x192", "type": "image/png", "purpose": "any maskable"},
            {"src": "https://via.placeholder.com/512.png/0d6efd/ffffff?text=P", "sizes": "512x512", "type": "image/png", "purpose": "any maskable"}
        ]
    }
    return JsonResponse(manifest, json_dumps_params={'ensure_ascii': False})

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', RedirectView.as_view(url='/login_app/login_page/', permanent=False)),
    path('static/manifest.webmanifest', manifest_view, name='manifest'),
    path('manifest.json', manifest_view, name='manifest_json'),
    path('', include('dashboard.urls')),
    path('', include('task_app.urls')),
    path('', include('log_app.urls')),
    path('', include('ai_app.urls')),
    path('login_app/', include('login_app.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
