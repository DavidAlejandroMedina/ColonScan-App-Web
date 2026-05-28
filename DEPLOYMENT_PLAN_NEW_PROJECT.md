# Plan de Despliegue en Nuevo Proyecto GCP - Compute Engine + GCS + Cloud Run API

> **Ambiente:** Bash en Windows | **Región:** us-central1 | **Máquina:** e2-standard-4

---

## 📋 Fase 1: Preparar GCP (Proyecto, Autenticación, Permisos)

### 1.1 Configurar proyecto activo en gcloud CLI

```bash
# Listar proyectos disponibles
gcloud projects list

# Establecer el proyecto activo (reemplaza TU_PROJECT_ID)
gcloud config set project TU_PROJECT_ID

# Verificar que está configurado
gcloud config get-value project
```

### 1.2 Habilitar APIs necesarias

```bash
gcloud services enable compute.googleapis.com
gcloud services enable storage-api.googleapis.com
gcloud services enable storage-component.googleapis.com
gcloud services enable cloudbuild.googleapis.com
gcloud services enable cloudrun.googleapis.com
gcloud services enable iam.googleapis.com
```

### 1.3 Crear cuenta de servicio para la VM

```bash
# Crear la cuenta de servicio
gcloud iam service-accounts create colonscan-vm-sa \
  --display-name="ColonScan VM Service Account"

# Obtener el email de la cuenta (la necesitarás después)
gcloud iam service-accounts list --filter="displayName:ColonScan VM Service Account" \
  --format='value(email)'
# Guarda este email como: VM_SERVICE_ACCOUNT_EMAIL
```

### 1.4 Asignar permisos IAM a la cuenta de servicio

```bash
# Reemplaza TU_PROJECT_ID y VM_SERVICE_ACCOUNT_EMAIL
PROJECT_ID="TU_PROJECT_ID"
VM_SA_EMAIL="VM_SERVICE_ACCOUNT_EMAIL"

# Permiso para leer/escribir en Cloud Storage (bucket)
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:$VM_SA_EMAIL" \
  --role="roles/storage.objectAdmin"

# Permiso para actuar como la cuenta de servicio (opcional pero recomendado)
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:$VM_SA_EMAIL" \
  --role="roles/iam.serviceAccountUser"

# Permiso para loguear en Cloud Logging (recomendado)
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:$VM_SA_EMAIL" \
  --role="roles/logging.logWriter"
```

---

## 🗂️ Fase 2: Crear Infraestructura de Almacenamiento

### 2.1 Crear el bucket de GCS

```bash
# Reemplaza BUCKET_NAME con algo único (ej: colonscan-evidencias-2026)
BUCKET_NAME="colonscan-evidencias-2026"

gcloud storage buckets create "gs://$BUCKET_NAME" \
  --location=us-central1 \
  --uniform-bucket-level-access

echo "✅ Bucket creado: $BUCKET_NAME"
```

### 2.2 (Opcional) Crear carpeta dentro del bucket

```bash
# Crear estructura de carpetas (en GCS es solo un prefijo)
gcloud storage cp /dev/null "gs://$BUCKET_NAME/evaluations/ctc_scans/.keep"

echo "✅ Estructura de carpeta creada"
```

---

## 🖥️ Fase 3: Crear Compute Engine VM

### 3.1 Crear la VM

```bash
PROJECT_ID="TU_PROJECT_ID"
VM_NAME="colonscan-web-vm"
ZONE="us-central1-a"
VM_SA_EMAIL="VM_SERVICE_ACCOUNT_EMAIL"

gcloud compute instances create "$VM_NAME" \
  --zone="$ZONE" \
  --machine-type=e2-standard-4 \
  --image-family=ubuntu-2204-lts \
  --image-project=ubuntu-os-cloud \
  --boot-disk-size=50GB \
  --tags=http-server,https-server \
  --service-account="$VM_SA_EMAIL" \
  --scopes=https://www.googleapis.com/auth/cloud-platform

echo "✅ VM creada: $VM_NAME"
```

### 3.2 Crear reglas de firewall para HTTP/HTTPS

```bash
# Permitir HTTP
gcloud compute firewall-rules create allow-colonscan-http \
  --allow=tcp:80 \
  --target-tags=http-server \
  --description="Allow HTTP to ColonScan VM"

# Permitir HTTPS (opcional, para después)
gcloud compute firewall-rules create allow-colonscan-https \
  --allow=tcp:443 \
  --target-tags=https-server \
  --description="Allow HTTPS to ColonScan VM"

echo "✅ Reglas de firewall creadas"
```

### 3.3 Obtener la IP pública de la VM

```bash
ZONE="us-central1-a"
VM_NAME="colonscan-web-vm"

gcloud compute instances describe "$VM_NAME" \
  --zone="$ZONE" \
  --format='value(networkInterfaces[0].accessConfigs[0].natIP)'

# Guarda esta IP como: VM_EXTERNAL_IP
```

---

## 📦 Fase 4: Desplegar Aplicación en la VM

### 4.1 Conectarse a la VM por SSH

```bash
ZONE="us-central1-a"
VM_NAME="colonscan-web-vm"

gcloud compute ssh "$VM_NAME" --zone="$ZONE"
```

### 4.2 Una vez dentro de la VM, preparar el entorno

```bash
# Actualizar sistema
sudo apt-get update
sudo apt-get upgrade -y

# Instalar dependencias del sistema
sudo apt-get install -y \
  python3.10 \
  python3.10-venv \
  python3-pip \
  git \
  nginx \
  postgresql-client \
  curl \
  wget

# Crear directorios
sudo mkdir -p /opt/colonscan
sudo chown -R $USER:$USER /opt/colonscan
```

### 4.3 Clonar repositorio

```bash
cd /opt/colonscan
git clone https://github.com/TU_USUARIO/ColonScan-App-Web.git app
cd app

# Verificar que estás en la rama correcta
git branch -a
git checkout main  # O la rama que uses
```

### 4.4 Crear entorno virtual

```bash
cd /opt/colonscan/app

# Crear venv con Python 3.10
python3.10 -m venv /opt/colonscan/venv

# Activar venv
source /opt/colonscan/venv/bin/activate

# Actualizar pip
pip install --upgrade pip

# Instalar dependencias de la app
pip install -r requirements.txt
```

### 4.5 Configurar variables de entorno

```bash
cd /opt/colonscan/app

# Copiar archivo de ejemplo
cp .env.example .env

# Editar .env (usa nano o tu editor favorito)
nano .env
```

**Valores críticos a configurar en `.env`:**

```env
# Django
SECRET_KEY='genera-una-clave-aleatoria-larga'
DEBUG=False
ALLOWED_HOSTS=VM_EXTERNAL_IP,localhost
SESSION_COOKIE_SECURE=False
CSRF_COOKIE_SECURE=False

# Base de Datos (ELIGE UNA OPCIÓN)
# OPCIÓN A: PostgreSQL en Cloud SQL
DB_NAME=ColonScan
DB_USER=postgres
DB_PASSWORD=tu-contraseña-fuerte
DB_HOST=<IP_CLOUD_SQL_O_LOCALHOST>
DB_PORT=5432

# OPCIÓN B: SQLite (más fácil para inicio)
# Simplemente deja las variables de DB vacías y Django usará SQLite

# Google Cloud Storage
GCS_ENABLED=True
GCS_BUCKET_NAME=colonscan-evidencias-2026
GCS_EVIDENCE_PREFIX=evaluations/ctc_scans
GCS_VERIFY_MAX_RETRIES=3
GCS_VERIFY_RETRY_DELAY_SECONDS=1
GCS_MAKE_PUBLIC_ON_UPLOAD=False

# API del modelo de IA (Cloud Run)
API_URL=http://tu-cloud-run-api-url/api/v1/analyze
API_BASE_URL=http://tu-cloud-run-api-url/api/v1
API_TIMEOUT=900
API_ENABLE_SSL_VERIFY=True

# Upload
MAX_UPLOAD_MB=1024
FILE_UPLOAD_MAX_MEMORY_SIZE=10485760
```

### 4.6 Ejecutar setup script

```bash
cd /opt/colonscan/app

# Dar permisos de ejecución
chmod +x deploy/compute-engine/setup-vm.sh

# Ejecutar script
./deploy/compute-engine/setup-vm.sh
```

**El script debería:**
- Crear systemd service `colonscan`
- Configurar Nginx como reverse proxy
- Recolectar archivos estáticos
- Aplicar migraciones de base de datos

### 4.7 Verificar que los servicios estén corriendo

```bash
# Verificar servicio Django/Gunicorn
sudo systemctl status colonscan --no-pager

# Verificar Nginx
sudo systemctl status nginx --no-pager

# Ver logs si hay errores
sudo journalctl -u colonscan -n 50
```

---

## 🔐 Fase 5: Autenticarse con Google Cloud desde la VM

### 5.1 Autenticar como aplicación (ADC)

```bash
# Estando en la VM, usar gcloud CLI para autenticar
gcloud auth application-default login

# Configurar el proyecto
gcloud config set project TU_PROJECT_ID

# Establecer quota project
gcloud auth application-default set-quota-project TU_PROJECT_ID

# Verificar que funciona
gcloud auth application-default print-access-token
```

> **Nota:** Este paso crea credenciales en `~/.config/gcloud`. La aplicación Django usará estas credenciales automáticamente (ADC).

---

## ✅ Fase 6: Verificaciones y Pruebas

### 6.1 Probar API de la VM (desde tu máquina local)

```bash
# Reemplaza VM_EXTERNAL_IP
curl -I http://VM_EXTERNAL_IP/
```

Deberías ver:
```
HTTP/1.1 200 OK
```

### 6.2 Acceder a la UI

1. Abre navegador: `http://VM_EXTERNAL_IP`
2. Deberías ver la página de login

### 6.3 Crear usuario superadmin (si es necesario)

```bash
# Dentro de la VM, activar venv
ssh colonscan-web-vm --zone=us-central1-a

cd /opt/colonscan/app
source /opt/colonscan/venv/bin/activate

# Crear superusuario
python manage.py createsuperuser

# O usar seed script si está configurado
python manage.py seed_data
```

### 6.4 Prueba de carga en GCS

1. Logueate en la app
2. Ve a "Evaluación" → "Subir archivo"
3. Sube un ZIP pequeño (< 50MB para prueba rápida)
4. Verifica que el archivo aparece en GCS:

```bash
# Desde tu máquina local
gcloud storage ls gs://colonscan-evidencias-2026/evaluations/ctc_scans/
```

### 6.5 Verificar conexión a API de IA (Cloud Run)

```bash
# Desde la VM
curl -v http://tu-cloud-run-api-url/api/v1/health

# O desde tu máquina local si la API es pública
curl https://tu-cloud-run-api-url/api/v1/health
```

---

## 🔄 Fase 7: Actualizar Código (después del despliegue inicial)

Cuando necesites actualizar el código (templates, lógica, dependencias):

```bash
# Conectarse a la VM
gcloud compute ssh colonscan-web-vm --zone=us-central1-a

# Actualizar código
cd /opt/colonscan/app
git pull origin main

# Si cambiaron dependencias
source /opt/colonscan/venv/bin/activate
pip install -r requirements.txt

# Aplicar migraciones si hay
python manage.py migrate

# Recolectar estáticos si cambiaron CSS/JS
python manage.py collectstatic --noinput

# Reiniciar servicios
sudo systemctl restart colonscan
sudo systemctl reload nginx
```

O usar el script incluido:
```bash
cd /opt/colonscan/app
chmod +x deploy/compute-engine/update-vm.sh
./deploy/compute-engine/update-vm.sh main
```

---

## 🚨 Solución de Problemas Comunes

### Error: "Bucket not found"
- Verifica el nombre del bucket en `.env`
- Confirma que el bucket existe: `gcloud storage ls`

### Error: "Permission denied" en GCS
- Verifica que la cuenta de servicio tiene permisos:
  ```bash
  gcloud projects get-iam-policy TU_PROJECT_ID \
    --flatten="bindings[].members" \
    --filter="bindings.members:serviceAccount:VM_SERVICE_ACCOUNT_EMAIL"
  ```

### Servicio colonscan no inicia
```bash
# Ver logs detallados
sudo journalctl -u colonscan -n 100 -f
```

### Nginx retorna 502 Bad Gateway
```bash
# Verificar que Gunicorn está corriendo
sudo systemctl status colonscan

# Ver logs de Nginx
sudo tail -f /var/log/nginx/error.log
```

### ADC no funciona desde la VM
```bash
# Verificar credenciales
gcloud auth application-default print-access-token

# Si falla, reintentar login
gcloud auth application-default login
```

---

## 📝 Resumen de Variables Clave

Guarda estos valores después de crear recursos:

```bash
PROJECT_ID=tu-proyecto-gcp
VM_NAME=colonscan-web-vm
VM_EXTERNAL_IP=tu-ip-aqui
BUCKET_NAME=colonscan-evidencias-2026
VM_SERVICE_ACCOUNT_EMAIL=colonscan-vm-sa@tu-proyecto-gcp.iam.gserviceaccount.com
CLOUD_RUN_API_URL=https://tu-cloud-run-url
```

---

## 🎯 Checklist Final

- [ ] Proyecto GCP creado/seleccionado
- [ ] APIs habilitadas
- [ ] Cuenta de servicio creada con permisos IAM
- [ ] Bucket de GCS creado
- [ ] VM creado en Compute Engine
- [ ] Firewall rules creadas
- [ ] Código clonado en `/opt/colonscan/app`
- [ ] Venv creado y dependencias instaladas
- [ ] `.env` configurado correctamente
- [ ] Setup script ejecutado
- [ ] Servicios colonscan y nginx corriendo
- [ ] ADC configurado en la VM
- [ ] UI accesible en `http://VM_EXTERNAL_IP`
- [ ] Prueba de upload a GCS exitosa

---

**Próximos pasos:**
1. Ejecutar Fase 1-3 desde tu máquina local (gcloud commands)
2. Ejecutar Fase 4-5 conectándote a la VM
3. Verificar todo en Fase 6
