#!/usr/bin/env bash
set -euo pipefail

APP_ROOT="/opt/colonscan/app"
VENV_ROOT="/opt/colonscan/venv"
SERVICE_FILE="/etc/systemd/system/colonscan.service"
NGINX_SITE="/etc/nginx/sites-available/colonscan"

echo "[1/8] Installing system dependencies"
sudo apt-get update
sudo apt-get install -y python3 python3-venv python3-pip nginx git build-essential libpq-dev

echo "[2/8] Preparing directories"
sudo mkdir -p /opt/colonscan
sudo chown -R "$USER":"$USER" /opt/colonscan

if [[ ! -d "$APP_ROOT/.git" ]]; then
  echo "ERROR: Application repository was not found at $APP_ROOT"
  echo "Clone your repo first, for example:"
  echo "  sudo mkdir -p /opt/colonscan && sudo chown -R $USER:$USER /opt/colonscan"
  echo "  git clone <your-repo-url> $APP_ROOT"
  exit 1
fi

echo "[3/8] Creating virtual environment"
python3 -m venv "$VENV_ROOT"
source "$VENV_ROOT/bin/activate"
pip install --upgrade pip
pip install -r "$APP_ROOT/requirements.txt"

echo "[4/8] Preparing .env"
if [[ ! -f "$APP_ROOT/.env" ]]; then
  cp "$APP_ROOT/deploy/compute-engine/compute-engine.env.example" "$APP_ROOT/.env"
  echo "Created $APP_ROOT/.env from template. Update secrets before starting service."
fi

echo "[5/8] Running Django setup"
cd "$APP_ROOT"
"$VENV_ROOT/bin/python" manage.py migrate
"$VENV_ROOT/bin/python" manage.py collectstatic --noinput

echo "[6/8] Installing systemd service"
sudo cp "$APP_ROOT/deploy/compute-engine/colonscan.service" "$SERVICE_FILE"
sudo systemctl daemon-reload
sudo systemctl enable colonscan
sudo systemctl restart colonscan

echo "[7/8] Installing Nginx site"
sudo cp "$APP_ROOT/deploy/compute-engine/nginx-colonscan.conf" "$NGINX_SITE"
sudo ln -sf "$NGINX_SITE" /etc/nginx/sites-enabled/colonscan
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl restart nginx

echo "[8/8] Health checks"
sudo systemctl --no-pager --full status colonscan || true
sudo systemctl --no-pager --full status nginx || true

echo "Done. If you changed .env, restart service with: sudo systemctl restart colonscan"
