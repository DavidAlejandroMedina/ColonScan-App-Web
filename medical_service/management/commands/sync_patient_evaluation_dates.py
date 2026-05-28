"""
Management command para sincronizar las fechas de última evaluación de los pacientes
con la fecha más reciente de sus evaluaciones registradas.

Uso:
    python manage.py sync_patient_evaluation_dates
    python manage.py sync_patient_evaluation_dates --verbose
"""
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Max
from medical_service.models import Patient, Evaluation


class Command(BaseCommand):
    help = 'Sincroniza las fechas de última evaluación con la fecha más reciente de evaluaciones'

    def add_arguments(self, parser):
        parser.add_argument(
            '--verbose',
            action='store_true',
            dest='verbose',
            help='Muestra información detallada de cada actualización',
        )
        parser.add_argument(
            '--patient-id',
            type=str,
            dest='patient_id',
            help='Actualiza solo un paciente específico (UUID)',
        )

    def handle(self, *args, **options):
        verbose = options['verbose']
        patient_id = options.get('patient_id')

        # Filtrar pacientes
        if patient_id:
            try:
                patients = Patient.objects.filter(id=patient_id)
                if not patients.exists():
                    raise CommandError(f'Paciente con ID {patient_id} no encontrado')
            except Exception as e:
                raise CommandError(f'Error al filtrar paciente: {str(e)}')
        else:
            patients = Patient.objects.all()

        updated_count = 0
        unchanged_count = 0
        no_evaluations_count = 0

        self.stdout.write(f'Procesando {patients.count()} pacientes...\n')

        for patient in patients:
            # Obtener la fecha más reciente de evaluación
            latest_eval = (
                Evaluation.objects
                .filter(patient=patient)
                .aggregate(max_study_date=Max('study_date'))['max_study_date']
            )

            if latest_eval is None:
                # El paciente no tiene evaluaciones
                if patient.last_evaluation_date is not None:
                    patient.last_evaluation_date = None
                    patient.save(update_fields=['last_evaluation_date'])
                    updated_count += 1
                    if verbose:
                        self.stdout.write(
                            self.style.WARNING(
                                f'  ✓ {patient.first_name} {patient.last_name}: '
                                f'Se limpió la fecha (no hay evaluaciones)'
                            )
                        )
                else:
                    no_evaluations_count += 1
            else:
                # El paciente tiene evaluaciones
                if patient.last_evaluation_date != latest_eval:
                    old_date = patient.last_evaluation_date
                    patient.last_evaluation_date = latest_eval
                    patient.save(update_fields=['last_evaluation_date'])
                    updated_count += 1
                    if verbose:
                        self.stdout.write(
                            self.style.SUCCESS(
                                f'  ✓ {patient.first_name} {patient.last_name}: '
                                f'{old_date} → {latest_eval}'
                            )
                        )
                else:
                    unchanged_count += 1
                    if verbose:
                        self.stdout.write(
                            f'  - {patient.first_name} {patient.last_name}: '
                            f'Ya estaba sincronizado ({latest_eval})'
                        )

        # Resumen
        self.stdout.write('\n' + '='*60)
        self.stdout.write(
            self.style.SUCCESS(
                f'✓ {updated_count} pacientes actualizados'
            )
        )
        self.stdout.write(
            f'  {unchanged_count} pacientes ya estaban sincronizados'
        )
        self.stdout.write(
            f'  {no_evaluations_count} pacientes sin evaluaciones'
        )
        self.stdout.write('='*60)
