# ColonScan - Sistema Web de Análisis Médico Colonoscopía

Sistema web profesional desarrollado con **Django MVT** para gestión y análisis de imágenes médicas de colonoscopía mediante inteligencia artificial.

## Características Principales

- **Gestión de Pacientes**: Registro completo con historial de evaluaciones
- **Procesamiento de Imágenes**: Carga y procesamiento de archivos DICOM
- **Análisis con IA**: Envío automático a APIs de procesamiento de imágenes médicas
- **Dashboard Médico**: Panel interactivo con resumen de evaluaciones
- **Autenticación Segura**: Sesiones seguras solo para doctores
- **Reportes**: Visualización detallada de resultados por paciente

---

## Arquitectura: Django MVT

Este proyecto utiliza el patrón **Model-View-Template (MVT)** de Django:

```
ColonScan-App-Web/
│
├── colonscan_project/          # Configuración del proyecto Django
│   ├── settings.py             # Configuración (BD, apps, middleware)
│   ├── urls.py                 # Rutas principales
│   ├── wsgi.py                 # Servidor WSGI (Gunicorn)
│   └── asgi.py                 # Servidor ASGI
│
├── medical_service/            # Aplicación principal
│   ├── models.py               # M - Modelos de BD (User, Patient, Evaluation)
│   ├── views.py                # V - Vistas (lógica de negocio)
│   ├── urls.py                 # Rutas de la app
│   ├── forms.py                # Formularios Django
│   ├── admin.py                # Admin de Django
│   ├── migrations/             # Migraciones de BD
│   ├── management/             # Comandos personalizados
│   │   └── commands/
│   │       └── delete_patient.py
│   ├── templates/              # T - Templates HTML (UI)
│   │   ├── login.html
│   │   ├── dashboard.html
│   │   ├── detail.html
│   │   ├── evaluation.html
│   │   ├── evaluation_results.html
│   │   ├── processing.html
│   │   └── ...
│   ├── static/css/             # Estilos CSS
│   ├── static/media/           # Imágenes, documentos
│   └── templatetags/           # Filtros y tags personalizados
│
├── Dockerfile                  # Configuración Docker multi-stage
├── docker-compose.yml          # Orquestación Django y PostgreSQL
├── requirements.txt            # Dependencias Python
├── manage.py                   # Herramienta CLI de Django
└── seed_data.py                # Script para cargar datos de prueba

```

### Flujo MVT

1. **Routes (urls.py)** → Recibe la solicitud HTTP
2. **Views (views.py)** → Procesa la lógica y consulta Models
3. **Models (models.py)** → Consulta/modifica la base de datos
4. **Templates (*.html)** → Renderiza la respuesta al usuario

---

## Stack Tecnológico

| Componente | Tecnología | Versión |
|-----------|-----------|---------|
| **Backend** | Django | 5.0.1 |
| **Servidor Web** | Gunicorn | 21.2.0 |
| **Base de Datos** | PostgreSQL | 15 |
| **Python** | Python | 3.11 |
| **Contenedores** | Docker & Docker Compose | 29.0+ |
| **Static Files** | WhiteNoise | 6.6.0 |

### Dependencias Principales

```
Django==5.0.1              # Framework web
gunicorn==21.2.0          # Servidor WSGI producción
psycopg2-binary==2.9.9    # Driver PostgreSQL
whitenoise==6.6.0         # Servir archivos estáticos
python-dotenv==1.0.0      # Variables de entorno
```

---

## Inicio Rápido con Docker

### Requisitos

- Docker 29.0+
- Docker Compose 2.0+
- Git

### Paso 1: Clonar el Repositorio

```bash
git clone https://github.com/tu-usuario/ColonScan-App-Web.git
cd ColonScan-App-Web
```

### Paso 2: Configurar Variables de Entorno

```bash
cp .env.example .env
```

Edita `.env` con tus valores (Windows: `notepad .env`, Linux: `nano .env`):

```env
DEBUG=False
SECRET_KEY=tu-clave-secreta-segura-aqui
ALLOWED_HOSTS=localhost,127.0.0.1

DB_NAME=colonscan
DB_USER=postgres
DB_PASSWORD=postgres
DB_HOST=db
DB_PORT=5432

# ⚠️ IMPORTANTE: Configuración de la API de IA
# Estas URLs deben apuntar al servidor de la API ML (ColonScan-API-ML)
# que debe estar corriendo en paralelo en puerto 8001

# Para desarrollo LOCAL (sin Docker):
API_URL=http://localhost:8001/api/v1/analyse
API_BASE_URL=http://localhost:8001/api/v1

# Para DOCKER (Windows/Mac con Docker Desktop):
# Reemplaza las líneas anteriores con estas:
# API_URL=http://host.docker.internal:8001/api/v1/analyse
# API_BASE_URL=http://host.docker.internal:8001/api/v1

# Timeout para consultas a la API (en segundos)
API_TIMEOUT=300

# Clave API (si tu servidor la requiere)
API_KEY=

# SSL verification (False para desarrollo, True para producción)
API_ENABLE_SSL_VERIFY=False
```

**Nota Importante sobre API_URL y API_BASE_URL:**

| Entorno | API_URL | API_BASE_URL |
|---------|---------|--------------|
| **Desarrollo Local** | `http://localhost:8001/api/v1/analyse` | `http://localhost:8001/api/v1` |
| **Docker Desktop** | `http://host.docker.internal:8001/api/v1/analyse` | `http://host.docker.internal:8001/api/v1` |

- `API_URL`: Endpoint para enviar imágenes DICOM para análisis
- `API_BASE_URL`: Endpoint base para consultar estado de tareas completadas
- `host.docker.internal` es necesario en Docker para que los contenedores accedan a servicios en tu máquina host

### Paso 3: Construir la Imagen Docker

```bash
# Construir sin caché (primera vez)
docker build --no-cache -t colonscan:latest .
```

### Paso 4: Iniciar los Contenedores

```bash
# Iniciar Django + PostgreSQL en segundo plano
docker-compose up -d

# Verificar que ambos contenedores estén running
docker-compose ps
```

Resultado esperado:
```
NAME            STATUS      PORTS
colonscan_db    Up 10s      0.0.0.0:5432->5432/tcp
colonscan_web   Up 5s       0.0.0.0:8000->8000/tcp
```

### Paso 5: Ejecutar Migraciones de Base de Datos

```bash
# Las migraciones se ejecutan automáticamente al iniciar, 
# pero si necesitas ejecutarlas manualmente:
docker-compose exec web python manage.py migrate
```

### Paso 6: Cargar Datos de Prueba (Importante!)

```bash
docker-compose exec web python seed_data.py
```

**Resultado:**
```
✓ Doctor (demo@colonscan.com) creado con éxito.
✓ 6 pacientes creados para pruebas.
```

---

## Credenciales para Testing

### Usuario Doctor (Precargado con seed_data.py)

| Campo | Valor |
|-------|-------|
| **Usuario** | `demo@colonscan.com` |
| **Contraseña** | `demo123` |
| **Nombre** | Juan Pérez |
| **Rol** | Doctor / Superuser |

### Pacientes de Prueba

Se crean 6 pacientes de prueba con `seed_data.py`:

1. **María Elena González López** (52 años) - Estado: Pendiente
2. **Carlos Andrés Ramírez Pérez** (67 años) - Estado: Pendiente
3. **Ana Lucía Martínez Ruiz** (45 años) - Estado: Pendiente
4. **José Miguel Fernández** (59 años) - Estado: Pendiente
5. **Laura Sofía Sánchez Torres** (38 años) - Estado: Pendiente
6. **Roberto García Díaz** (71 años) - Estado: Pendiente

---

## Acceso a la Aplicación

Una vez que los contenedores estén corriendo:

### URLs Principales

```
http://localhost:8000/                    # Página de login
http://localhost:8000/dashboard/          # Dashboard principal (requiere login)
http://localhost:8000/admin/              # Panel administrativo Django
```

### Flujo de Login

1. Abre `http://localhost:8000/`
2. Ingresa las credenciales del doctor:
   - **Usuario**: `demo@colonscan.com`
   - **Contraseña**: `demo123`
3. Serás redirigido a `/dashboard/`
4. Podrás ver el listado de pacientes cargados

---

## Pantallas Principales

### 1. **Login** (`/`)
- Formulario de autenticación seguro
- Estilos responsivos

### 2. **Dashboard** (`/dashboard/`)
- Tabla de pacientes sinceramente
- Filtros y búsqueda
- Badges con estado de evaluación
- Botones de acción (ver detalles, evaluar)

### 3. **Detalle de Paciente** (`/detail/<id>/`)
- Información completa del paciente
- Historial de evaluaciones
- Estado de procesamientos

### 4. **Evaluación** (`/evaluation/<id>/`)
- Carga de imágenes DICOM
- Envío a API de procesamiento
- Pantalla de carga con animación

### 5. **Resultados** (`/evaluation_results/<task_id>/`)
- Visualización de hallazgos
- Reportes generados por IA
- Descarga de reportes

---

## Comandos Útiles

### Gestión de Contenedores

```bash
# Ver estado de contenedores
docker-compose ps

# Ver logs en tiempo real
docker-compose logs -f web

# Ver solo logs del web
docker-compose logs -f web

# Ver solo logs de la BD
docker-compose logs -f db

# Pausar contenedores (sin eliminar)
docker-compose stop

# Reanudar contenedores pausados
docker-compose start

# Detener y eliminar contenedores (mantiene datos)
docker-compose down

# Eliminar TODO (contenedores, volúmenes, datos)
docker-compose down -v
```

### Comandos Django en Contenedor

```bash
# Crear nuevo superuser
docker-compose exec web python manage.py createsuperuser

# Cargar datos de prueba
docker-compose exec web python seed_data.py

# Ejecutar migraciones
docker-compose exec web python manage.py migrate

# Crear migración por cambios en models
docker-compose exec web python manage.py makemigrations

# Recolectar archivos estáticos
docker-compose exec web python manage.py collectstatic --noinput

# Acceder a shell interactivo de Django
docker-compose exec web python manage.py shell

# Acceder a terminal de contenedor
docker-compose exec web bash
```

---

## Base de Datos

Las migraciones se aplican automáticamente al iniciar. Si lo haces manualmente:

```bash
docker-compose exec web python manage.py migrate
```

### Tablas Principales

- `auth_user` - Usuarios del sistema (Doctores)
- `medical_service_patient` - Pacientes
- `medical_service_evaluation` - Evaluaciones de pacientes
- `django_migrations` - Historial de migraciones

---

## Estructura de Proyectos - Modelos

### Patient (Paciente)
```python
- identification: CharField    # Cédula/RUT
- first_name: CharField        # Nombre
- middle_name: CharField       # Segundo nombre
- last_name: CharField         # Apellido
- age: IntegerField            # Edad
- status: CharField            # Estado: 'evaluated' o 'pending'
- last_evaluation_date: DateField  # Última evaluación
- created_at: DateTimeField    # Fecha de creación
- updated_at: DateTimeField    # Última actualización
```

### User (Doctor) - De Django Auth
```python
- username: CharField          # Email del doctor
- email: EmailField            # Email
- first_name: CharField        # Nombre
- last_name: CharField         # Apellido
- password: CharField          # Password (hash)
- is_superuser: Boolean        # Es admin
```

---

## Solución de Problemas

### El contenedor web no inicia

```bash
# Ver logs detallados
docker-compose logs web

# Reconstruir sin caché
docker-compose down -v
docker build --no-cache -t colonscan:latest .
docker-compose up -d
```

### Error de conexión a BD

```bash
# Esperar a que PostgreSQL esté listo (10-15 segundos)
docker-compose ps  # Verificar que 'db' esté 'Up'

# Reintentar migraciones
docker-compose exec web python manage.py migrate
```

### Errores 404 en archivos estáticos

WhiteNoise ya está configurado para servir CSS, JS e imágenes. Si persisten:

```bash
# Recolectar archivos estáticos
docker-compose exec web python manage.py collectstatic --noinput

# Reconstruir imagen
docker build --no-cache -t colonscan:latest .
docker-compose restart web
```

### seed_data.py falla

```bash
# Ejecutar con output detallado
docker-compose exec web python seed_data.py

# O si necesitas recrear datos (elimina BD)
docker-compose down -v
docker-compose up -d
docker-compose exec web python seed_data.py
```

---

## Notas Importantes

- ✅ WhiteNoise sirve archivos estáticos automáticamente
- ✅ Las migraciones se ejecutan al iniciar docker-compose
- ✅ Los datos persisten en volúmenes de Docker
- ✅ El archivo `.env` está en `.gitignore` (no se sube a GitHub)
- ⚠️ `seed_data.py` debe ejecutarse manualmente después de iniciar

---

## Desarrollo Local

Para desarrollo sin Docker:

```bash
# Crear entorno virtual
python -m venv venv
source venv/Scripts/activate  # Windows
source venv/bin/activate      # Linux/Mac

# Instalar dependencias
pip install -r requirements.txt

# Aplicar migraciones
python manage.py migrate

# Crear superuser
python manage.py createsuperuser

# Cargar datos de prueba
python seed_data.py

# Ejecutar servidor de desarrollo
python manage.py runserver
```

---

## Recursos

- [Django Documentation](https://docs.djangoproject.com/)
- [Docker Documentation](https://docs.docker.com/)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [WhiteNoise Documentation](https://whitenoise.readthedocs.io/)

---

**Preguntas o problemas?** Contacta al equipo de desarrollo.

## Tecnologías Utilizadas

| Componente | Versión |
|-----------|---------|
| **Django** | 6.0.2 |
| **Python** | 3.8+ |
| **PostgreSQL** | (configurado en settings) |
| **JavaScript** | Vanilla JS (Sin frameworks) |
| **CSS** | CSS3 con animaciones |

### Dependencias principales
- `psycopg2-binary` - Conector PostgreSQL
- `python-dotenv` - Gestión de variables de entorno
- `requests` - Cliente HTTP para API
- `asgiref` - Soporte asincrónico

---

## Requisitos Previos

Antes de comenzar, asegúrate de tener instalado:

1. **Python 3.8+**
   ```bash
   python --version  # Verificar versión
   ```

2. **PostgreSQL** (opcional, puede usar SQLite para desarrollo inicial)
   ```bash
   # Windows: Descargar desde https://www.postgresql.org/download/windows/
   # El puerto por defecto es 5432
   ```

3. **Git**
   ```bash
   git --version
   ```

4. **Administrador de paquetes pip**
   ```bash
   pip --version
   ```

---

## Guía de Instalación Paso a Paso

### Clonar el Repositorio

```bash
# Ir a la carpeta donde guardas tus proyectos
cd c:\Users\david\Documents\Github

# Clonar el repositorio (si aún no lo has hecho)
git clone https://github.com/tu-usuario/ColonScan-App-Web.git
cd ColonScan-App-Web
```

### Crear Entorno Virtual

```bash
# Crear entorno virtual
python -m venv venv

# Activar entorno virtual
# En Windows:
venv\Scripts\activate

# En macOS/Linux:
source venv/bin/activate

# Deberías ver (venv) al inicio de tu terminal
```

### Instalar Dependencias

```bash
# Actualizar pip
pip install --upgrade pip

# Instalar todas las dependencias del proyecto
pip install -r requirements.txt
```

### Configurar Variables de Entorno

Crea un archivo `.env` en la raíz del proyecto:

```bash
# En Windows PowerShell o Bash
# Copia el contenido siguiente en un archivo llamado .env

# Django Settings
SECRET_KEY=tu-clave-secreta-super-segura-aqui
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Database (Opción 1: SQLite para desarrollo)
# DATABASE_URL=sqlite:///db.sqlite3

# Database (Opción 2: PostgreSQL - descomentar si usas PostgreSQL)
# DATABASE_ENGINE=django.db.backends.postgresql
# DATABASE_NAME=colonscan_db
# DATABASE_USER=postgres
# DATABASE_PASSWORD=tu_contraseña
# DATABASE_HOST=localhost
# DATABASE_PORT=5432

# API de IA
API_BASE_URL=http://localhost:8001
API_KEY=tu_api_key_si_es_necesario
```

**Generar SECRET_KEY segura:**
```bash
# Python
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

### Aplicar Migraciones de Base de Datos

```bash
# Crear migraciones (si hay cambios nuevos)
python manage.py makemigrations

# Aplicar migraciones a la BD
python manage.py migrate

# Deberías ver "OK" o "Operations to perform: ..."
```

### Crear Superusuario (Admin)

```bash
# Crear usuario administrador
python manage.py createsuperuser

# Seguir los prompts:
# Username: admin
# Email: admin@colonscan.com
# Password: (ingresar contraseña segura)
# Password (again): (confirmar)
```

### Recolectar Archivos Estáticos (Opcional para desarrollo)

```bash
# En desarrollo esto es opcional, pero en producción es obligatorio
python manage.py collectstatic --noinput
```

---

## Ejecutar la Aplicación

### Servidor de Desarrollo

```bash
# Asegúrate de estar en la carpeta raíz del proyecto y venv activado
python manage.py runserver

# Deberías ver algo como:
# Starting development server at http://127.0.0.1:8000/

# Accede a: http://localhost:8000
```

---

## 🔌 Integración con API de IA

El proyecto requiere una API backend corriendo en paralelo para procesar las imágenes (ColonScan-API-ML):

### Ejecutar la API en Desarrollo Local

```bash
# En otra terminal, en la carpeta de la API
cd ../ColonScan-API-ML
python run.py

# La API debería estar en: http://localhost:8001
# Verifica con: curl http://localhost:8001/api/v1/health
```

### Configuración de URLs según el Entorno

**Desarrollo Local (sin Docker):**
```bash
# Tu .env debe contener:
API_URL=http://localhost:8001/api/v1/analyse
API_BASE_URL=http://localhost:8001/api/v1
```

**Docker Desktop (Windows/Mac):**
```bash
# Tu .env debe contener:
API_URL=http://host.docker.internal:8001/api/v1/analyse
API_BASE_URL=http://host.docker.internal:8001/api/v1
```

**⚠️ Importante:**
- `host.docker.internal` solo funciona en Docker Desktop (Windows/Mac)
- En Linux, usar la IP del host o configurar una red Docker compartida
- Asegúrate de que la API ML esté corriendo en puerto 8001 antes de iniciar Django

### Endpoints de API Esperados

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| POST | `/api/v1/analyze` | Enviar imágenes DICOM en ZIP para análisis |
| GET | `/api/v1/task/{task_id}` | Obtener estado del análisis y los resultados completados |

### Flujo de Comunicación

```
Usuario carga imágenes
         ↓
Django recibe ZIP
         ↓
Envía a API_URL (POST /api/v1/analyze)
         ↓
API retorna task_id
         ↓
JavaScript polling a API_BASE_URL (GET /api/v1/task/{task_id})
         ↓
Cuando status='completed' → muestra resultados
```

---

## Contacto y Soporte

Para reportar bugs o sugerir mejoras, por favor:
1. Crear un Issue en el repositorio
2. Describir el problema con claridad
3. Incluir pasos para reproducir

---

**Última actualización:** 24 de Marzo, 2026  
**Versión del Proyecto:** 1.0  
**Versión de Django:** 6.0.2

¡Listo para usar! Si tienes preguntas, consulta los archivos de documentación o revisa los errores en la terminal.
