from django.apps import AppConfig


class MedicalServiceConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'medical_service'
    verbose_name = 'Medical Service'
    
    def ready(self):
        """Importa los signals cuando la app está lista"""
        import medical_service.signals  # noqa
