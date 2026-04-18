# Deploy en Compute Engine para uploads pesados

Este despliegue permite que el backend Django reciba archivos grandes y luego los suba al bucket GCS, evitando el límite de tamaño de request de Cloud Run.

## Arquitectura propuesta

1. Usuario sube ZIP al backend Django en la VM.
2. Nginx acepta cargas grandes y las pasa a Gunicorn.
3. Django procesa y sube a GCS usando la cuenta de servicio de la VM.
4. Django invoca tu API de IA con la URL/metadata del archivo.

## 1) Crear VM

Ejemplo (ajusta proyecto/region/subred):

```bash
gcloud compute instances create colonscan-web-vm \
  --zone=us-central1-a \
  --machine-type=e2-standard-4 \
  --image-family=ubuntu-2204-lts \
  --image-project=ubuntu-os-cloud \
  --boot-disk-size=50GB \
  --tags=http-server,https-server \
  --service-account=<VM_SERVICE_ACCOUNT_EMAIL> \
  --scopes=https://www.googleapis.com/auth/cloud-platform
```

## 2) Permisos IAM para la cuenta de servicio de la VM

Concede mínimo:

- roles/storage.objectAdmin sobre el bucket de evidencias.
- roles/cloudsql.client si conectas por Cloud SQL Auth Proxy.

## 3) Abrir puertos firewall

```bash
gcloud compute firewall-rules create allow-colonscan-http \
  --allow=tcp:80 \
  --target-tags=http-server
```

## 4) Preparar app en la VM

```bash
ssh <VM_NAME>
sudo mkdir -p /opt/colonscan
sudo chown -R $USER:$USER /opt/colonscan
git clone <REPO_URL> /opt/colonscan/app
cd /opt/colonscan/app
chmod +x deploy/compute-engine/setup-vm.sh
./deploy/compute-engine/setup-vm.sh
```

## 5) Configurar variables de entorno

Edita:

- /opt/colonscan/app/.env

Usa como base:

- /opt/colonscan/app/deploy/compute-engine/compute-engine.env.example

Campos críticos:

- ALLOWED_HOSTS
- CSRF_TRUSTED_ORIGINS
- DB_HOST/DB_PORT/credenciales
- GCS_BUCKET_NAME
- API_URL/API_BASE_URL
- MAX_UPLOAD_MB

## 6) Ajustar tamaño máximo permitido

Dos límites deben coincidir:

1. Nginx en deploy/compute-engine/nginx-colonscan.conf
   - client_max_body_size 1024M;
2. Django en colonscan_project/settings.py
   - MAX_UPLOAD_MB=1024 (por .env)

Si deseas 2GB, cambia ambos a 2048M y 2048.

## 7) Reiniciar servicios

```bash
sudo systemctl restart colonscan
sudo systemctl restart nginx
sudo systemctl status colonscan --no-pager
sudo systemctl status nginx --no-pager
```

## 7.1) Actualizar código en la VM (templates + lógica)

Cuando ya tienes la VM funcionando y quieres aplicar cambios nuevos del repositorio (Python, HTML, JS, CSS, etc.), usa este flujo:

```bash
ssh <VM_NAME>
cd /opt/colonscan/app
git status
git pull --ff-only origin main
/opt/colonscan/venv/bin/pip install -r requirements.txt
/opt/colonscan/venv/bin/python manage.py migrate
/opt/colonscan/venv/bin/python manage.py collectstatic --noinput
sudo systemctl restart colonscan
sudo systemctl reload nginx
```

Notas:

- `templates`: se actualizan con `git pull`.
- `lógica backend`: se actualiza con `git pull` y se aplica al reiniciar `colonscan`.
- `static`: si cambias CSS/JS, ejecuta `collectstatic` para que Nginx sirva la versión nueva.
- `requirements.txt`: si cambió, siempre reinstala dependencias.

También puedes ejecutar el script incluido:

```bash
cd /opt/colonscan/app
chmod +x deploy/compute-engine/update-vm.sh
./deploy/compute-engine/update-vm.sh main
```

Si quieres, puedes dejar la VM siempre en la rama correcta (por ejemplo `main`) y evitar mezclas de código local.

## 8) Verificaciones rápidas

```bash
curl -I http://<VM_EXTERNAL_IP>/
```

Prueba UI:

1. Login
2. Registro de paciente
3. Subida de ZIP grande (>120MB)
4. Confirmar que se crea objeto en GCS
5. Confirmar cambio de estado en procesamiento

## 9) Recomendaciones de producción

- Agrega HTTPS con Nginx + Certbot.
- Usa dominio dedicado y fija ALLOWED_HOSTS/CSRF_TRUSTED_ORIGINS.
- Configura backup/snapshot de disco.
- Activa Cloud Monitoring + log rotation.
- Considera migrar jobs pesados a cola (Celery/Cloud Tasks) si aumenta el volumen.
