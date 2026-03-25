from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import User
from django.forms.widgets import FileInput
from .models import Patient, Evaluation
import zipfile
import os

class CustomLoginForm(AuthenticationForm):
    username = forms.CharField(
        label="Correo electrónico",
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'ejemplo@hospital.com'
        })
    )
    password = forms.CharField(
        label="Contraseña",
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': '••••••••'
        })
    )

class PatientForm(forms.ModelForm):
    class Meta:
        model = Patient
        fields = ['first_name', 'middle_name', 'last_name', 'age', 'identification']
        labels = {
            'first_name': 'Primer Nombre',
            'middle_name': 'Segundo Nombre (opcional)',
            'last_name': 'Apellidos',
            'age': 'Edad',
            'identification': 'Identificación',
        }
        widgets = {
            'first_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: Juan'
            }),
            'middle_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: Carlos (opcional)'
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: Pérez García'
            }),
            'age': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: 58',
                'min': '1'
            }),
            'identification': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: 123456789'
            }),
        }
    
    def clean_age(self):
        """Validar que la edad no sea mayor a 123 años"""
        age = self.cleaned_data.get('age')
        
        if age is not None:
            if age > 123:
                raise forms.ValidationError('La edad no puede ser mayor a 123 años')
            if age < 0:
                raise forms.ValidationError('La edad no puede ser negativa')
        
        return age



class EvaluationForm(forms.ModelForm):
    """ModelForm para crear/editar Evaluations. Incluye study_date y observations."""
    
    zip_file = forms.FileField(
        required=True,
        label='Archivo CTC (.zip)',
        widget=forms.FileInput(attrs={
            'class': 'file-input',
            'accept': '.zip',
            'id': 'file-upload'
        })
    )

    class Meta:
        model = Evaluation
        fields = ['study_date', 'observations']
        widgets = {
            'study_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'observations': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Ingrese sus observaciones o comentarios sobre el caso...'
            }),
        }
        labels = {
            'study_date': 'Fecha de la toma',
            'observations': 'Observaciones iniciales'
        }
    
    def clean_zip_file(self):
        """Validar que el archivo sea un ZIP válido"""
        zip_file = self.cleaned_data.get('zip_file')
        
        if zip_file:
            # Validar extensión
            if not zip_file.name.endswith('.zip'):
                raise forms.ValidationError('El archivo debe tener extensión .zip')
            
            # Validar que sea un ZIP válido
            try:
                if not zipfile.is_zipfile(zip_file):
                    raise forms.ValidationError('El archivo no es un ZIP válido')
            except Exception as e:
                raise forms.ValidationError(f'Error al validar el archivo ZIP: {str(e)}')
            
            # Validar tamaño (máximo 500MB)
            if zip_file.size > 500 * 1024 * 1024:
                raise forms.ValidationError('El archivo no puede ser mayor a 500MB')
        
        return zip_file

# class MultipleFileInput(FileInput):
#     def __init__(self, attrs=None):
#         default_attrs = {'multiple': True}
#         if attrs:
#             default_attrs.update(attrs)
#         super().__init__(attrs=default_attrs)

# class EvaluationForm(forms.ModelForm):
#     images = forms.FileField(
#         required=False,
#         laberl='Archivos CTC',
#         widget=MultipleFileInput(attrs={
#             'accept': '.dcm,.dicom,image/*,.jpg,.jpeg,.png',
#             'class': 'file-input'
#         })
#     )
    
#     class Meta:
#         model = Evaluation
#         fields = ['patient', 'notes']  # sin images


# class EvaluationForm(forms.ClearableFileInput):
#     files = forms.FileField(
#         widget=forms.ClearableFileInput(attrs={
#             'multiple': True,
#             'accept': '.dcm,.dicom,image/*,.jpg,.jpeg,.png',
#             'class': 'file-input'
#         }),
#         required=True,
#         label='Archivos CTC'
#     )

#     class Meta:
#         model = Evaluation
#         fields = ['study_date', 'observations']
#         widgets = {
#             'study_date': forms.DateInput(attrs={
#                 'class': 'form-control',
#                 'type': 'date'
#             }),
#             'observations': forms.Textarea(attrs={
#                 'class': 'form-control',
#                 'rows': 4,
#                 'placeholder': 'Ingrese sus observaciones o comentarios sobre el caso...'
#             }),
#         }
#         labels = {
#             'study_date': 'Fecha de la toma',
#             'observations': 'Observaciones iniciales'
#         }

class UserRegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True)
    first_name = forms.CharField(max_length=100, required=True, label='Nombre')
    last_name = forms.CharField(max_length=100, required=True, label='Apellido')

    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name', 'password1', 'password2']
    
    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        if commit:
            user.save()
        return user