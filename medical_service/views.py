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
import threading
from urllib.parse import quote
from dotenv import load_dotenv
from datetime import datetime
from .models import Patient, Evaluation, UploadedFile
from .forms import EvaluationForm, PatientForm
from .gcs_service import gcs_service
import random
import string
import logging

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

                # Redirigir directamente a evaluación del paciente recién creado
                redirect_url = reverse('evaluation', kwargs={'patient_id': patient.id})
                print(f"🔀 Redirigiendo a evaluación: {redirect_url}")
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
        try:
            email = request.POST.get('email')
            password = request.POST.get('password')

            user = authenticate(request, username=email, password=password)

            if user is not None:
                login(request, user)
                return redirect(f"{reverse('dashboard')}?login_success=1")

            messages.error(request, 'Credenciales incorrectas')
            return redirect('login')  # Redirect to display message and consume it
        except Exception:
            logger.exception("Unexpected error during login")
            messages.error(request, 'Ocurrió un error al iniciar sesión. Intenta nuevamente.')
            return redirect('login')
            
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
    """Vista para la evaluación con imágenes CTC
    
    FLUJO NUEVO CON GCS:
    1. Recibe archivo ZIP
    2. Sube a Google Cloud Storage
    3. Obtiene URL firmada
    4. Envía URL a la API (no el archivo)
    """
    print(f"📸 Accediendo a evaluación para paciente ID: {patient_id}")
    patient = get_object_or_404(Patient, id=patient_id)
    
    print(f"✓ Paciente encontrado: {patient.first_name} {patient.last_name}")
    
    # Crear el formulario (vacío para GET, con datos para POST)
    form = EvaluationForm(request.POST or None, request.FILES or None)
    
    if request.method == 'POST':
        print(f"📸 Procesando evaluación para paciente {patient.first_name}")
        
        # Procesar el archivo ZIP
        zip_file = request.FILES.get('zip_file')
        print(f"   Archivo ZIP recibido: {zip_file is not None}")
        
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
            
            # PASO 1: Subir archivo a Google Cloud Storage
            try:
                print(f"\n📤 PASO 1: Subiendo archivo a Google Cloud Storage...")
                
                # Subir archivo a GCS usando la instancia global
                zip_file.seek(0)  # Reiniciar posición
                gcs_result = gcs_service.upload_file(
                    zip_file,
                    evaluation_id=str(evaluation.id),
                    filename=zip_file.name
                )
                
                if not gcs_result['success']:
                    print(f"❌ Error al subir a GCS: {gcs_result['error']}")
                    messages.error(request, f'Error al subir archivo a almacenamiento: {gcs_result.get("error", "Error desconocido")}')
                    evaluation.delete()  # Limpiar evaluación si falló la carga
                    return render(request, 'evaluation.html', {'patient': patient, 'form': form})

                if not gcs_result.get('verified', False):
                    print("❌ Archivo no verificado en bucket, se cancela envío a API")
                    messages.error(request, 'No se pudo verificar el archivo en el bucket. Intenta nuevamente.')
                    evaluation.delete()
                    return render(request, 'evaluation.html', {'patient': patient, 'form': form})
                
                # Elegir la mejor referencia disponible del archivo en GCS
                # Prioridad: signed_url -> public_url (si es público) -> gs_uri
                gcs_file_url = (
                    gcs_result.get('signed_url')
                    or gcs_result.get('public_url')
                    or gcs_result.get('gs_uri')
                )

                if not gcs_file_url:
                    print("❌ No se obtuvo ninguna referencia de archivo en GCS")
                    messages.error(request, 'No se pudo obtener la URL/URI del archivo en GCS')
                    evaluation.delete()
                    return render(request, 'evaluation.html', {'patient': patient, 'form': form})

                if gcs_result.get('signed_url'):
                    file_url_type = 'signed_url'
                elif gcs_result.get('public_url'):
                    file_url_type = 'public_url'
                else:
                    file_url_type = 'gs_uri'

                # La API no soporta gs://; convertir a URL HTTPS de GCS.
                if file_url_type == 'gs_uri':
                    encoded_blob_name = quote(gcs_result['blob_name'], safe='/')
                    gcs_file_url = f"https://storage.googleapis.com/{os.getenv('GCS_BUCKET_NAME', '')}/{encoded_blob_name}"
                    file_url_type = 'https_gcs'
                    print("ℹ️ Convirtiendo gs:// a https://storage.googleapis.com/... para compatibilidad con la API")

                # Guardar información de GCS en la evaluación de forma tolerante a diferencias de esquema
                supports_gcs_file_url = True
                max_url_len = 2000
                try:
                    max_url_len = evaluation._meta.get_field('gcs_file_url').max_length or 2000
                except Exception:
                    supports_gcs_file_url = False
                    print("⚠️ Modelo Evaluation sin campo gcs_file_url; se guarda solo gcs_blob_name")

                if supports_gcs_file_url:
                    if gcs_file_url and len(gcs_file_url) <= max_url_len:
                        evaluation.gcs_file_url = gcs_file_url
                    else:
                        evaluation.gcs_file_url = None
                        print(f"⚠️ gcs_file_url excede {max_url_len} caracteres; se guarda solo gcs_blob_name")

                evaluation.gcs_blob_name = gcs_result['blob_name']
                evaluation.save()
                
                print(f"✅ Archivo subido a GCS")
                print(f"   Blob: {gcs_result['blob_name']}")
                print("   Verificación bucket: OK")
                print(f"   Tipo de referencia: {file_url_type}")
                print(f"   URL (primeros 80 chars): {gcs_file_url[:80]}...")
                
                # PASO 2: Enviar URL a la API del modelo de IA
                print(f"\n📡 PASO 2: Enviando URL a la API de análisis...")
                
                api_url = os.getenv('API_URL')
                api_timeout = int(os.getenv('API_TIMEOUT', '300'))
                api_key = os.getenv('API_KEY', '')
                ssl_verify = os.getenv('API_ENABLE_SSL_VERIFY', 'False').lower() == 'true'
                
                # Validar que API_URL esté configurado
                if not api_url:
                    print("❌ ERROR: API_URL no está configurado")
                    messages.error(request, 'Error de configuración: API_URL no definida')
                    return render(request, 'evaluation.html', {'patient': patient, 'form': form})
                
                # Preparar headers
                headers = {
                    'Authorization': f'Bearer {request.user.id}',
                    'Content-Type': 'application/json'
                }
                if api_key:
                    headers['X-API-Key'] = api_key
                
                # Preparar datos para enviar a API (schema exacto de /api/v1/analyze)
                payload = {
                    'file_url': gcs_file_url,  # URL firmada del archivo en GCS
                    'evaluation_id': str(evaluation.id),
                    'patient_id': str(patient.id),
                    'doctor_id': str(request.user.id),
                    'study_date': str(evaluation.study_date),
                    'observations': evaluation.observations or ''
                }
                
                print(f"📤 Enviando a API: {api_url}")
                print(f"   Payload: {json.dumps({k: v if k != 'file_url' else v[:50]+'...' for k,v in payload.items()})}")
                print(f"   Timeout: {api_timeout}s")

                def _submit_to_api_in_background(evaluation_id, api_url_bg, headers_bg, payload_bg, api_timeout_bg, ssl_verify_bg):
                    max_retries = 3
                    for attempt in range(max_retries):
                        try:
                            print(f"   [BG] Intento {attempt + 1}/{max_retries} para evaluación {evaluation_id}...")
                            response = requests.post(
                                api_url_bg,
                                json=payload_bg,
                                headers=headers_bg,
                                timeout=(30, api_timeout_bg),
                                verify=ssl_verify_bg
                            )

                            print(f"   [BG] Status Code: {response.status_code}")
                            if response.status_code in [200, 202]:
                                print(f"   [BG] Respuesta API (preview): {response.text[:300]}")
                                result = response.json()
                                task_id = (
                                    result.get('task_id')
                                    or result.get('taskId')
                                    or result.get('id')
                                    or (result.get('data', {}) or {}).get('task_id')
                                    or (result.get('data', {}) or {}).get('taskId')
                                    or (result.get('result', {}) or {}).get('task_id')
                                    or (result.get('result', {}) or {}).get('taskId')
                                    or response.headers.get('X-Task-Id')
                                )

                                evaluation_bg = Evaluation.objects.get(id=evaluation_id)
                                if task_id:
                                    evaluation_bg.task_id = task_id
                                    evaluation_bg.analysis_status = 'processing'
                                    evaluation_bg.save(update_fields=['task_id', 'analysis_status'])
                                    print(f"✅ [BG] URL enviada a API. Task ID: {task_id}")
                                else:
                                    evaluation_bg.analysis_status = 'failed'
                                    evaluation_bg.save(update_fields=['analysis_status'])
                                    print(f"❌ [BG] API respondió sin task_id para evaluación {evaluation_id}")
                                return

                            if attempt < max_retries - 1:
                                print(f"⚠️  [BG] Intento {attempt + 1} falló (status {response.status_code}). Reintentando...")
                                import time
                                time.sleep(2 ** attempt)
                                continue

                            print(f"❌ [BG] Error API: {response.status_code}")
                            print(f"   [BG] Respuesta: {response.text[:1000]}")
                            Evaluation.objects.filter(id=evaluation_id).update(analysis_status='failed')
                            return
                        except requests.exceptions.Timeout:
                            if attempt < max_retries - 1:
                                print(f"⚠️  [BG] Timeout en intento {attempt + 1}")
                                continue
                            Evaluation.objects.filter(id=evaluation_id).update(analysis_status='failed')
                            print(f"❌ [BG] Timeout final para evaluación {evaluation_id}")
                            return
                        except Exception as bg_error:
                            Evaluation.objects.filter(id=evaluation_id).update(analysis_status='failed')
                            print(f"❌ [BG] Error inesperado enviando a API: {bg_error}")
                            return

                background_thread = threading.Thread(
                    target=_submit_to_api_in_background,
                    args=(str(evaluation.id), api_url, headers.copy(), payload.copy(), api_timeout, ssl_verify),
                    daemon=True
                )
                background_thread.start()

                print("✅ Solicitud a API iniciada en segundo plano. Redirigiendo a processing...")
                return redirect(
                    'processing',
                    patient_id=patient.id,
                    task_id='pending',
                    evaluation_id=evaluation.id
                )
                
            except requests.exceptions.Timeout as e:
                print(f"❌ Timeout: {str(e)}")
                messages.error(request, f'Timeout al conectar con API ({api_timeout}s)')
            except requests.exceptions.ConnectionError as e:
                print(f"❌ Conexión rechazada: {str(e)}")
                messages.error(request, f'No se pudo conectar con la API en {api_url}')
            except Exception as e:
                print(f"❌ Error inesperado: {str(e)}")
                import traceback
                print(traceback.format_exc())
                messages.error(request, f'Error: {str(e)}')
        
        elif not zip_file:
            print("⚠ No se recibió archivo ZIP")
            messages.error(request, 'Por favor selecciona un archivo ZIP')
        else:
            print(f"❌ Formulario inválido: {form.errors}")
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
def get_evaluation_task_status(request, evaluation_id):
    """Retorna task_id y estado de una evaluación para polling inicial."""
    try:
        evaluation = get_object_or_404(Evaluation, id=evaluation_id)
        return JsonResponse({
            'success': True,
            'evaluation_id': str(evaluation.id),
            'task_id': evaluation.task_id,
            'analysis_status': evaluation.analysis_status,
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


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