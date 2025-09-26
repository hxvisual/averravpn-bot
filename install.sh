#!/usr/bin/env bash
set -euo pipefail

# Параметры
DOMAIN="bot.hexsad.ru"
EMAIL="dimatarasov825@gmail.com"   # укажите реальную почту; иначе будет использован --register-unsafely-without-email

# 0) Переменные окружения приложения (укажите значения здесь либо экспортируйте перед запуском)
BOT_TOKEN="${BOT_TOKEN:-}"
MARZBAN_BASE_URL="${MARZBAN_BASE_URL:-}"
MARZBAN_USERNAME="${MARZBAN_USERNAME:-}"
MARZBAN_PASSWORD="${MARZBAN_PASSWORD:-}"
YOOMONEY_WALLET_ID="${YOOMONEY_WALLET_ID:-}"
YOOMONEY_NOTIFICATION_SECRET="${YOOMONEY_NOTIFICATION_SECRET:-}"
INSTRUCTION_URL="${INSTRUCTION_URL:-}"
SUPPORT_URL="${SUPPORT_URL:-}"
WEBHOOK_HOST="${WEBHOOK_HOST:-0.0.0.0}"
WEBHOOK_PORT="${WEBHOOK_PORT:-8080}"

require_var() {
  local name="$1"
  local value="$2"
  if [ -z "$value" ]; then
    echo "Ошибка: переменная $name не задана. Укажите её в install.sh или через окружение и запустите скрипт снова." >&2
    exit 1
  fi
}

# Запрос значения у пользователя, если переменная не задана и терминал интерактивный
prompt_for_var() {
  local var_name="$1"
  local ask_text="$2"
  local is_secret="${3:-0}"
  local current_value="${!var_name:-}"
  if [ -z "$current_value" ] && [ -t 0 ]; then
    if [ "$is_secret" = "1" ]; then
      read -r -s -p "$ask_text: " input_val || true
      echo
    else
      read -r -p "$ask_text: " input_val || true
    fi
    eval "$var_name=\"${input_val}\""
  fi
}

# 1) Пакеты
sudo apt update -y
sudo apt install -y git python3 python3-venv python3-pip nginx

# 2) Директория и права
sudo mkdir -p /opt/averra-bot
RUN_USER="${SUDO_USER:-$USER}"
sudo chown "$RUN_USER":"$RUN_USER" /opt/averra-bot

cd /opt/averra-bot

# 2.5) Клонирование репозитория при необходимости (если каталог пуст и не git-репозиторий)
if [ ! -d ".git" ] && [ -z "$(ls -A)" ]; then
  git clone https://github.com/hxvisual/averravpn-bot.git .
fi

# 2.6) Проверка обязательных переменных и создание .env
# Запрос значений, если они не заданы в окружении (интерактивно)
prompt_for_var "BOT_TOKEN" "Введите BOT_TOKEN (токен бота)" 1
prompt_for_var "MARZBAN_BASE_URL" "Введите MARZBAN_BASE_URL (например, https://vpn.example.com)"
prompt_for_var "MARZBAN_USERNAME" "Введите MARZBAN_USERNAME"
prompt_for_var "MARZBAN_PASSWORD" "Введите MARZBAN_PASSWORD" 1
prompt_for_var "YOOMONEY_WALLET_ID" "Введите YOOMONEY_WALLET_ID"
prompt_for_var "YOOMONEY_NOTIFICATION_SECRET" "Введите YOOMONEY_NOTIFICATION_SECRET" 1
prompt_for_var "INSTRUCTION_URL" "Введите INSTRUCTION_URL (ссылка на инструкцию)"
prompt_for_var "SUPPORT_URL" "Введите SUPPORT_URL (ссылка на поддержку)"
prompt_for_var "WEBHOOK_HOST" "Введите WEBHOOK_HOST (по умолчанию 0.0.0.0)"
prompt_for_var "WEBHOOK_PORT" "Введите WEBHOOK_PORT (по умолчанию 8080)"

require_var "BOT_TOKEN" "$BOT_TOKEN"
require_var "MARZBAN_BASE_URL" "$MARZBAN_BASE_URL"
require_var "MARZBAN_USERNAME" "$MARZBAN_USERNAME"
require_var "MARZBAN_PASSWORD" "$MARZBAN_PASSWORD"
require_var "YOOMONEY_WALLET_ID" "$YOOMONEY_WALLET_ID"
require_var "YOOMONEY_NOTIFICATION_SECRET" "$YOOMONEY_NOTIFICATION_SECRET"
require_var "INSTRUCTION_URL" "$INSTRUCTION_URL"
require_var "SUPPORT_URL" "$SUPPORT_URL"

cat > .env <<EOF
BOT_TOKEN=$BOT_TOKEN
MARZBAN_BASE_URL=$MARZBAN_BASE_URL
MARZBAN_USERNAME=$MARZBAN_USERNAME
MARZBAN_PASSWORD=$MARZBAN_PASSWORD
YOOMONEY_WALLET_ID=$YOOMONEY_WALLET_ID
YOOMONEY_NOTIFICATION_SECRET=$YOOMONEY_NOTIFICATION_SECRET
INSTRUCTION_URL=$INSTRUCTION_URL
SUPPORT_URL=$SUPPORT_URL
WEBHOOK_HOST=$WEBHOOK_HOST
WEBHOOK_PORT=$WEBHOOK_PORT
EOF
chmod 600 .env

# 3) Виртуальное окружение и зависимости (код должен быть уже в /opt/averra-bot)
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
if [ -f requirements.txt ]; then
  pip install -r requirements.txt
else
  echo "requirements.txt не найден в /opt/averra-bot" >&2
  exit 1
fi

# 4) Systemd unit
sudo tee /etc/systemd/system/averra-bot.service >/dev/null <<'UNIT'
[Unit]
Description=Averra VPN 
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/averra-bot
Environment=PYTHONUNBUFFERED=1
ExecStart=/opt/averra-bot/.venv/bin/python /opt/averra-bot/main.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
UNIT

sudo systemctl daemon-reload
sudo systemctl enable averra-bot
sudo systemctl restart averra-bot
sudo systemctl status averra-bot | cat

# 5) Nginx (HTTP, прокси на Uvicorn)
sudo tee /etc/nginx/sites-available/averra-bot.conf >/dev/null <<NGINX
server {
    listen 80;
    server_name ${DOMAIN};

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host               \$host;
        proxy_set_header X-Real-IP          \$remote_addr;
        proxy_set_header X-Forwarded-For    \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto  \$scheme;
        proxy_read_timeout 120s;
    }
}
NGINX

sudo ln -sf /etc/nginx/sites-available/averra-bot.conf /etc/nginx/sites-enabled/averra-bot.conf
sudo nginx -t
sudo systemctl reload nginx

# 6) Certbot (TLS)
sudo apt install -y certbot python3-certbot-nginx

if [[ "$EMAIL" == *"@"* ]]; then
  sudo certbot --nginx -d "${DOMAIN}" --agree-tos -m "${EMAIL}" --redirect -n
else
  # если email не указан — регистрируемся без почты
  sudo certbot --nginx -d "${DOMAIN}" --agree-tos --register-unsafely-without-email --redirect -n
fi

# 7) Перевод HTTPS на порт 4444 и редирект с 80 на 4444
NGINX_CONF="/etc/nginx/sites-available/averra-bot.conf"
if [ -f "$NGINX_CONF" ]; then
  # Меняем порт прослушивания в HTTPS-сервере
  sudo sed -i 's/listen 443 ssl;/listen 4444 ssl;/g' "$NGINX_CONF"
  sudo sed -i 's/listen \[::\]:443 ssl;/listen [::]:4444 ssl;/g' "$NGINX_CONF"
  # Меняем редирект на указание порта 4444 (HTTP -> HTTPS:4444)
  sudo sed -i 's#return 301 https://\$host\$request_uri;#return 301 https://\$host:4444\$request_uri;#g' "$NGINX_CONF"

  # Открываем порт в UFW, если установлен
  if command -v ufw >/dev/null 2>&1; then
    sudo ufw allow 4444/tcp || true
  fi

  sudo nginx -t
  sudo systemctl reload nginx
fi

# Проверка
curl -I "https://${DOMAIN}:4444/health" | cat || true
echo "Готово. Если что-то не работает — проверьте: journalctl -u averra-bot -f и /var/log/nginx/error.log"

