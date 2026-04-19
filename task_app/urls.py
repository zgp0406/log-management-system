
from django.urls import path
from django.shortcuts import redirect
from . import views
from . import api_views

urlpatterns = [
    path('tasks/api/', api_views.tasks_api, name='tasks_api'),
    path('tasks/api/<int:task_id>/take/', api_views.task_take_api, name='task_take_api'),
    path('tasks/api/<int:task_id>/complete/', api_views.task_complete_api, name='task_complete_api'),
    path('tasks/api/create/', api_views.task_create_api, name='task_create_api'),
    path('tasks/api/<int:task_id>/update/', api_views.task_update_api, name='task_update_api'),
    path('tasks/api/<int:task_id>/delete/', api_views.task_delete_api, name='task_delete_api'),
    path('tasks/', views.task_page, name='task_page'),
    path('m/tasks/', views.mobile_task_page, name='mobile_task_page'),
    path('m/tasks/new/', views.mobile_task_new_page, name='mobile_task_new_page'),
    path('m/tasks/<int:task_id>/', views.mobile_task_detail_page, name='mobile_task_detail_page'),
    path('m/notifications/', views.mobile_task_notifications_page, name='mobile_task_notifications_page'),
    path('tasks/<int:task_id>/', views.task_detail, name='task_detail'),
    path('tasks/<int:task_id>/delete/', views.task_delete, name='task_delete'),
    path('tasks/<int:task_id>/update/', views.task_update, name='task_update'),
    path('tasks/<int:task_id>/update_status/', views.task_update_status, name='task_update_status'),
    # 子任务相关路由
    path('tasks/<int:task_id>/subtasks/', views.subtask_list, name='subtask_list'),
    path('tasks/<int:task_id>/subtasks/create/', views.subtask_create, name='subtask_create'),
    path('tasks/<int:task_id>/subtasks/<int:subtask_id>/update/', views.subtask_update, name='subtask_update'),
    path('tasks/<int:task_id>/subtasks/<int:subtask_id>/delete/', views.subtask_delete, name='subtask_delete'),
    # 通知相关路由
    path('tasks/notifications/', views.get_notifications, name='get_notifications'),
    path('tasks/notifications/<int:notification_id>/read/', views.mark_notification_read, name='mark_notification_read'),
    path('tasks/notifications/read_all/', views.mark_all_notifications_read, name='mark_all_notifications_read'),
    path('tasks/notifications/stream/', api_views.notifications_stream, name='notifications_stream'),
]
