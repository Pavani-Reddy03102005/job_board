from django.contrib import admin
from django.urls import path
from resumeapp import views

urlpatterns = [
    path('admin/', admin.site.urls),

    path('', views.home, name='home'),

    path('login/', views.login_view, name='login'),

    path('logout/', views.logout_view, name='logout'),

    path('register/', views.register_view, name='register'),

    path('dashboard/', views.dashboard, name='dashboard'),

    path('upload/', views.upload_resume, name='upload_resume'),

    path('results/<int:id>/', views.results, name='results'),

    path('analytics/', views.analytics, name='analytics'),
]