# O‘rnatish va ishga tushirish

## 1. Talablar

* **Python 3.12** yoki undan yuqori
* (ixtiyoriy) **PostgreSQL 13+** — standart holatda SQLite ishlatiladi
* Telegram bot tokeni ([@BotFather](https://t.me/BotFather))

---

## 2. Muhitni tayyorlash

```bash
cd rashmodel_matematikabot

python -m venv env
env\Scripts\activate            # Windows
# source env/bin/activate       # Linux / macOS

pip install --upgrade pip
pip install -r requirements.txt
```

---

## 3. Sozlamalar (`.env`)

`.env.example` faylini `.env` nomi bilan nusxalang va to‘ldiring:

```bash
copy .env.example .env          # Windows
cp .env.example .env            # Linux / macOS
```

### Majburiy qiymatlar

| O‘zgaruvchi | Tavsif |
|-------------|--------|
| `BOT_TOKEN` | @BotFather bergan token |
| `BOT_USERNAME` | bot username (`@` belgisisiz) — deep-link uchun |
| `ADMIN_IDS` | asosiy adminlarning Telegram ID lari, vergul bilan |
| `REQUIRED_CHANNEL` | majburiy obuna kanali (`@Burgutali`) |
| `REQUIRED_CHANNEL_URL` | kanalga havola |
| `DJANGO_SECRET_KEY` | Django maxfiy kaliti (ishlab chiqarishda albatta o‘zgartiring) |

> **Telegram ID ni qanday bilish mumkin?**
> Botga `/start` yuboring — u sizni bazaga qo‘shadi. So‘ng
> `python manage.py shell` da:
> `from apps.users.models import BotUser; print(list(BotUser.objects.values("telegram_id", "full_name")))`

### Majburiy obuna

Bot kanaldagi a’zolikni tekshirishi uchun **bot kanalda administrator**
bo‘lishi kerak. Aks holda tekshiruv ishlamaydi va bot foydalanuvchilarni
to‘smaydi (log faylida ogohlantirish chiqadi).

Majburiy obunani butunlay o‘chirish: `SUBSCRIPTION_REQUIRED=0`.

---

## 4. Ma'lumotlar bazasi

### SQLite (standart)

Hech narsa sozlash shart emas — baza `data/db.sqlite3` da yaratiladi.
Bot va web bir vaqtda ishlashi uchun **WAL** rejimi avtomatik yoqiladi.

```bash
python manage.py migrate
python manage.py createsuperuser
```

### PostgreSQL

`.env` ichida:

```env
DATABASE_URL=postgres://rasch:parol@localhost:5432/raschbot
```

So‘ng:

```bash
python manage.py migrate
python manage.py createsuperuser
```

---

## 5. Ishga tushirish

Ikkita jarayon **alohida terminalda** ishlaydi:

```bash
# 1-terminal — web (boshqaruv paneli, Mini App, sertifikat tekshiruvi)
python manage.py runserver 0.0.0.0:8000

# 2-terminal — Telegram bot
python run_bot.py
```

Manzillar:

| Manzil | Tavsif |
|--------|--------|
| `http://127.0.0.1:8000/` | ommaviy bosh sahifa |
| `http://127.0.0.1:8000/panel/` | boshqaruv paneli (login va parol bilan) |
| `http://127.0.0.1:8000/panel/tg/` | panelga Telegram orqali kirish (Web App) |
| `http://127.0.0.1:8000/verify/` | sertifikatni tekshirish |
| `http://127.0.0.1:8000/app/` | web ilova (Mini App) |
| `http://127.0.0.1:8000/app/klaviatura/` | faqat matematik klaviatura |

---

## 6. Telegram Mini App (web ilova)

Web ilovada testni topshirish, javoblarni tekshirish, natijalarni ko‘rish,
sertifikat yuklab olish hamda test yaratish va o‘chirish mumkin.

Mini App **HTTPS** manzilni talab qiladi. Lokal ishlab chiqishda tunnel
ishlatiladi.

### 6.1. Bitta buyruq bilan (tavsiya etiladi)

```powershell
powershell -ExecutionPolicy Bypass -File .\ishga_tushirish.ps1
```

Skript avtomatik ravishda:

1. eski jarayonlarni to‘xtatadi;
2. **cloudflared** tunnelini ochadi (kerak bo‘lsa o‘zi yuklab oladi);
3. olingan HTTPS manzilni `.env` ga yozadi
   (`PUBLIC_BASE_URL`, `DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS`);
4. migratsiyalarni qo‘llab, Django serverini ishga tushiradi;
5. Telegram botni ishga tushiradi (bot Telegram menyu tugmasini web ilovaga bog‘laydi);
6. barcha manzillarni tekshirib, natijani ekranga chiqaradi.

To‘xtatish:

```powershell
powershell -ExecutionPolicy Bypass -File .\toxtatish.ps1
```

Qo‘shimcha parametrlar:

| Parametr | Vazifasi |
|----------|----------|
| `-Port 8080` | boshqa portda ishga tushirish |
| `-NoBot` | faqat web va tunnel (botsiz) |
| `-UseNgrok` | cloudflared o‘rniga ngrok ishlatish |

### 6.2. Nega cloudflared, ngrok emas?

**ngrok bepul tarifi** har bir yangi brauzer sessiyasida
«You are about to visit…» ogohlantirish sahifasini ko‘rsatadi
(`ERR_NGROK_6024`). Telegram webview ham shu sahifani oladi, bundan tashqari
ilovaning `fetch()` so‘rovlari JSON o‘rniga HTML qaytaradi — Mini App
ishlamaydi. `traffic-policy` orqali sarlavha qo‘shish ham yordam bermaydi
(ogohlantirish undan oldin ishlaydi).

**cloudflared quick tunnel** — bepul, hisob qaydnomasi talab qilmaydi va
ogohlantirish sahifasi yo‘q. Shu sababli standart tanlov shu.

ngrok baribir kerak bo‘lsa (masalan, pullik tarif bilan):
`.\ishga_tushirish.ps1 -UseNgrok`.

### 6.3. Qo‘lda sozlash

```powershell
.\tools\cloudflared.exe tunnel --url http://127.0.0.1:8000
python tools\set_public_url.py https://xxxx.trycloudflare.com
```

So‘ng Django va botni qayta ishga tushiring.

> Tunnel manzili **har safar o‘zgaradi**. `ishga_tushirish.ps1` buni
> hisobga oladi — har ishga tushirishda `.env` yangilanadi va bot yangi
> manzil bilan qayta ishga tushadi. Doimiy manzil kerak bo‘lsa, o‘z
> domeningizni ulang (9-bo‘limga qarang).

> `PUBLIC_BASE_URL` HTTPS bo‘lmasa, bot web ilova tugmalarini ko‘rsatmaydi —
> barcha amallar bot orqali bajarilaveradi, ochiq javoblar esa oddiy matn
> ko‘rinishida (`12 ; 3/4`) qabul qilinadi. Bu holat log faylida
> ogohlantirish sifatida qayd etiladi.

`PUBLIC_BASE_URL` shuningdek sertifikat QR-kodidagi havola uchun ishlatiladi.

**Brauzerda tekshirish (ishlab chiqish rejimi).** `DEBUG=1` bo‘lganda
ilovani Telegramsiz ochish mumkin: `/app/?debug_user=<telegram_id>`.
Bu yo‘l `DJANGO_DEBUG=0` da avtomatik yopiladi.

---

## 7. Sertifikat shrifti (ixtiyoriy)

Sertifikat PDF sida o‘zbek lotin harflari (`oʻ`, `gʻ`) to‘g‘ri chiqishi uchun
Unicode TTF shrift kerak. Tizim shriftlari avtomatik izlanadi
(`DejaVuSans`, `Arial`, `Segoe UI`, `Liberation Sans` …).

Eng yaxshi natija uchun `assets/fonts/` katalogiga quyidagilarni joylang:

```
assets/fonts/DejaVuSans.ttf
assets/fonts/DejaVuSans-Bold.ttf
```

Shrift topilmasa, matn avtomatik ravishda Latin-1 ga moslashtiriladi —
sertifikat baribir yaratiladi.

---

## 8. Tekshirish

```bash
python manage.py check      # Django tizim tekshiruvi
python selftest.py          # 551 ta tekshiruv (alohida sinov bazasida)
python simulate.py          # 157 ta tekshiruv (bot oqimi simulyatsiyasi)
```

Ikkala skript ham `data/selftest/` va `data/simulate/` kataloglarida
alohida baza yaratadi — ishchi ma'lumotlarga tegmaydi.

---

## 9. Ishlab chiqarishga chiqarish (production)

### 9.1. Sozlamalar

```env
DJANGO_ENV=prod
DJANGO_DEBUG=0
DJANGO_SECRET_KEY=<uzun-tasodifiy-satr>
DJANGO_ALLOWED_HOSTS=sizning-domeningiz.uz
DJANGO_CSRF_TRUSTED_ORIGINS=https://sizning-domeningiz.uz
PUBLIC_BASE_URL=https://sizning-domeningiz.uz
DATABASE_URL=postgres://rasch:parol@localhost:5432/raschbot
```

```bash
python manage.py collectstatic --noinput
python manage.py migrate
```

### 9.2. Gunicorn + nginx

```bash
pip install gunicorn
gunicorn config.wsgi:application --bind 127.0.0.1:8000 --workers 3
```

nginx namunasi:

```nginx
server {
    listen 443 ssl;
    server_name sizning-domeningiz.uz;

    client_max_body_size 20M;

    location /static/ { alias /srv/rasch/staticfiles/; }
    location /media/  { alias /srv/rasch/media/; }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### 9.3. systemd (Linux)

`/etc/systemd/system/rasch-web.service`:

```ini
[Unit]
Description=Rasch web
After=network.target

[Service]
User=rasch
WorkingDirectory=/srv/rasch
ExecStart=/srv/rasch/env/bin/gunicorn config.wsgi:application --bind 127.0.0.1:8000 --workers 3
Restart=always

[Install]
WantedBy=multi-user.target
```

`/etc/systemd/system/rasch-bot.service`:

```ini
[Unit]
Description=Rasch Telegram bot
After=network.target

[Service]
User=rasch
WorkingDirectory=/srv/rasch
ExecStart=/srv/rasch/env/bin/python run_bot.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now rasch-web rasch-bot
```

> **Diqqat:** bot faqat **bitta nusxada** ishlashi kerak. Ikkinchi nusxa ishga
> tushirilsa Telegram `Conflict: terminated by other getUpdates request`
> xatosini qaytaradi.

---

## 10. Zaxira nusxa (backup)

### SQLite

```bash
python manage.py dumpdata --indent 2 > backup_$(date +%F).json
# yoki oddiy fayl nusxasi:
cp data/db.sqlite3 backups/db_$(date +%F).sqlite3
```

### PostgreSQL

```bash
pg_dump -U rasch raschbot | gzip > backups/raschbot_$(date +%F).sql.gz
```

`media/certificates/` katalogini ham zaxiralang — sertifikat PDF fayllari
o‘sha yerda saqlanadi.

---

## 11. Ko‘p uchraydigan muammolar

| Muammo | Yechim |
|--------|--------|
| `BOT_TOKEN sozlanmagan yoki noto‘g‘ri` | `.env` dagi `BOT_TOKEN` ni tekshiring |
| `Conflict: terminated by other getUpdates` | Botning ikkinchi nusxasini to‘xtating |
| Obuna tekshiruvi ishlamayapti | Botni kanalga **administrator** qilib qo‘shing |
| Mini App tugmasi ko‘rinmayapti | `PUBLIC_BASE_URL` HTTPS bo‘lishi kerak |
| `database is locked` (SQLite) | WAL avtomatik yoqiladi; yuklama katta bo‘lsa PostgreSQL ga o‘ting |
| Sertifikatdagi harflar noto‘g‘ri | `assets/fonts/DejaVuSans.ttf` ni joylang |
| Panelga kira olmayapman | `python manage.py createsuperuser` bajaring yoki botdagi «Web panel» tugmasidan kiring |
| Panel Telegram'da oq ekran | `PUBLIC_BASE_URL` HTTPS ekanini tekshiring (iframe uchun `SameSite=None` kerak) |
| «Faqat administratorlar kira oladi» | `.env` dagi `ADMIN_IDS` ga Telegram ID ingizni qo‘shing va botni qayta ishga tushiring |
