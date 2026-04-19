from django.urls import path
from . import views
from . import api_views

app_name = 'dashboard'

urlpatterns = [
    path('dashboard/', views.dashboard_home, name='dashboard_home'),
    path('m/', views.mobile_dashboard_page, name='mobile_dashboard_page'),
    path('m/workbench/', views.mobile_workbench_page, name='mobile_workbench_page'),
    path('m/me/', views.mobile_me_page, name='mobile_me_page'),
    path('m/employees/', views.mobile_employees_page, name='mobile_employees_page'),
    path('m/views/', views.mobile_views_page, name='mobile_views_page'),
    path('dashboard/api/', api_views.dashboard_api, name='dashboard_api'),
    path('dashboard/api/employees/', api_views.employees_api, name='employees_api'),
    path('dashboard/api/announcement/ops/', api_views.announcement_ops_api, name='announcement_ops_api'),
    path('dashboard/get_all_tasks/', views.get_all_tasks, name='get_all_tasks'),
    path('dashboard/get_personal_tasks/', views.get_personal_tasks, name='get_personal_tasks'),
    path('dashboard/update_company_top_tasks/', views.update_company_top_tasks, name='update_company_top_tasks'),
    path('dashboard/update_personal_top_tasks/', views.update_personal_top_tasks, name='update_personal_top_tasks'),
    path('employee/', views.employee_detail, name='employee_detail'),
    path('employee/subordinates/', views.employee_subordinates, name='employee_subordinates'),
    path('employee/logs/', views.get_employee_logs, name='get_employee_logs'),
    path('employee_list/delete/', views.employee_delete, name='employee_delete'),
    path('employee_list/add', views.employee_add, name='employee_add'),
    path('employee_list/get/', views.employee_get, name='employee_get'),
    path('employee_list/detail/', views.get_employee_detail, name='get_employee_detail'),
    path('employee_list/manager_role/', views.get_manager_role, name='get_manager_role'),
    path('employee_list/update/', views.employee_update, name='employee_update'),
    path('employee_list/department_employees/', views.get_department_employees, name='get_department_employees'),
    path('employee_list/', views.employee_list, name='employee_list'),
    # 个人资料相关
    path('employee/profile_update/', views.employee_profile_update, name='employee_profile_update'),
    path('employee/change_password/', views.employee_change_password, name='employee_change_password'),
    path('views/calendar/', views.get_calendar_view, name='get_calendar_view'),
    path('views/', views.calendar_page, name='calendar_page'),
]
