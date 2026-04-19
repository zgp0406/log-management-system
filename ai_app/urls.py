from django.urls import path
from . import views, api_views


urlpatterns = [
    path('ai/', views.ai_dashboard_page, name='ai_dashboard'),
    path('m/ai/', views.mobile_ai_dashboard_page, name='mobile_ai_dashboard'),
    path('ai/report/view/<str:filename>/', views.weekly_report_detail, name='weekly_report_detail'),

    path('ai/api/dashboard/', api_views.ai_dashboard_api, name='ai_dashboard_api'),
    path('ai/api/departments/', api_views.departments_api, name='departments_api'),
    path('ai/api/mbti/', api_views.mbti_analysis_api, name='mbti_analysis_api'),
    path('ai/api/mbti_detect/', api_views.mbti_detect_api, name='mbti_detect_api'),
    path('ai/api/weekly_report/', api_views.weekly_report_api, name='weekly_report_api'),
    path('ai/api/analysis/<int:employee_id>/', api_views.employee_analysis_api, name='employee_analysis_api'),
]