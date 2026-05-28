"""
Signals para sincronizar datos entre Evaluation y Patient
"""
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.db.models import Max
from .models import Evaluation, Patient


@receiver(post_save, sender=Evaluation)
def update_patient_last_evaluation_date(sender, instance, created, **kwargs):
    """
    Actualiza el campo last_evaluation_date del paciente cuando se crea o modifica una evaluación.
    Se actualiza con la fecha más reciente de todas las evaluaciones del paciente.
    """
    patient = instance.patient
    
    # Obtener la fecha más reciente de evaluación
    latest_evaluation_date = (
        Evaluation.objects
        .filter(patient=patient)
        .aggregate(max_study_date=Max('study_date'))['max_study_date']
    )
    
    # Actualizar el paciente si hay una fecha más reciente
    if latest_evaluation_date and patient.last_evaluation_date != latest_evaluation_date:
        patient.last_evaluation_date = latest_evaluation_date
        patient.save(update_fields=['last_evaluation_date'])


@receiver(post_delete, sender=Evaluation)
def update_patient_after_evaluation_delete(sender, instance, **kwargs):
    """
    Actualiza el campo last_evaluation_date del paciente cuando se elimina una evaluación.
    Se calcula con la fecha más reciente de las evaluaciones restantes.
    """
    patient = instance.patient
    
    # Obtener la fecha más reciente de evaluación después de la eliminación
    latest_evaluation_date = (
        Evaluation.objects
        .filter(patient=patient)
        .aggregate(max_study_date=Max('study_date'))['max_study_date']
    )
    
    # Actualizar el paciente
    if patient.last_evaluation_date != latest_evaluation_date:
        patient.last_evaluation_date = latest_evaluation_date
        patient.save(update_fields=['last_evaluation_date'])
