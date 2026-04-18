#!/usr/bin/env bash
set -euo pipefail

APP_ROOT="/opt/colonscan/app"
VENV_ROOT="/opt/colonscan/venv"
BRANCH="${1:-main}"

if [[ ! -d "$APP_ROOT/.git" ]]; then
  echo "ERROR: no se encontró repositorio git en $APP_ROOT"
  exit 1
fi

if [[ ! -x "$VENV_ROOT/bin/python" ]]; then
  echo "ERROR: no se encontró el virtualenv en $VENV_ROOT"
  echo "Ejecuta primero deploy/compute-engine/setup-vm.sh"
  exit 1
fi

echo "[1/8] Actualizando código desde origin/$BRANCH"
cd "$APP_ROOT"
git fetch origin
git checkout "$BRANCH"
git pull --ff-only origin "$BRANCH"

echo "[2/8] Instalando dependencias Python"
"$VENV_ROOT/bin/pip" install --upgrade pip
"$VENV_ROOT/bin/pip" install -r requirements.txt

echo "[3/8] Ejecutando migraciones"
"$VENV_ROOT/bin/python" manage.py migrate

echo "[4/8] Recolectando estáticos (templates se actualizan con git pull)"
"$VENV_ROOT/bin/python" manage.py collectstatic --noinput

echo "[5/8] Reiniciando Gunicorn"
sudo systemctl restart colonscan

echo "[6/8] Recargando Nginx"
sudo nginx -t
sudo systemctl reload nginx

echo "[7/8] Estado de servicios"
sudo systemctl --no-pager --full status colonscan | sed -n '1,20p' || true
sudo systemctl --no-pager --full status nginx | sed -n '1,20p' || true

echo "[8/8] Check de Django"
"$VENV_ROOT/bin/python" manage.py check

echo "Actualización completada para rama: $BRANCH"
