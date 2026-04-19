from django.urls import path
from . import views

app_name = 'login_app'

urlpatterns = [
    path('login_page/', views.login_page, name='login_page'),
    path('login/', views.employee_login, name='employee_login'),
    path('logout/', views.employee_logout, name='employee_logout'),
]
