from django.urls import path
from django.contrib import admin
from . import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.login_view, name='login'),
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('patient/<uuid:patient_id>/', views.patient_detail, name='patient_detail'),
    path('patient/<uuid:patient_id>/details/', views.patient_detail, name='patient_detail_legacy'),
    path('patient/<uuid:patient_id>/evaluation/', views.evaluation, name='evaluation'),
    path('patient/<uuid:patient_id>/evaluation/save/', views.save_evaluation, name='save_evaluation'),
    path('patient/<uuid:patient_id>/evaluation/<uuid:evaluation_id>/save-notes/', views.save_evaluation_notes, name='save_evaluation_notes'),
    path('patient/<uuid:patient_id>/processing/<path:task_id>/<uuid:evaluation_id>/', views.processing_view, name='processing'),
    path('patient/<uuid:patient_id>/results/', views.evaluation_results, name='evaluation_results'),
    path('patient/<uuid:patient_id>/results/<uuid:evaluation_id>/', views.evaluation_results, name='evaluation_results_detail'),
    path('api/evaluation-task/<uuid:evaluation_id>/', views.get_evaluation_task_status, name='get_evaluation_task_status'),
    path('api/check-task-status/<path:task_id>/', views.check_task_status, name='check_task_status'),
    path('logout/', views.logout_view, name='logout'),
]