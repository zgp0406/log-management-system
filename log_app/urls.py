from django.urls import path
from . import views
from . import api_views

app_name = 'log_app'

urlpatterns = [
    path('logs/api/', api_views.logs_api, name='logs_api'),
    path('logs/api/tags/', api_views.tags_api, name='logs_tags_api'),
    path('logs/api/create/', api_views.log_create_api, name='logs_create_api'),
    path('logs/api/<int:log_id>/update/', api_views.log_update_api, name='logs_update_api'),
    path('logs/api/<int:log_id>/delete/', api_views.log_delete_api, name='logs_delete_api'),
    path('logs/api/amap/ip/', api_views.amap_ip_proxy, name='amap_ip_proxy'),
    path('logs/api/amap/regeo/', api_views.amap_regeo_proxy, name='amap_regeo_proxy'),
    path('m/logs/', views.mobile_log_page, name='mobile_log_page'),
    path('logs/', views.log_page, name='log_page'),
    path('logs/<int:log_id>/', views.log_detail, name='log_detail'),
    path('logs/<int:log_id>/delete/', views.log_delete, name='log_delete'),
    path('logs/<int:log_id>/update/', views.log_update, name='log_update'),
]
