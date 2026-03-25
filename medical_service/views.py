from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_http_methods
from django.views.decorators.csrf import csrf_exempt
import json
import requests
import os
from dotenv import load_dotenv
from .models import Patient, Evaluation, UploadedFile
from .forms import EvaluationForm, PatientForm
import random
import string
import logging
from datetime import datetime

# Cargar variables de entorno
load_dotenv()

logger = logging.getLogger(__name__)

@login_required
@require_http_methods(["GET", "POST"])
def dashboard_view(request):
        
    # Actualizar el estado de pacientes que ya tienen evaluaciones completadas
    # Cambiar de 'pending' a 'evaluated' si tienen al menos 1 evaluación completada
    pending_patients = Patient.objects.filter(status='pending')
    for patient in pending_patients:
        if patient.evaluations.filter(analysis_status='completed').exists():
            patient.status = 'evaluated'
            patient.save()
    
    patients = Patient.objects.all().order_by('-last_evaluation_date')
    
    # # Generar IDs para pacientes que no tienen
    # for patient in patients:
    #     if not hasattr(patient, 'patient_id') or not patient.patient_id:
    #         chars = string.ascii_uppercase + string.digits
    #         chars = chars.replace('0', '').replace('O', '').replace('I', '').replace('L', '')
    #         segment1 = ''.join(random.choices(chars, k=4))
    #         segment2 = ''.join(random.choices(chars, k=4))
    #         patient.patient_id = f"PAT-{segment1}-{segment2}"
    
    
    form = PatientForm()
    context = {
        'patients': patients,
        'form': form,
    }
    
    if request.method == 'POST':
        print("=" * 50)
        print("🔍 DEPURANDO SOLICITUD POST")
        print("=" * 50)
        print(f"📋 Datos POST: {request.POST}")
        print(f"📎 Archivos: {request.FILES}")
        
        form = PatientForm(request.POST, request.FILES)
        
        print(f"✓ Formulario creado")
        print(f"✓ Validando formulario...")
        
        if form.is_valid():
            print(f"✅ FORMULARIO VÁLIDO")
            print(f"   Datos limpios: {form.cleaned_data}")
            
            try:
                patient = form.save()
                print(f"✅ PACIENTE GUARDADO EXITOSAMENTE")
                print(f"   ID: {patient.id}")
                print(f"   Nombre: {patient.first_name} {patient.last_name}")
                print(f"   Patient ID: {patient.identification}")
                
                # Redirigir a dashboard con parámetro de éxito y nombre del paciente
                from urllib.parse import urlencode
                params = urlencode({'patient_created': '1', 'patient_name': patient.first_name})
                redirect_url = f"{reverse('dashboard')}?{params}"
                print(f"🔀 Redirigiendo a: {redirect_url}")
                return redirect(redirect_url)
            
            except Exception as e:
                print(f"❌ ERROR AL GUARDAR: {str(e)}")
                print(f"   Tipo de error: {type(e).__name__}")
                import traceback
                traceback.print_exc()
        else:
            print(f"❌ FORMULARIO INVÁLIDO")
            print(f"   Errores: {form.errors}")
            for field, errors in form.errors.items():
                print(f"   - {field}: {errors}")
        
        print("=" * 50)
    
    return render(request, 'dashboard.html', context)

# @login_required
# def create_patient(request):
#     if request.method == 'POST':
#         try:
#             patient = Patient.objects.create(
#                 first_name=request.POST.get('first_name'),
#                 last_name=request.POST.get('last_name'),
#                 age=request.POST.get('age'),
#                 status='pending'
#             )
#             messages.success(request, 'Paciente creado exitosamente')
#         except Exception as e:
#             messages.error(request, f'Error al crear paciente: {str(e)}')
        
#         return redirect('dashboard')
    
#     return redirect('dashboard')

def login_view(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        
        user = authenticate(request, username=email, password=password)
        
        if user is not None:
            login(request, user)
            return redirect(f"{reverse('dashboard')}?login_success=1")
        else:
            messages.error(request, 'Credenciales incorrectas')
            return redirect('login')  # Redirect to display message and consume it
            
    return render(request, 'login.html')

@login_required
def logout_view(request):
    logout(request)
    return redirect(f"{reverse('login')}?logout_success=1")


@login_required
def patient_detail(request, patient_id):
    """Vista de detalles del paciente"""
    patient = get_object_or_404(Patient, id=patient_id)
    evaluations = patient.evaluations.all().order_by('-study_date')
    
    context = {
        'patient': patient,
        'evaluations': evaluations,
    }
    return render(request, 'detail.html', context)


@login_required
def evaluation(request, patient_id):
    """Vista para la evaluación con imágenes CTC"""
    print(f"📸 Accediendo a evaluación para paciente ID: {patient_id}")
    patient = get_object_or_404(Patient, id=patient_id)
    
    print(f"✓ Paciente encontrado: {patient.first_name} {patient.last_name}")
    
    # Crear el formulario (vacío para GET, con datos para POST)
    form = EvaluationForm(request.POST or None, request.FILES or None)
    print(f"📝 Formulario creado: {form.fields['study_date'].initial}")
    
    if request.method == 'POST':
        print(f"📸 Procesando evaluación para paciente {patient.first_name}")
        
        # Procesar el archivo ZIP
        zip_file = request.FILES.get('zip_file')
        print(f"   Archivo ZIP recibido: {zip_file is not None}")
        print(f"   Datos POST: {request.POST.keys()}")
        
        if form.is_valid() and zip_file:
            print(f"✅ Formulario válido y archivo ZIP recibido")
            print(f"📦 Tamaño del archivo: {zip_file.size / (1024*1024):.2f}MB")
            
            # Crear evaluación con datos del formulario
            evaluation = form.save(commit=False)
            evaluation.patient = patient
            evaluation.doctor = request.user
            evaluation.analysis_status = 'processing'
            evaluation.save()
            
            print(f"✅ Evaluación creada: {evaluation.id}")
            
            # Enviar el ZIP a la API del modelo
            try:
                # Leer el contenido del archivo ZIP
                zip_file.seek(0)  # Reiniciar posición del archivo
                
                # Obtener configuración de la API desde variables de entorno
                api_url = os.getenv('API_URL')
                api_timeout = int(os.getenv('API_TIMEOUT', '300'))
                api_key = os.getenv('API_KEY', '')
                ssl_verify = os.getenv('API_ENABLE_SSL_VERIFY', 'False').lower() == 'true'
                
                # Validar que API_URL esté configurado
                if not api_url:
                    print("❌ ERROR: API_URL no está configurado en variables de entorno")
                    messages.error(request, 'Error de configuración: API_URL no definida')
                    return render(request, 'evaluation.html', {'patient': patient, 'form': form})
                
                # Preparar headers
                headers = {'Authorization': f'Bearer {request.user.id}'}
                if api_key:
                    headers['X-API-Key'] = api_key
                
                # Preparar para envío a API
                files = {'file': (zip_file.name, zip_file, 'application/zip')}
                
                print(f"📡 Enviando archivo a API: {api_url}")
                print(f"   Tamaño: {zip_file.size} bytes")
                print(f"   Timeout: {api_timeout}s")
                print(f"   SSL Verify: {ssl_verify}")
                
                # Intentar conexión con reintentos
                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        print(f"   Intento {attempt + 1}/{max_retries}...")
                        response = requests.post(
                            api_url, 
                            files=files, 
                            headers=headers, 
                            timeout=api_timeout,
                            verify=ssl_verify
                        )
                        
                        print(f"   Status Code: {response.status_code}")
                        print(f"   Response Headers: {response.headers}")
                        print(f"   Response Body (primeros 500 chars): {response.text[:500]}")
                        
                        if response.status_code == 200:
                            result = response.json()
                            task_id = result.get('task_id')
                            
                            if task_id:
                                evaluation.task_id = task_id
                                evaluation.analysis_status = 'processing'
                                evaluation.save()
                                print(f"✅ Archivo enviado a la API. Task ID: {task_id}")
                                return redirect('processing', patient_id=patient.id, task_id=task_id, evaluation_id=evaluation.id)
                            else:
                                print(f"⚠️  API respondió 200 pero sin task_id. Response: {result}")
                                messages.error(request, 'API respondió pero sin task_id. Intenta de nuevo.')
                                break
                        elif response.status_code == 202:
                            # Accepted - procesamiento en background
                            result = response.json()
                            task_id = result.get('task_id')
                            if task_id:
                                evaluation.task_id = task_id
                                evaluation.analysis_status = 'processing'
                                evaluation.save()
                                print(f"✅ Archivo aceptado para procesamiento. Task ID: {task_id}")
                                return redirect('processing', patient_id=patient.id, task_id=task_id, evaluation_id=evaluation.id)
                        else:
                            if attempt < max_retries - 1:
                                print(f"⚠️  Intento {attempt + 1} falló con status {response.status_code}. Reintentando...")
                                import time
                                time.sleep(2 ** attempt)  # Backoff exponencial
                                continue
                            else:
                                print(f"❌ Error en API después de {max_retries} intentos: {response.status_code}")
                                print(f"   Respuesta: {response.text}")
                                messages.error(request, f'Error al procesar el archivo: {response.status_code}')
                                break
                    except requests.exceptions.Timeout:
                        if attempt < max_retries - 1:
                            print(f"⚠️  Timeout en intento {attempt + 1}. Reintentando...")
                            continue
                        else:
                            raise
                    
            except requests.exceptions.Timeout as e:
                print(f"❌ Timeout en la API después de retries: {str(e)}")
                messages.error(request, f'La API tardó demasiado en responder (timeout: {api_timeout}s). Intenta de nuevo o aumenta el timeout.')
            except requests.exceptions.ConnectionError as e:
                print(f"❌ Error de conexión con la API: {str(e)}")
                print(f"   URL: {api_url}")
                messages.error(request, f'No se pudo conectar con la API. Verifica que esté corriendo en {api_url}')
            except requests.exceptions.RequestException as e:
                print(f"❌ Error en la solicitud: {str(e)}")
                messages.error(request, f'Error al conectar con el servidor de análisis: {str(e)}')
            except Exception as e:
                print(f"❌ Error inesperado: {str(e)}")
                import traceback
                print(traceback.format_exc())
                messages.error(request, f'Error inesperado: {str(e)}')
        elif not zip_file:
            print("⚠ No se recibió archivo ZIP")
            messages.error(request, 'Por favor selecciona un archivo ZIP')
        else:
            print(f"❌ Errores en formulario: {form.errors}")
            for field, errors in form.errors.items():
                messages.error(request, f'{field}: {errors[0]}')
    
    context = {
        'patient': patient,
        'form': form,
    }
    return render(request, 'evaluation.html', context)

@login_required
def evaluation_results(request, patient_id, evaluation_id=None):
    """Vista para mostrar resultados de la evaluación"""
    patient = get_object_or_404(Patient, id=patient_id)
    
    if evaluation_id:
        evaluation = get_object_or_404(Evaluation, id=evaluation_id, patient=patient)
    else:
        # Obtener la última evaluación
        evaluation = Evaluation.objects.filter(patient=patient).latest('study_date')
    
    context = {
        'patient': patient,
        'evaluation': evaluation,
    }
    return render(request, 'evaluation_results.html', context)


@login_required
@require_http_methods(["GET"])
def check_task_status(request, task_id):
    """Endpoint API para verificar el estado del procesamiento de tareas"""
    try:
        # Obtener configuración de la API
        # En Docker: usar host.docker.internal para acceder al host local
        # En local: usar localhost
        api_base_url = os.getenv('API_BASE_URL', 'http://host.docker.internal:8001/api/v1')
        api_status_url = f"{api_base_url}/task/{task_id}"
        api_timeout = int(os.getenv('API_TIMEOUT', '30'))
        
        print(f"🔍 Verificando estado del task: {task_id}")
        print(f"   URL: {api_status_url}")
        
        # Consultar estado a la API
        response = requests.get(
            api_status_url,
            timeout=api_timeout,
            verify=os.getenv('API_ENABLE_SSL_VERIFY', 'False').lower() == 'true'
        )
        
        print(f"   Status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            status = result.get('status')
            print(f"   Task status: {status}")
            
            # Buscar y actualizar la evaluación si está completada
            if status == 'completed':
                try:
                    evaluation = Evaluation.objects.get(task_id=task_id)
                    
                    # Guardar resultados en la evaluación
                    evaluation.analysis_result = result
                    evaluation.analysis_status = 'completed'
                    evaluation.save()
                    
                    print(f"✅ Evaluación actualizada con resultados: {evaluation.id}")
                except Evaluation.DoesNotExist:
                    print(f"⚠️  No se encontró evaluación con task_id: {task_id}")
            
            return JsonResponse({
                'success': True,
                'task_id': task_id,
                'status': status,
                'progress': result.get('progress', 0),
                'result': result.get('result'),
                'message': result.get('message', '')
            })
        else:
            print(f"   Error: {response.status_code}")
            return JsonResponse({
                'success': False,
                'error': f'API retornó status {response.status_code}'
            }, status=response.status_code)
            
    except requests.exceptions.Timeout:
        print(f"❌ Timeout al verificar estado del task")
        return JsonResponse({
            'success': False,
            'error': 'Timeout al consultar estado'
        }, status=504)
    except requests.exceptions.ConnectionError:
        print(f"❌ Error de conexión al verificar estado")
        return JsonResponse({
            'success': False,
            'error': 'No se puede conectar con la API'
        }, status=503)
    except Exception as e:
        print(f"❌ Error inesperado: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_POST
def save_evaluation_notes(request, patient_id, evaluation_id):
    """Guardar notas del médico en una evaluación existente"""
    try:
        patient = get_object_or_404(Patient, id=patient_id)
        evaluation = get_object_or_404(Evaluation, id=evaluation_id, patient=patient)
        
        # Obtener las notas del cuerpo de la solicitud
        data = json.loads(request.body)
        observations = data.get('observations', '').strip()
        
        # Actualizar las observaciones
        evaluation.observations = observations
        evaluation.save()
        
        logger.info(f"✅ Notas guardadas para evaluación {evaluation_id}")
        
        return JsonResponse({
            'success': True,
            'message': 'Notas guardadas exitosamente en la evaluación'
        })
    except Evaluation.DoesNotExist:
        logger.error(f"❌ Evaluación no encontrada: {evaluation_id}")
        return JsonResponse({
            'success': False,
            'error': 'Evaluación no encontrada'
        }, status=404)
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Formato de datos inválido'
        }, status=400)
    except Exception as e:
        logger.error(f"❌ Error al guardar notas: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)


@login_required
@require_POST
def save_evaluation(request, patient_id):
    """Guardar evaluación en Django después de enviar a la API"""
    patient = get_object_or_404(Patient, id=patient_id)
    
    study_date = request.POST.get('study_date')
    observations = request.POST.get('observations', '')
    
    try:
        # Crear evaluación
        evaluation = Evaluation.objects.create(
            patient=patient,
            doctor=request.user,
            study_date=study_date,
            observations=observations,
            analysis_status='processing'
        )
        
        logger.info(f"✅ Evaluación creada: {evaluation.id}")
        
        return JsonResponse({
            'success': True,
            'evaluation_id': str(evaluation.id),
            'message': 'Evaluación guardada exitosamente'
        })
    except Exception as e:
        logger.error(f"❌ Error al guardar evaluación: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)


@login_required
@require_POST
def update_evaluation_task_id(request, evaluation_id):
    """Actualizar task_id de una evaluación"""
    try:
        data = json.loads(request.body)
        task_id = data.get('task_id')
        
        evaluation = get_object_or_404(Evaluation, id=evaluation_id, doctor=request.user)
        evaluation.task_id = task_id
        evaluation.save()
        
        logger.info(f"✅ Task ID actualizado para evaluación {evaluation_id}: {task_id}")
        
        return JsonResponse({
            'success': True,
            'message': 'Task ID actualizado exitosamente'
        })
    except Exception as e:
        logger.error(f"❌ Error al actualizar task_id: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)


@login_required
@require_POST
def save_analysis_results(request, evaluation_id):
    """Guardar resultados del análisis de la API"""
    try:
        from datetime import datetime
        
        data = json.loads(request.body)
        
        logger.info(f"📦 Datos recibidos: {json.dumps(data, indent=2)}")
        
        evaluation = get_object_or_404(Evaluation, id=evaluation_id, doctor=request.user)
        
        # Guardar el resultado completo del API
        evaluation.analysis_result = data.get('analysis_result')
        evaluation.analysis_status = data.get('status', 'completed')
        
        # Mapear el timestamp de predicción
        prediction_timestamp_str = data.get('prediction_timestamp')
        logger.info(f"⏰ prediction_timestamp recibido: {prediction_timestamp_str}")
        
        if prediction_timestamp_str:
            try:
                # Convertir el string ISO a datetime
                prediction_timestamp = datetime.fromisoformat(prediction_timestamp_str)
                evaluation.analysis_completed_at = prediction_timestamp
                logger.info(f"✅ Timestamp parseado correctamente: {prediction_timestamp}")
            except ValueError as parse_error:
                logger.warning(f"⚠️ No se pudo parsear prediction_timestamp '{prediction_timestamp_str}': {parse_error}")
        else:
            logger.warning(f"⚠️ prediction_timestamp no encontrado en la respuesta")
        
        if data.get('status') == 'completed':
            evaluation.analysis_status = 'completed'
            # Actualizar el estado del paciente a 'evaluated'
            patient = evaluation.patient
            patient.status = 'evaluated'
            patient.save()
        elif data.get('status') == 'failed':
            evaluation.analysis_status = 'failed'
        
        evaluation.save()
        
        logger.info(f"✅ Resultados guardados para evaluación {evaluation_id}")
        logger.info(f"📊 analysis_completed_at en DB: {evaluation.analysis_completed_at}")
        
        return JsonResponse({
            'success': True,
            'message': 'Resultados guardados exitosamente'
        })
    except Exception as e:
        logger.error(f"❌ Error al guardar resultados: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)


@login_required
def processing_view(request, patient_id, task_id, evaluation_id):
    """Vista de procesamiento - muestra la pantalla de carga"""
    patient = get_object_or_404(Patient, id=patient_id)
    
    # Intentar obtener la evaluación si existe
    try:
        evaluation = Evaluation.objects.get(id=evaluation_id, patient=patient)
    except Evaluation.DoesNotExist:
        # Si no existe aún, crear una temporal
        evaluation = None
    
    context = {
        'patient': patient,
        'task_id': task_id,
        'evaluation_id': evaluation_id,
        'patient_id': patient_id,
    }
    
    return render(request, 'processing.html', context)

# @login_required
# @require_http_methods(["GET", "POST"])
# def patient_create(request):
#     if request.method == 'POST':
#         form = PatientForm(request.POST)
        
#         print(f"📋 Datos recibidos: {request.POST}")
#         print(f"✓ Validando formulario...")
        
#         if form.is_valid():
#             patient = form.save()
#             print(f"✅ ÉXITO: Paciente guardado en BD")
#             print(f"   - Nombre: {patient.first_name} {patient.last_name}")
#             print(f"   - ID: {patient.identification}")
#             print(f"   - Edad: {patient.age}")
#             print(f"   - BD ID: {patient.id}")
            
#             # Verificar que realmente se guardó
#             exists = Patient.objects.filter(id=patient.id).exists()
#             print(f"   - Verificación: {'✓ Existe en BD' if exists else '✗ NO existe en BD'}")
            
#             return redirect('dashboard')
#         else:
#             print(f"❌ ERRORES en formulario:")
#             for field, errors in form.errors.items():
#                 print(f"   - {field}: {errors}")
            
#             return render(request, 'dashboard.html', {'form': form, 'errors': form.errors})
    
#     form = PatientForm()
#     return render(request, 'dashboard.html', {'form': form})

# @login_required
# def patient_detail(request, patient_id):
#     """Vista de detalles del paciente"""
#     patient = get_object_or_404(Patient, id=patient_id, doctor=request.user)
#     evaluations = patient.evaluations.all().order_by('-created_at')
#     context = {
#         'patient': patient,
#         'evaluations': evaluations
#     }
#     return render(request, '_register.html', context)

# @login_required
# def evaluation_create_view(request):
#     if request.method == 'POST':
#         form = EvaluationForm(request.POST)
#         if form.is_valid():
#             # Procesar archivos en memoria
#             files = request.FILES.getlist('images')
            
#             # Guardar evaluación
#             evaluation = Evaluation.objects.create(
#                 patient=form.cleaned_data['patient'],
#                 notes=form.cleaned_data['notes'],
#                 doctor=request.user
#             )
            
#             # Procesar archivos sin guardarlos
#             analysis_results = []
#             for file in files:
#                 file_content = file.read()
#                 # Aquí llamas tu modelo ML para análisis
#                 result = analyze_with_model(file_content)
#                 analysis_results.append(result)
            
#             # Guardar resultados si es necesario
#             # evaluation.results = analysis_results
#             # evaluation.save()
            
#             return redirect('dashboard')
#     else:
#         form = EvaluationForm()
    
#     return render(request, 'evaluation_form.html', {'form': form})

# def analyze_with_model(file_content):
#     """Tu función de análisis con el modelo ML"""
#     # Implementar lógica aquí
#     return {'diagnosis': 'resultado del análisis'}

# API Views
# @csrf_exempt
# @require_POST
# @login_required
# def create_patient_api(request):
#     """API para crear paciente vía AJAX"""
#     try:
#         data = json.loads(request.body)
        
#         # Crear paciente
#         patient = Patient.objects.create(
#             first_name=data.get('first_name'),
#             middle_name=data.get('middle_name', ''),
#             last_name=data.get('last_name'),
#             age=int(data.get('age')),
#             identification=data.get('identification'),
#             doctor=request.user
#         )
        
#         return JsonResponse({
#             'success': True,
#             'patient': {
#                 'id': str(patient.id),
#                 'name': f"{patient.first_name} {patient.last_name}",
#                 'patient_id': patient.patient_id
#             }
#         })
#     except Exception as e:
#         return JsonResponse({
#             'success': False,
#             'error': str(e)
#         }, status=400)

# @login_required
# def start_analysis_api(request, evaluation_id):
#     """API para iniciar análisis (simulación)"""
#     evaluation = get_object_or_404(Evaluation, id=evaluation_id, doctor=request.user)
    
#     # Aquí iría la integración con el modelo Keras
#     # Por ahora solo simulamos
    
#     evaluation.analysis_status = 'completed'
#     evaluation.analysis_result = {
#         'findings': 'No se detectaron pólipos significativos',
#         'confidence': 0.95,
#         'recommendations': 'Continuar con controles regulares'
#     }
#     evaluation.save()
    
#     return JsonResponse({
#         'success': True,
#         'status': evaluation.analysis_status
#     })