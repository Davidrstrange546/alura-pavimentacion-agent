#!/usr/bin/env bash
# ============================================================
# Despliegue del bot RAG (Normativa Pavimentacion MINVU) en una
# instancia Ubuntu de OCI (Always Free).
#
# Uso (desde cero, en la instancia OCI):
#   git clone https://github.com/Davidrstrange546/alura-pavimentacion-agent.git
#   cd alura-pavimentacion-agent
#   chmod +x deploy/setup_oci.sh
#   ./deploy/setup_oci.sh
#
# Es idempotente: se puede volver a correr para actualizar
# (git pull + reinstalar dependencias + re-ingesta + reiniciar el servicio).
# El bot corre en modo polling: no requiere abrir ningun puerto entrante
# en el Security List de OCI mas alla del SSH que ya usas para administrar
# la instancia.
# ============================================================
set -euo pipefail

# --- Opcional: swapfile de 2GB (descomentar si la instancia tiene poca RAM,
#     comun en la shape AMD "Micro" de 1GB del tier Always Free) ---
# if [ ! -f /swapfile ]; then
#   sudo fallocate -l 2G /swapfile
#   sudo chmod 600 /swapfile
#   sudo mkswap /swapfile
#   sudo swapon /swapfile
#   echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
# fi

INSTALL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERVICE_USER="$(whoami)"
SERVICE_NAME="alura-bot"

echo "==> Directorio de instalacion: $INSTALL_DIR"
echo "==> Usuario de servicio: $SERVICE_USER"

echo "==> Instalando dependencias del sistema..."
sudo apt-get update -y
sudo apt-get install -y python3-venv python3-pip git

cd "$INSTALL_DIR"

if [ -d .git ]; then
  echo "==> Actualizando repo (git pull)..."
  git pull
else
  echo "==> ADVERTENCIA: este script debe correrse desde dentro del repo ya clonado."
  exit 1
fi

echo "==> Creando/actualizando entorno virtual..."
if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt

if [ ! -f .env ]; then
  echo "==> Creando .env (las claves no quedan en el historial de la shell)..."
  read -rp "Pega tu GEMINI_API_KEY: " gemini_key
  read -rsp "Pega tu TELEGRAM_BOT_TOKEN: " telegram_token
  echo
  cat > .env <<EOF
TELEGRAM_BOT_TOKEN=${telegram_token}
GEMINI_API_KEY=${gemini_key}
EOF
  chmod 600 .env
  echo "==> .env creado y protegido (chmod 600)."
else
  echo "==> .env ya existe, no se modifica."
fi

if [ ! -d chroma_db ]; then
  echo "==> Corriendo ingesta del PDF a ChromaDB (primera vez)..."
  python ingest.py
else
  echo "==> chroma_db/ ya existe, no se re-ingesta (borrala manualmente si el PDF cambio)."
fi

echo "==> Instalando servicio systemd..."
sed -e "s|__INSTALL_DIR__|${INSTALL_DIR}|g" -e "s|__SERVICE_USER__|${SERVICE_USER}|g" \
  deploy/alura-bot.service | sudo tee "/etc/systemd/system/${SERVICE_NAME}.service" > /dev/null

sudo systemctl daemon-reload
sudo systemctl enable --now "${SERVICE_NAME}"
sudo systemctl restart "${SERVICE_NAME}"

echo "==> Listo. Estado del servicio:"
sudo systemctl status "${SERVICE_NAME}" --no-pager

echo ""
echo "Logs en vivo: sudo journalctl -u ${SERVICE_NAME} -f"
