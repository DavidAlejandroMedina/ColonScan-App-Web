import uuid
from django.db import models
from django.contrib.auth.models import User
import random
import string

class DoctorProfile(models.Model):
    # Relación 1 a 1 con el usuario de Django
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    
    # Campos extra que no están en el User básico
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)

    def __str__(self):
        return f"Dr. {self.user.last_name}"

class Patient(models.Model):
    STATUS_CHOICES = [
        ('evaluated', 'Evaluado'),
        ('pending', 'Pendiente'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    identification = models.CharField(max_length=50, unique=True, null=True, blank=True)
    first_name = models.CharField(max_length=100)
    middle_name = models.CharField(max_length=100, blank=True, null=True)
    last_name = models.CharField(max_length=100)
    age = models.IntegerField()
    first_evaluation_date = models.DateField(auto_now_add=True)
    last_evaluation_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='pending')

    # def save(self, *args, **kwargs):
    #     if not self.patient_id:
    #         self.patient_id = self.generate_patient_id()
    #     super().save(*args, **kwargs)

    # @staticmethod
    # def generate_patient_id():
    #     """Genera ID similar a PAT-K7M9-N4P2"""
    #     chars = string.ascii_uppercase + string.digits
    #     # Eliminar caracteres ambiguos
    #     chars = chars.replace('0', '').replace('O', '').replace('I', '').replace('L', '')
    #     segment1 = ''.join(random.choices(chars, k=4))
    #     segment2 = ''.join(random.choices(chars, k=4))
    #     return f"PAT-{segment1}-{segment2}"

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.id})"

    class Meta:
        ordering = ['last_name']

class CTCImage(models.Model):
    id_ctc = models.CharField(max_length=100, unique=True)
    evaluation_date = models.DateField()
    result = models.TextField(null=True, blank=True)
    observation = models.TextField(null=True, blank=True)
    
    # Relaciones (Foreign Keys)
    doctor = models.ForeignKey(User, on_delete=models.RESTRICT)
    patient = models.ForeignKey(Patient, on_delete=models.RESTRICT)

    def __str__(self):
        return f"Examen {self.id_ctc} - {self.patient.last_name}"

class Evaluation(models.Model):
    """Modelo para almacenar las evaluaciones de pacientes"""
    
    ANALYSIS_STATUS_CHOICES = [
        ('processing', 'Procesando'),
        ('completed', 'Completado'),
        ('failed', 'Fallado'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='evaluations')
    doctor = models.ForeignKey(User, on_delete=models.RESTRICT)
    study_date = models.DateField()
    observations = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    # Campos para el análisis IA
    analysis_status = models.CharField(max_length=20, choices=ANALYSIS_STATUS_CHOICES, default='pending')
    analysis_result = models.JSONField(null=True, blank=True)
    analysis_completed_at = models.DateTimeField(null=True, blank=True)
    task_id = models.CharField(max_length=255, null=True, blank=True)  # ID de tarea de la API
    
    # Campos para archivos en Google Cloud Storage
    gcs_file_url = models.URLField(null=True, blank=True)  # URL del archivo en GCS
    gcs_blob_name = models.CharField(max_length=500, null=True, blank=True)  # Ruta del blob en GCS
    
    def __str__(self):
        return f"Evaluación {self.patient} - {self.study_date}"

class UploadedFile(models.Model):
    """Modelo para archivos subidos durante la evaluación"""
    evaluation = models.ForeignKey(Evaluation, on_delete=models.CASCADE, related_name='files')
    file = models.FileField(upload_to='ctc_scans/%Y/%m/%d/', null=True, blank=True)  # Archivo local (opcional)
    original_filename = models.CharField(max_length=255)
    file_size = models.IntegerField()  # en bytes
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    # Campos para Google Cloud Storage
    gcs_blob_name = models.CharField(max_length=500, null=True, blank=True)  # Ruta en el bucket
    gcs_file_url = models.URLField(null=True, blank=True)  # URL firmada para acceder al archivo
    gcs_uploaded_at = models.DateTimeField(null=True, blank=True)  # Fecha de carga a GCS
    
    def __str__(self):
        return self.original_filename