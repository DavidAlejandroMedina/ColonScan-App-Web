# Comandos Rápidos - Despliegue en GCP (Copiar y Pegar)

> **Instrucciones:** Ejecuta estos comandos en orden. Reemplaza valores entre `<...>` con tus datos.

---

## 🔧 Valores a Configurar (CAMBIA ESTOS)

```bash
# REEMPLAZA ESTOS VALORES
PROJECT_ID="<tu-proyecto-gcp-aqui>"
REGION="us-central1"
ZONE="us-central1-a"
BUCKET_NAME="colonscan-evidencias-2026"
VM_NAME="colonscan-web-vm"
VM_SA_NAME="colonscan-vm-sa"
REPO_URL="https://github.com/<TU_USUARIO>/ColonScan-App-Web.git"
CLOUD_RUN_API_URL="https://<tu-cloud-run-url>.run.app"
```

---

## FASE 1: Configurar GCP (Ejecutar en tu máquina local - Bash)

### Paso 1.1: Establecer proyecto activo
```bash
gcloud config set project $PROJECT_ID
gcloud config get-value project
```

### Paso 1.2: Habilitar APIs
```bash
gcloud services enable compute.googleapis.com \
  storage-api.googleapis.com \
  storage-component.googleapis.com \
  cloudbuild.googleapis.com \
  cloudrun.googleapis.com \
  iam.googleapis.com
```

### Paso 1.3: Crear cuenta de servicio
```bash
gcloud iam service-accounts create $VM_SA_NAME \
  --display-name="ColonScan VM Service Account"

# Obtener email de la cuenta de servicio
VM_SA_EMAIL=$(gcloud iam service-accounts list \
  --filter="displayName:ColonScan VM Service Account" \
  --format='value(email)')

echo "Email de la cuenta de servicio: $VM_SA_EMAIL"
```

### Paso 1.4: Asignar permisos IAM
```bash
VM_SA_EMAIL=$(gcloud iam service-accounts list \
  --filter="displayName:ColonScan VM Service Account" \
  --format='value(email)')

# Storage
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:$VM_SA_EMAIL" \
  --role="roles/storage.objectAdmin"

# Logging
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:$VM_SA_EMAIL" \
  --role="roles/logging.logWriter"
```

---

## FASE 2: Crear Infraestructura (GCS + Firewall)

### Paso 2.1: Crear bucket de GCS
```bash
gcloud storage buckets create "gs://$BUCKET_NAME" \
  --location=$REGION \
  --uniform-bucket-level-access

echo "✅ Bucket creado: gs://$BUCKET_NAME"
```

### Paso 2.2: Crear estructura de carpetas (opcional)
```bash
gcloud storage cp /dev/null "gs://$BUCKET_NAME/evaluations/ctc_scans/.keep"
echo "✅ Estructura creada"
```

### Paso 2.3: Crear reglas de firewall
```bash
gcloud compute firewall-rules create allow-colonscan-http \
  --allow=tcp:80 \
  --target-tags=http-server \
  --description="Allow HTTP to ColonScan"

gcloud compute firewall-rules create allow-colonscan-https \
  --allow=tcp:443 \
  --target-tags=https-server \
  --description="Allow HTTPS to ColonScan"

echo "✅ Firewall rules creadas"
```

---

## FASE 3: Crear VM en Compute Engine

### Paso 3.1: Crear VM
```bash
VM_SA_EMAIL=$(gcloud iam service-accounts list \
  --filter="displayName:ColonScan VM Service Account" \
  --format='value(email)')

gcloud compute instances create "$VM_NAME" \
  --zone="$ZONE" \
  --machine-type=e2-standard-4 \
  --image-family=ubuntu-2204-lts \
  --image-project=ubuntu-os-cloud \
  --boot-disk-size=50GB \
  --tags=http-server,https-server \
  --service-account="$VM_SA_EMAIL" \
  --scopes=https://www.googleapis.com/auth/cloud-platform

echo "✅ VM creada. Esperando que inicie..."
sleep 30
```

### Paso 3.2: Obtener IP externa de la VM
```bash
VM_EXTERNAL_IP=$(gcloud compute instances describe "$VM_NAME" \
  --zone="$ZONE" \
  --format='value(networkInterfaces[0].accessConfigs[0].natIP)')

echo "📍 IP Externa: $VM_EXTERNAL_IP"
```

---

## FASE 4: Desplegar en la VM (Ejecutar dentro de la VM via SSH)

### Paso 4.1: Conectarse a la VM
```bash
gcloud compute ssh "$VM_NAME" --zone="$ZONE"
```

### Paso 4.2: Una vez dentro de la VM, actualizar el sistema
```bash
sudo apt-get update
sudo apt-get upgrade -y
sudo apt-get install -y \
  python3.10 \
  python3.10-venv \
  python3-pip \
  git \
  nginx \
  postgresql-client \
  curl \
  wget
```

### Paso 4.3: Crear directorios y clonar repo
```bash
sudo mkdir -p /opt/colonscan
sudo chown -R $USER:$USER /opt/colonscan

cd /opt/colonscan
git clone https://github.com/TU_USUARIO/ColonScan-App-Web.git app
cd app

git branch -a
git checkout main
```

### Paso 4.4: Crear venv e instalar dependencias
```bash
cd /opt/colonscan/app

python3.10 -m venv /opt/colonscan/venv
source /opt/colonscan/venv/bin/activate

pip install --upgrade pip
pip install -r requirements.txt
```

### Paso 4.5: Configurar .env (MÁS IMPORTANTE ⚠️)
```bash
cd /opt/colonscan/app
cp .env.example .env

# Editar con nano (o tu editor favorito)
nano .env
```

**Valores esenciales a cambiar en .env:**

```env
SECRET_KEY='genera-una-clave-aleatoria-larga-aqui-min-32-chars'
DEBUG=False
ALLOWED_HOSTS=<VM_EXTERNAL_IP>,localhost,127.0.0.1

# Base de datos (elige una opción)
# OPCIÓN 1: SQLite (fácil para inicio)
# (dejar vacías las variables DB_*)

# OPCIÓN 2: PostgreSQL en Cloud SQL
# DB_NAME=ColonScan
# DB_USER=postgres
# DB_PASSWORD=contraseña-fuerte
# DB_HOST=<ip-cloud-sql-aqui>
# DB_PORT=5432

# Google Cloud Storage (IMPORTANTE)
GCS_ENABLED=True
GCS_BUCKET_NAME=<tu-bucket-name>
GCS_EVIDENCE_PREFIX=evaluations/ctc_scans
GCS_MAKE_PUBLIC_ON_UPLOAD=False

# API del modelo de IA
API_URL=<CLOUD_RUN_API_URL>/api/v1/analyze
API_BASE_URL=<CLOUD_RUN_API_URL>/api/v1
API_ENABLE_SSL_VERIFY=True

# Upload
MAX_UPLOAD_MB=1024
```

### Paso 4.6: Ejecutar setup script
```bash
cd /opt/colonscan/app
chmod +x deploy/compute-engine/setup-vm.sh
./deploy/compute-engine/setup-vm.sh

# Esperar a que termine y verificar
sleep 10
sudo systemctl status colonscan --no-pager
sudo systemctl status nginx --no-pager
```

---

## FASE 5: Autenticar con GCP (Dentro de la VM)

### Paso 5.1: Configurar ADC
```bash
gcloud config set project $PROJECT_ID
gcloud auth application-default login

# Establecer quota project
gcloud auth application-default set-quota-project $PROJECT_ID

# Verificar (debería mostrar un token)
gcloud auth application-default print-access-token
```

### Paso 5.2: Salir de la VM
```bash
exit
```

---

## FASE 6: Verificaciones (Desde tu máquina local)

### Verificar que la app está corriendo
```bash
VM_EXTERNAL_IP=$(gcloud compute instances describe "$VM_NAME" \
  --zone="$ZONE" \
  --format='value(networkInterfaces[0].accessConfigs[0].natIP)')

curl -I http://$VM_EXTERNAL_IP/
# Debería mostrar "HTTP/1.1 200 OK"
```

### Verificar bucket de GCS
```bash
gcloud storage ls gs://$BUCKET_NAME/
```

### Verificar que la API de IA es accesible
```bash
# Si la API es pública
curl -I $CLOUD_RUN_API_URL/api/v1/health
```

---

## FASE 7: Crear Admin (Dentro de la VM via SSH)

```bash
gcloud compute ssh "$VM_NAME" --zone="$ZONE"

# Dentro de la VM:
cd /opt/colonscan/app
source /opt/colonscan/venv/bin/activate

# Opción A: Crear superusuario manualmente
python manage.py createsuperuser

# Opción B: Usar seed script (si está configurado)
export DEMO_ADMIN_USERNAME=admin
export DEMO_ADMIN_EMAIL=admin@colonscan.local
export DEMO_ADMIN_PASSWORD=Admin12345!
python manage.py seed_data

exit
```

---

## 🔄 Actualizar código después del despliegue

```bash
gcloud compute ssh "$VM_NAME" --zone="$ZONE"

# Dentro de la VM:
cd /opt/colonscan/app
git pull origin main

source /opt/colonscan/venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput

sudo systemctl restart colonscan
sudo systemctl reload nginx

exit
```

---

## 🚨 Debugging

### Ver logs del servicio Django
```bash
gcloud compute ssh "$VM_NAME" --zone="$ZONE"
sudo journalctl -u colonscan -n 50 -f
```

### Ver logs de Nginx
```bash
gcloud compute ssh "$VM_NAME" --zone="$ZONE"
sudo tail -f /var/log/nginx/error.log
```

### Probar conexión a GCS desde la VM
```bash
gcloud compute ssh "$VM_NAME" --zone="$ZONE"
gcloud storage ls gs://$BUCKET_NAME/
```

---

## 📝 Cheatsheet de URLs

Una vez desplegado:

```
Web App: http://<VM_EXTERNAL_IP>/
Admin: http://<VM_EXTERNAL_IP>/admin/
Login: http://<VM_EXTERNAL_IP>/accounts/login/
```

---

## ✅ Checklist Final

```
ANTES DE DESPLEGAR:
[ ] Reemplazé PROJECT_ID, BUCKET_NAME, REPO_URL, etc.
[ ] Mi proyecto GCP está creado
[ ] Estoy autenticado en gcloud CLI

FASE 1-3 (Desde máquina local):
[ ] APIs habilitadas
[ ] Cuenta de servicio creada
[ ] Bucket de GCS creado
[ ] Firewall rules creadas
[ ] VM creada

FASE 4-5 (Dentro de la VM):
[ ] Repositorio clonado
[ ] Venv creado
[ ] Dependencias instaladas
[ ] .env configurado
[ ] Setup script ejecutado
[ ] ADC configurado

FASE 6 (Verificaciones):
[ ] App accesible en http://VM_EXTERNAL_IP/
[ ] Bucket aparece en gcloud storage ls
[ ] Admin creado

LISTO PARA PRODUCCIÓN:
[ ] Prueba de upload exitosa
[ ] Archivos en GCS
[ ] API respondiendo
```
