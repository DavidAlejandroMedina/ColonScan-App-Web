# Guía de Autenticación con Google Cloud Storage (ADC)

Este proyecto usa **Application Default Credentials (ADC)** para autenticarse con Google Cloud Storage. No necesitas pasar credenciales JSON en variables de entorno.

## Requisitos Previos

- Cuenta de Google Cloud con un proyecto existente
- Bucket de GCS creado
- Permiso en IAM para acceder al bucket (tu correo debe tener rol `roles/storage.objectCreator` o superior)
- Docker y Docker Compose instalados

## Configuración Inicial (Una sola vez)

### 1. Configurar el archivo `.env`

Copia `.env.example` a `.env` y edita:

```bash
cp .env.example .env
```

Reemplaza estos valores:

```env
GCS_ENABLED=True
GCS_BUCKET_NAME=tu-nombre-bucket-aqui
API_URL=http://host.docker.internal:8001/api/v1/analyze
API_BASE_URL=http://host.docker.internal:8001/api/v1
```

### 2. Iniciar el Backend

```bash
docker compose up -d
```

### 3. Autenticarse con Google Cloud (desde el contenedor)

**Paso 1: Obtener Project ID**

```bash
docker compose exec web gcloud projects list
```

Copia tu `PROJECT_ID`.

**Paso 2: Autenticarse**

```bash
docker compose exec -it web gcloud auth login
```

Esto abrirá una URL en el navegador. Completa el login con tu cuenta de Google.

**Paso 3: Configurar proyecto**

```bash
docker compose exec web gcloud config set project TU_PROJECT_ID
```

Reemplaza `TU_PROJECT_ID` con el ID que obtuviste en el Paso 1.

**Paso 4: Generar credenciales ADC**

```bash
docker compose exec -it web gcloud auth application-default login
```

Nuevamente, completa el login en el navegador.

**Paso 5: Establecer quota project**

```bash
docker compose exec web gcloud auth application-default set-quota-project TU_PROJECT_ID
```

**Paso 6: Verificar (opcional)**

```bash
docker compose exec web gcloud auth application-default print-access-token
```

Debería mostrar un token de acceso válido.

## ✅ Listo

Las credenciales se guardan en el volumen `gcloud-config` (/home/appuser/.config/gcloud) y **persisten** entre reinicios del contenedor.

## Si Bajas el Contenedor

Si ejecutas `docker compose down`:

```bash
docker compose down
```

Las credenciales se pierden. Cuando levantes de nuevo:

```bash
docker compose up -d
```

Debes repetir los **Pasos 4 y 5** (login ADC y quota project).

## Flujo de Uso

Una vez autenticado:

1. Accede a la aplicación en `http://localhost:8000`
2. Sube un archivo ZIP en el formulario de evaluación
3. El backend:
   - Sube el ZIP a Google Cloud Storage automáticamente
   - Obtiene una URL firmada del archivo
   - Envía la URL (no el archivo) a tu API de análisis
   - API lee el archivo directamente desde GCS
4. Resultados se guardan en la BD

## Permiso Necesario en IAM

Tu correo debe tener al menos estos permisos en GCP:

- `storage.objects.create` - Subir archivos
- `storage.objects.get` - Leer archivos (para generar URLs)
- `storage.objects.delete` - Eliminar (opcional)

Rol recomendado: **Storage Object Admin** en el bucket específico.

## Solución de Problemas

### Error: "No se encontraron credenciales GCS (ADC)"

**Solución:**
- Verifica que hiciste `gcloud auth application-default login`
- Reinicia el contenedor: `docker compose restart web`

### Error: "Access Denied" al subir a GCS

**Solución:**
- Verifica que tu correo tiene permisos en IAM sobre el bucket
- Espera unos minutos para que se propaguen los cambios de IAM

### Error: "Bucket not found"

**Solución:**
- Verifica el nombre del bucket en `.env` (`GCS_BUCKET_NAME`)
- Confirma que el bucket existe en tu proyecto GCP

## En Producción

Para producción, usa una **cuenta de servicio** en lugar de ADC de usuario:

1. Crea una cuenta de servicio en GCP
2. Descarga el JSON de credenciales
3. Monta el JSON en el contenedor (volumen o variable de entorno)
4. Usa `docker run -e GOOGLE_APPLICATION_CREDENTIALS=/secret/gcp-key.json ...`

## Referencias

- [Google Cloud Auth Documentation](https://cloud.google.com/docs/authentication)
- [Application Default Credentials](https://cloud.google.com/docs/authentication/provide-credentials-adc)
- [Google Cloud Storage Python Client](https://cloud.google.com/python/docs/reference/storage/latest)
