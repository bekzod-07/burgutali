#!/usr/bin/env bash
# ==========================================================================
#  Ona tili RASH platformasi — server o'rnatish skripti
#  (Ubuntu 22.04 / 24.04 / 26.04). Domen: oybek-onatili.uz
#
#  Ishlatish (serverda, root sifatida):
#      cd /opt/onatili
#      chmod +x deploy.sh
#      sudo ./deploy.sh
#
#  Skript idempotent — yangilash uchun qayta ishga tushirish kifoya:
#      git pull && sudo ./deploy.sh
# ==========================================================================
set -euo pipefail

# --------------------------- Sozlamalar ----------------------------------
DOMAIN="${DOMAIN:-oybek-onatili.uz}"
APP_NAME="${APP_NAME:-onatili}"
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$APP_DIR/.venv"
GUNICORN_BIND="127.0.0.1:8001"
CERTBOT_EMAIL="${CERTBOT_EMAIL:-timeweb90@gmail.com}"

#: Panelga kirish uchun boshlang'ich hisob.
PANEL_USER="${PANEL_USER:-admin}"
PANEL_PASSWORD="${PANEL_PASSWORD:-admin}"

WEB_SERVICE="${APP_NAME}-web"
BOT_SERVICE="${APP_NAME}-bot"

log()  { echo -e "\e[1;32m==> $*\e[0m"; }
warn() { echo -e "\e[1;33m!!  $*\e[0m"; }
die()  { echo -e "\e[1;31mXATO: $*\e[0m" >&2; exit 1; }

[ "$(id -u)" -eq 0 ] || die "Skriptni root sifatida ishga tushiring: sudo ./deploy.sh"

# ----------------------- 1. Tizim paketlari ------------------------------
log "Tizim paketlari o'rnatilmoqda..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq python3 python3-venv python3-pip python3-dev \
    build-essential nginx certbot python3-certbot-nginx git curl >/dev/null

# --------------------- 1b. Python 3.12 -----------------------------------
# Django 4.2 va requirements.txt dagi numpy/scipy/pandas/Pillow versiyalari
# 3.12 uchun mo'ljallangan. Ubuntu 26.04 da tizimda faqat 3.14 bor, shuning
# uchun kerak bo'lsa `uv` orqali mustaqil 3.12 o'rnatiladi.
export PATH="/root/.local/bin:$PATH"

find_python() {
    for cand in python3.12 /root/.local/bin/python3.12; do
        command -v "$cand" >/dev/null 2>&1 && { command -v "$cand"; return 0; }
    done
    if command -v uv >/dev/null 2>&1; then
        uv python find 3.12 2>/dev/null && return 0
    fi
    return 1
}

PYTHON_BIN="$(find_python || true)"

if [ -z "$PYTHON_BIN" ]; then
    log "Python 3.12 topilmadi — uv orqali o'rnatilmoqda..."
    if ! command -v uv >/dev/null 2>&1; then
        curl -LsSf https://astral.sh/uv/install.sh | sh >/dev/null
    fi
    command -v uv >/dev/null 2>&1 || die "uv o'rnatilmadi — internetni tekshiring."
    uv python install 3.12 >/dev/null
    PYTHON_BIN="$(uv python find 3.12)" || die "Python 3.12 o'rnatilmadi."
fi

PYVER="$("$PYTHON_BIN" -c 'import sys; print(f"{sys.version_info[0]}.{sys.version_info[1]}")')"
log "Python: $PYTHON_BIN ($PYVER)"

# ----------------------- 2. Virtual muhit --------------------------------
log "Virtual muhit va bog'liqliklar..."
[ -d "$VENV_DIR" ] || "$PYTHON_BIN" -m venv "$VENV_DIR"
"$VENV_DIR/bin/pip" install --upgrade pip -q
"$VENV_DIR/bin/pip" install -r "$APP_DIR/requirements.txt" gunicorn -q

# ----------------------- 3. .env fayli -----------------------------------
if [ ! -f "$APP_DIR/.env" ]; then
    log ".env yaratilmoqda (.env.example asosida)..."
    cp "$APP_DIR/.env.example" "$APP_DIR/.env"

    SECRET_KEY="$("$VENV_DIR/bin/python" -c 'import secrets; print(secrets.token_urlsafe(50))')"
    sed -i \
        -e "s|^DJANGO_ENV=.*|DJANGO_ENV=prod|" \
        -e "s|^DJANGO_DEBUG=.*|DJANGO_DEBUG=0|" \
        -e "s|^DJANGO_SECRET_KEY=.*|DJANGO_SECRET_KEY=$SECRET_KEY|" \
        -e "s|^DJANGO_ALLOWED_HOSTS=.*|DJANGO_ALLOWED_HOSTS=$DOMAIN,www.$DOMAIN,127.0.0.1,localhost|" \
        -e "s|^DJANGO_CSRF_TRUSTED_ORIGINS=.*|DJANGO_CSRF_TRUSTED_ORIGINS=https://$DOMAIN,https://www.$DOMAIN|" \
        -e "s|^PUBLIC_BASE_URL=.*|PUBLIC_BASE_URL=https://$DOMAIN|" \
        "$APP_DIR/.env"
    chmod 600 "$APP_DIR/.env"
fi

# BOT_TOKEN to'ldirilganini tekshirish
if grep -q "^BOT_TOKEN=123456789:" "$APP_DIR/.env"; then
    warn "------------------------------------------------------------------"
    warn ".env faylida BOT_TOKEN hali to'ldirilmagan!"
    warn "Tahrirlang:  nano $APP_DIR/.env"
    warn "  - BOT_TOKEN     (@BotFather dan)"
    warn "  - BOT_USERNAME  (@ belgisisiz)"
    warn "  - ADMIN_IDS     (Telegram ID lar, vergul bilan)"
    warn "So'ng qayta ishga tushiring:  sudo ./deploy.sh"
    warn "------------------------------------------------------------------"
    exit 1
fi

# ----------------------- 4. Django tayyorlash ----------------------------
log "Migratsiyalar va statik fayllar..."
mkdir -p "$APP_DIR/data" "$APP_DIR/logs" "$APP_DIR/media" "$APP_DIR/staticfiles"
cd "$APP_DIR"
# collectstatic birinchi: production da `ManifestStaticFilesStorage`
# ishlatiladi va manifest yig'ilmaguncha statik manzillar hisoblanmaydi.
"$VENV_DIR/bin/python" manage.py collectstatic --noinput >/dev/null
"$VENV_DIR/bin/python" manage.py migrate --noinput

# Panelga kirish uchun hisob (yo'q bo'lsa yaratiladi, paroli yangilanadi).
log "Panel hisobi tekshirilmoqda ($PANEL_USER)..."
PANEL_USER="$PANEL_USER" PANEL_PASSWORD="$PANEL_PASSWORD" \
    "$VENV_DIR/bin/python" manage.py shell -c '
import os
from django.contrib.auth.models import User

name = os.environ["PANEL_USER"]
password = os.environ["PANEL_PASSWORD"]
account, created = User.objects.get_or_create(
    username=name,
    defaults={"is_staff": True, "is_superuser": True, "is_active": True},
)
account.is_staff = True
account.is_superuser = True
account.is_active = True
account.set_password(password)
account.save()
print("Panel hisobi:", "yaratildi" if created else "yangilandi", name)
'

# www-data o'qiy olishi uchun
chown -R www-data:www-data "$APP_DIR/staticfiles" "$APP_DIR/media"

# Loyiha /root ichida bo'lsa, nginx (www-data) papkalarga yetib borishi uchun
# /root ga faqat "o'tish" (execute) ruxsatini beramiz — o'qish ruxsati emas.
case "$APP_DIR" in
    /root/*)
        setfacl -m u:www-data:x /root 2>/dev/null || chmod 711 /root
        ;;
esac

# ----------------------- 5. systemd xizmatlari ---------------------------
log "systemd xizmatlari yozilmoqda..."

cat > "/etc/systemd/system/$WEB_SERVICE.service" <<EOF
[Unit]
Description=Ona tili RASH platformasi — Django web (gunicorn)
After=network.target

[Service]
Type=simple
WorkingDirectory=$APP_DIR
ExecStart=$VENV_DIR/bin/gunicorn config.wsgi:application \\
    --bind $GUNICORN_BIND --workers 3 --timeout 90 \\
    --access-logfile $APP_DIR/logs/gunicorn-access.log \\
    --error-logfile $APP_DIR/logs/gunicorn-error.log
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

cat > "/etc/systemd/system/$BOT_SERVICE.service" <<EOF
[Unit]
Description=Ona tili RASH platformasi — Telegram bot (aiogram)
After=network.target $WEB_SERVICE.service

[Service]
Type=simple
WorkingDirectory=$APP_DIR
ExecStart=$VENV_DIR/bin/python run_bot.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable "$WEB_SERVICE" "$BOT_SERVICE" >/dev/null 2>&1

# ----------------------- 6. Nginx ----------------------------------------
log "Nginx sozlanmoqda ($DOMAIN)..."

cat > "/etc/nginx/sites-available/$APP_NAME" <<EOF
server {
    listen 80;
    server_name $DOMAIN www.$DOMAIN;

    client_max_body_size 25M;

    # --- Xavfsizlik sarlavhalari ---
    # Eslatma: frame-ancestors/X-Frame-Options qo'yilmaydi — Mini App
    # Telegram Web mijozlarida iframe ichida ochiladi.
    add_header X-Content-Type-Options nosniff always;
    add_header Referrer-Policy same-origin always;
    add_header Permissions-Policy "camera=(), microphone=(), geolocation=(), payment=()" always;

    location /static/ {
        alias $APP_DIR/staticfiles/;
        expires 30d;
        access_log off;
    }

    location /media/ {
        alias $APP_DIR/media/;
        expires 7d;
        access_log off;
    }

    location / {
        proxy_pass http://$GUNICORN_BIND;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 90s;
    }
}
EOF

ln -sf "/etc/nginx/sites-available/$APP_NAME" "/etc/nginx/sites-enabled/$APP_NAME"
rm -f /etc/nginx/sites-enabled/default
nginx -t || die "Nginx konfiguratsiyasi xato."
systemctl reload nginx

# ----------------------- 7. SSL (Let's Encrypt) --------------------------
# Skript nginx konfiguratsiyasini har safar qayta yozadi, shuning uchun certbot
# ham har safar chaqiriladi: sertifikat mavjud bo'lsa --keep-until-expiring
# uni yangilamasdan, faqat SSL blokini konfiguratsiyaga qayta o'rnatadi.
log "SSL sozlanmoqda (Let's Encrypt)..."
if certbot --nginx -d "$DOMAIN" -d "www.$DOMAIN" \
    --non-interactive --agree-tos -m "$CERTBOT_EMAIL" \
    --redirect --keep-until-expiring; then
    log "SSL faol: https://$DOMAIN"
elif certbot --nginx -d "$DOMAIN" \
    --non-interactive --agree-tos -m "$CERTBOT_EMAIL" \
    --redirect --keep-until-expiring; then
    warn "www.$DOMAIN uchun DNS yozuvi topilmadi — faqat $DOMAIN uchun SSL o'rnatildi."
else
    warn "SSL olinmadi. DNS A-yozuvi shu server IP siga qaratilganini tekshiring,"
    warn "so'ng qo'lda ishga tushiring:  certbot --nginx -d $DOMAIN"
    warn "Hozircha sayt http://$DOMAIN da ishlayveradi."
fi

# ----------------------- 8. Xizmatlarni ishga tushirish ------------------
log "Xizmatlar (qayta) ishga tushirilmoqda..."
systemctl restart "$WEB_SERVICE" "$BOT_SERVICE"
sleep 2

echo
log "============================================================"
log "  O'rnatish yakunlandi!"
log "  Sayt:        https://$DOMAIN"
log "  Panel:       https://$DOMAIN/panel/kirish/  ($PANEL_USER / $PANEL_PASSWORD)"
log "  Web holati:  systemctl status $WEB_SERVICE"
log "  Bot holati:  systemctl status $BOT_SERVICE"
log "  Loglar:      journalctl -u $BOT_SERVICE -f"
log "               tail -f $APP_DIR/logs/gunicorn-error.log"
log "============================================================"
systemctl --no-pager --lines=0 status "$WEB_SERVICE" "$BOT_SERVICE" || true
