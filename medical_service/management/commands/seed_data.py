import os
from datetime import datetime, timedelta

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from medical_service.models import Patient


class Command(BaseCommand):
    help = "Create demo doctor user and sample patients"

    def handle(self, *args, **options):
        demo_username = os.getenv("DEMO_ADMIN_USERNAME")
        demo_password = os.getenv("DEMO_ADMIN_PASSWORD")
        demo_email = os.getenv("DEMO_ADMIN_EMAIL") or demo_username

        if demo_username and demo_password:
            if not User.objects.filter(username=demo_username).exists():
                User.objects.create_superuser(
                    username=demo_username,
                    email=demo_email,
                    password=demo_password,
                    first_name="Juan",
                    last_name="Perez",
                )
                self.stdout.write(self.style.SUCCESS(f"Doctor {demo_username} created"))
        else:
            self.stdout.write(
                self.style.WARNING(
                    "Skipping demo admin creation. Set DEMO_ADMIN_USERNAME and DEMO_ADMIN_PASSWORD to enable it."
                )
            )

        today = datetime.now().date()
        test_patients = [
            {
                "first_name": "Maria",
                "middle_name": "Elena",
                "last_name": "Gonzalez Lopez",
                "age": 52,
                "status": "pending",
                "last_evaluation_date": today - timedelta(days=74),
                "identification": "234920232",
            },
            {
                "first_name": "Carlos",
                "middle_name": "Andres",
                "last_name": "Ramirez Perez",
                "age": 67,
                "status": "pending",
                "last_evaluation_date": today - timedelta(days=104),
                "identification": "234920233",
            },
            {
                "first_name": "Ana",
                "middle_name": "Lucia",
                "last_name": "Martinez Ruiz",
                "age": 45,
                "status": "pending",
                "last_evaluation_date": today - timedelta(days=105),
                "identification": "2349334334",
            },
            {
                "first_name": "Jose",
                "middle_name": "Miguel",
                "last_name": "Fernandez",
                "age": 59,
                "status": "pending",
                "last_evaluation_date": today - timedelta(days=106),
                "identification": "2340494434",
            },
            {
                "first_name": "Laura",
                "middle_name": "Sofia",
                "last_name": "Sanchez Torres",
                "age": 38,
                "status": "pending",
                "last_evaluation_date": today - timedelta(days=107),
                "identification": "23445494435",
            },
            {
                "first_name": "Roberto",
                "middle_name": "",
                "last_name": "Garcia Diaz",
                "age": 71,
                "status": "pending",
                "last_evaluation_date": today - timedelta(days=108),
                "identification": "434920234",
            },
        ]

        created_count = 0
        for patient_data in test_patients:
            _, created = Patient.objects.get_or_create(
                first_name=patient_data["first_name"],
                middle_name=patient_data.get("middle_name", ""),
                last_name=patient_data["last_name"],
                defaults={
                    "age": patient_data["age"],
                    "status": patient_data["status"],
                    "last_evaluation_date": patient_data["last_evaluation_date"],
                    "identification": patient_data["identification"],
                },
            )
            if created:
                created_count += 1

        self.stdout.write(self.style.SUCCESS(f"{created_count} patients created"))
        self.stdout.write(self.style.SUCCESS(f"Total patients: {Patient.objects.count()}"))
