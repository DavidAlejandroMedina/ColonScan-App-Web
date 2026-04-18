from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView
from medical_service import views

urlpatterns = [
    path('admin/', admin.site.urls),
    # Esto habilita login, logout, password reset de forma automática
    # path('accounts/', include('django.contrib.auth.urls')),
    # Redirigir la raíz al login
    # path('', RedirectView.as_view(url='/accounts/login/')),
    
    # path('admin/', admin.site.urls),
    path('', views.login_view, name='login'),
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('patient/<uuid:patient_id>/', views.patient_detail, name='patient_detail'),
    path('patient/<uuid:patient_id>/details/', views.patient_detail, name='patient_detail_legacy'),
    path('patient/<uuid:patient_id>/evaluation/', views.evaluation, name='evaluation'),
    path('patient/<uuid:patient_id>/evaluation/save/', views.save_evaluation, name='save_evaluation'),
    path('patient/<uuid:patient_id>/evaluation/<uuid:evaluation_id>/save-notes/', views.save_evaluation_notes, name='save_evaluation_notes'),
    path('patient/<uuid:patient_id>/processing/<str:task_id>/<uuid:evaluation_id>/', views.processing_view, name='processing'),
    path('patient/<uuid:patient_id>/results/', views.evaluation_results, name='evaluation_results'),
    path('patient/<uuid:patient_id>/results/<uuid:evaluation_id>/', views.evaluation_results, name='evaluation_results_detail'),
    path('evaluation/<uuid:evaluation_id>/update_task/', views.update_evaluation_task_id, name='update_task_id'),
    path('evaluation/<uuid:evaluation_id>/save_results/', views.save_analysis_results, name='save_results'),
    path('api/evaluation-task/<uuid:evaluation_id>/', views.get_evaluation_task_status, name='get_evaluation_task_status'),
    path('api/check-task-status/<path:task_id>/', views.check_task_status, name='check_task_status'),
    path('logout/', views.logout_view, name='logout'),
]