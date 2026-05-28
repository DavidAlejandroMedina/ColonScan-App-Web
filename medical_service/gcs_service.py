"""
Servicio para interactuar con Google Cloud Storage con ADC (Application Default Credentials)
Maneja la carga de archivos ZIP a GCS y genera URLs firmadas
"""

import os
import time
import logging
import base64
import hashlib
from google.cloud import storage
from google.auth.exceptions import DefaultCredentialsError
from google.auth.transport.requests import Request
from google.oauth2 import service_account
from google.auth import iam
import google.auth
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)


class GCSService:
    """Servicio para manejar operaciones con Google Cloud Storage usando ADC"""
    
    def __init__(self):
        """
        Inicializa el cliente de GCS usando Application Default Credentials (ADC)
        
        ADC busca credenciales en este orden:
        1. Variable GOOGLE_APPLICATION_CREDENTIALS (ruta a archivo JSON)
        2. ~/.config/gcloud/application_default_credentials.json (ADC de usuario)
        3. Credenciales de cuenta de servicio del ambiente
        """
        self.bucket_name = os.getenv('GCS_BUCKET_NAME')
        self.evidence_prefix = os.getenv('GCS_EVIDENCE_PREFIX', 'evaluations/ctc_scans')
        self.make_public_on_upload = os.getenv('GCS_MAKE_PUBLIC_ON_UPLOAD', 'False').lower() == 'true'
        self.enabled = False
        self.client = None
        self.bucket = None
        self.uniform_bucket_level_access = False
        
        if not self.bucket_name:
            logger.warning("⚠️  GCS_BUCKET_NAME no está configurado. GCS deshabilitado.")
            return
        
        try:
            # ADC se detecta automáticamente
            self.client = storage.Client()
            self.bucket = self.client.bucket(self.bucket_name)
            try:
                self.bucket.reload()
                ubla = self.bucket.iam_configuration.uniform_bucket_level_access_enabled
                self.uniform_bucket_level_access = bool(ubla)
            except Exception:
                self.uniform_bucket_level_access = False
            self.enabled = True
            logger.info(f"✅ Cliente GCS inicializado con ADC. Bucket: {self.bucket_name}")
            
        except DefaultCredentialsError as e:
            logger.error(
                f"❌ No se encontraron credenciales GCS (ADC):\n{str(e)}\n"
                f"Ejecuta en el contenedor: gcloud auth application-default login"
            )
            self.enabled = False
        except Exception as e:
            logger.error(f"❌ Error al inicializar cliente GCS: {str(e)}")
            self.enabled = False
    
    def upload_file(self, file_obj, evaluation_id, filename) -> dict:
        """
        Sube un archivo a GCS
        
        Args:
            file_obj: Objeto archivo de Django (InMemoryUploadedFile)
            evaluation_id: ID de la evaluación (para organizar en carpetas)
            filename: Nombre original del archivo
            
        Returns:
            dict: {
                'success': bool,
                'signed_url': str,  # URL firmada (válida 7 días)
                'blob_name': str,   # Ruta dentro del bucket
                'error': str (opcional)
            }
        """
        if not self.enabled or not self.client:
            return {
                'success': False,
                'error': 'GCS no está habilitado o no hay credenciales ADC'
            }
        
        try:
            # Crear ruta: evaluations/ctc_scans/{evaluation_id}/{filename}
            blob_name = f"{self.evidence_prefix}/{evaluation_id}/{filename}"
            blob = self.bucket.blob(blob_name)
            
            # Reiniciar el puntero del archivo
            file_obj.seek(0)
            
            # Obtener tamaño del archivo
            file_size = file_obj.size if hasattr(file_obj, 'size') else 0
            logger.info(
                f"📤 Subiendo archivo a GCS: {blob_name} "
                f"({file_size / (1024*1024):.2f}MB)"
            )
            
            # Subir el archivo
            blob.upload_from_file(
                file_obj,
                content_type='application/zip',
                timeout=600  # 10 minutos para archivos grandes
            )
            
            logger.info(f"✅ Archivo subido a GCS: {blob_name}")

            # Verificar que el archivo realmente exista en el bucket antes de continuar
            max_retries = int(os.getenv('GCS_VERIFY_MAX_RETRIES', '3'))
            retry_delay = float(os.getenv('GCS_VERIFY_RETRY_DELAY_SECONDS', '1'))
            file_exists = False

            for attempt in range(max_retries):
                if blob.exists(client=self.client):
                    file_exists = True
                    break
                if attempt < max_retries - 1:
                    time.sleep(retry_delay * (attempt + 1))

            if not file_exists:
                logger.error(
                    f"❌ El archivo no pudo confirmarse en GCS después de subirlo: {blob_name}"
                )
                return {
                    'success': False,
                    'error': 'No se pudo confirmar el archivo en el bucket después de la subida',
                    'blob_name': blob_name,
                    'verified': False
                }
            
            gs_uri = f"gs://{self.bucket_name}/{blob_name}"
            public_url = None
            is_public = False

            # Generar URL firmada válida por 7 días.
            # Se intentan múltiples métodos dependiendo de dónde se ejecute la aplicación
            logger.info("📝 Generando URL firmada para GCS...")
            signed_url = self.get_signed_url(blob_name, expiration_days=7)

            # Las URLs públicas no funcionan con uniform bucket-level access
            # Por lo tanto, siempre confiamos en URLs firmadas
            public_url = None
            is_public = False
            
            if self.uniform_bucket_level_access:
                logger.info(
                    "ℹ️ Uniform Bucket-Level Access habilitado. "
                    "Se usarán URLs firmadas en lugar de URLs públicas."
                )
            
            # Si no hay signed URL y el objeto no es público, la API no podrá leerlo por HTTPS.
            if not signed_url and not is_public:
                return {
                    'success': False,
                    'error': (
                        'No se pudo generar una URL accesible del archivo en GCS. '
                        'Revisa permisos IAM de firmado (signBlob) o acceso público del bucket.'
                    ),
                    'blob_name': blob_name,
                    'verified': True,
                }

            return {
                'success': True,
                'signed_url': signed_url,
                'public_url': public_url,
                'gs_uri': gs_uri,
                'is_public': is_public,
                'blob_name': blob_name,
                'verified': True,
                'error': None
            }
            
        except Exception as e:
            logger.error(f"❌ Error al subir archivo a GCS: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def delete_file(self, blob_name: str) -> bool:
        """
        Elimina un archivo de GCS
        
        Args:
            blob_name: Nombre del blob en GCS
            
        Returns:
            bool: True si se eliminó, False en caso contrario
        """
        if not self.enabled or not self.client:
            logger.warning("GCS no está habilitado")
            return False
            
        try:
            blob = self.bucket.blob(blob_name)
            blob.delete()
            logger.info(f"🗑️  Archivo eliminado de GCS: {blob_name}")
            return True
        except Exception as e:
            logger.error(f"❌ Error al eliminar archivo de GCS: {str(e)}")
            return False
    
    def _generate_signed_url_with_iam(self, blob_name: str, expiration_days: int = 7) -> str:
        """
        Genera URL firmada usando Google IAM API directamente (para Compute Engine)
        Construye el string a firmar y usa iam.serviceAccounts.signBlob
        
        Args:
            blob_name: Nombre del blob en GCS
            expiration_days: Días de validez de la URL
            
        Returns:
            str: URL firmada completamente construida
        """
        try:
            import json
            import requests
            from urllib.parse import quote_plus
            
            # Obtener el token de acceso del metadata service
            credentials, project_id = google.auth.default()
            
            # Obtener details de la cuenta de servicio
            try:
                from google.cloud import compute_v1
                compute_client = compute_v1.InstancesClient()
                instance_name = os.getenv('GCP_INSTANCE_NAME', 'colonscan-web-vm')
                zone = os.getenv('GCP_ZONE', 'us-central1-a')
                instance = compute_client.get(
                    project=project_id,
                    zone=zone,
                    resource=instance_name
                )
                service_account_email = instance.service_accounts[0].email if instance.service_accounts else None
            except Exception:
                # Fallback: intentar obtener del metadata service
                try:
                    resp = requests.get(
                        'http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/email',
                        headers={'Metadata-Flavor': 'Google'},
                        timeout=2
                    )
                    service_account_email = resp.text if resp.status_code == 200 else None
                except Exception:
                    service_account_email = None
            
            if not service_account_email:
                logger.warning("⚠️ No se pudo obtener service account email")
                return None
            
            # Construir el "string to sign" para la URL firmada de GCS
            expiration_datetime = datetime.now(timezone.utc) + timedelta(days=expiration_days)
            expiration_unix = int(expiration_datetime.timestamp())
            
            # El formato requerido para firmar una URL de GCS
            string_to_sign = "\n".join([
                "GET",
                "",  # Content-MD5
                "",  # Content-Type
                str(expiration_unix),
                f"/{self.bucket_name}/{blob_name}"
            ])
            
            logger.info(f"📝 Firmando string para URL: {service_account_email}")
            
            # Usar IAM signBlob para firmar
            refresh_request = Request()
            credentials.refresh(refresh_request)
            
            # Hacer request a IAM signBlob API
            iam_url = f"https://iam.googleapis.com/v1/projects/-/serviceAccounts/{service_account_email}:signBlob"
            headers = {
                'Authorization': f'Bearer {credentials.token}',
                'Content-Type': 'application/json'
            }
            
            body = {
                'bytesToSign': base64.b64encode(string_to_sign.encode('utf-8')).decode('utf-8')
            }
            
            response = requests.post(iam_url, json=body, headers=headers, timeout=10)
            
            if response.status_code != 200:
                logger.warning(f"⚠️ IAM signBlob failed: {response.status_code} - {response.text}")
                return None
            
            signature_data = response.json()
            signature_b64 = signature_data.get('signature', '')
            
            if not signature_b64:
                logger.warning("⚠️ No signature returned from IAM API")
                return None
            
            # Construir la URL firmada
            signed_url = (
                f"https://storage.googleapis.com/{self.bucket_name}/{blob_name}"
                f"?GoogleAccessId={quote_plus(service_account_email)}"
                f"&Expires={expiration_unix}"
                f"&Signature={quote_plus(signature_b64)}"
            )
            
            logger.info("✅ Signed URL generada con Google IAM API")
            return signed_url
            
        except Exception as e:
            logger.warning(f"⚠️ Error generando URL con IAM API: {str(e)}")
            return None

    def get_signed_url(self, blob_name: str, expiration_days: int = 7) -> str:
        """
        Genera una URL firmada para un archivo en GCS
        
        Args:
            blob_name: Nombre del blob en GCS
            expiration_days: Días de validez de la URL
            
        Returns:
            str: URL firmada o None
        """
        if not self.enabled or not self.client:
            return None
            
        try:
            blob = self.bucket.blob(blob_name)
            
            # Intento 1: Con credenciales locales (si tienen clave privada - service account file)
            try:
                signed_url = blob.generate_signed_url(
                    version="v4",
                    expiration=timedelta(days=expiration_days),
                    method="GET"
                )
                logger.info("✅ Signed URL generada con credenciales locales")
                return signed_url
            except Exception as e:
                logger.debug(f"Intento 1 fallido (credenciales locales): {str(e)}")
            
            # Intento 2: Con service account key desde archivo
            try:
                service_account_json = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
                
                if service_account_json and os.path.exists(service_account_json):
                    service_creds = service_account.Credentials.from_service_account_file(
                        service_account_json,
                        scopes=['https://www.googleapis.com/auth/devstorage.full_control']
                    )
                    signed_url = blob.generate_signed_url(
                        version="v4",
                        expiration=timedelta(days=expiration_days),
                        method="GET",
                        service_account_email=service_creds.service_account_email,
                        signing_credentials=service_creds
                    )
                    logger.info("✅ Signed URL generada con service account key file")
                    return signed_url
            except Exception as e:
                logger.debug(f"Intento 2 fallido (service account file): {str(e)}")
            
            # Intento 3: Usar Google IAM signBlob API (para Compute Engine)
            signed_url = self._generate_signed_url_with_iam(blob_name, expiration_days)
            if signed_url:
                return signed_url
            
            logger.error(f"❌ No se pudo generar URL firmada con ningún método disponible")
            return None
        except Exception as e:
            logger.error(f"❌ Error al generar URL firmada: {str(e)}")
            return None


# Instancia global del servicio GCS
gcs_service = GCSService()
