"""
Servicio para interactuar con Google Cloud Storage con ADC (Application Default Credentials)
Maneja la carga de archivos ZIP a GCS y genera URLs firmadas
"""

import os
import time
import logging
from google.cloud import storage
from google.auth.exceptions import DefaultCredentialsError
from google.auth.transport.requests import Request
from datetime import timedelta

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
            # Si las credenciales no tienen clave privada (Compute Engine),
            # intentamos el flujo IAM con service_account_email + access_token.
            signed_url = None
            try:
                signed_url = blob.generate_signed_url(
                    version="v4",
                    expiration=timedelta(days=7),
                    method="GET"
                )
            except Exception as sign_error:
                logger.warning(
                    f"⚠️ No se pudo generar signed URL con flujo local: {str(sign_error)}"
                )

                # Fallback para credenciales de Compute Engine/metadata server.
                try:
                    creds = self.client._credentials
                    if getattr(creds, 'service_account_email', None):
                        creds.refresh(Request())
                        signed_url = blob.generate_signed_url(
                            version="v4",
                            expiration=timedelta(days=7),
                            method="GET",
                            service_account_email=creds.service_account_email,
                            access_token=creds.token,
                        )
                        logger.info("✅ Signed URL generada con IAM (Compute Engine)")
                except Exception as iam_sign_error:
                    logger.warning(
                        f"⚠️ No se pudo generar signed URL con IAM: {str(iam_sign_error)}"
                    )

            if self.make_public_on_upload:
                if self.uniform_bucket_level_access:
                    logger.warning(
                        "⚠️ No se puede usar make_public: Uniform Bucket-Level Access está habilitado"
                    )
                else:
                    try:
                        blob.make_public()
                        public_url = blob.public_url
                        is_public = True
                        logger.info(f"✅ Archivo marcado como público: {blob_name}")
                    except Exception as public_error:
                        logger.warning(
                            f"⚠️ No se pudo hacer público el archivo {blob_name}: {str(public_error)}"
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
            signed_url = blob.generate_signed_url(
                version="v4",
                expiration=timedelta(days=expiration_days),
                method="GET"
            )
            return signed_url
        except Exception as e:
            logger.error(f"❌ Error al generar URL firmada: {str(e)}")
            return None


# Instancia global del servicio GCS
gcs_service = GCSService()
