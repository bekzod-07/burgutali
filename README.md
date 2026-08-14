# Rasch Telegram Bot — matematik testlarni baholash platformasi

Matematika fanidan Milliy sertifikat formatidagi testlarni **Telegram bot**
orqali o‘tkazish va **Rasch (IRT-1PL)** modeli asosida baholash uchun to‘liq
platforma.

Loyiha ikkita mustaqil, lekin bitta ma'lumotlar bazasi ustida ishlaydigan
qismdan iborat:

| Qism | Texnologiya | Vazifasi |
|------|-------------|----------|
| **Bot** | Python 3.12 + aiogram 3 | Foydalanuvchi bilan muloqot, test o‘tkazish |
| **Web** | Django 4.2 + o‘z CSS dizayni | Boshqaruv paneli, Mini App, sertifikat tekshiruvi |

---

> **Interfeys qoidasi:** loyihada **emoji ishlatilmaydi**. Web ilova, panel
> va sayt — chiziqli **SVG ikonkalar** bilan; Telegram bot esa toza matn va
> tipografik belgilar (`✓`, `✗`, `±`, `·`, `•`) bilan ishlaydi.

---

## Asosiy imkoniyatlar

### Web ilova (Telegram Mini App)

Testni topshirish, javoblarni tekshirish, natijalarni ko‘rish va sertifikat
yuklab olish — barchasi **web ilovada**, tugmalar orqali:

* **Bosh sahifa** — profil, tez amallar, tugallanmagan testni davom ettirish;
* **Testlar** — testga **faqat kod orqali** kiriladi; testlar ro‘yxati
  ishtirokchilarga ko‘rsatilmaydi (uni faqat adminlar ko‘radi);
* **Test topshirish** — **javoblar varaqasi**: barcha savollar bitta oynada,
  yuqorida savollar palitrasi. Tanlov «radio» kabi ishlaydi (ikkinchi
  variant bosilsa, birinchisi o‘chadi) — bu 1–32 (A–D) va 33–35
  (moslashtirish, A–F) savollarining ikkalasiga ham tegishli: har bir
  savolda **faqat bitta** javob belgilanadi. Ochiq savollar uchun
  **matematik klaviatura** va jonli SymPy tekshiruvi. Har bir javob darhol serverga
  saqlanadi. Testni javobsiz savollar bilan ham yakunlash mumkin — bot
  qaysi savollar qolganini ogohlantirib aytadi;
* **Natija** — RASH balli, daraja, reyting, har bir savol bo‘yicha
  to‘g‘ri/xato tahlili;
* **Sertifikatlar** — bitta tugma bilan PDF yuklab olish va QR tekshiruvi;
* **Testlarim** — test **yaratish**, boshqarish (faollashtirish, yopish,
  hisoblash, e’lon qilish), ID kodlar, nusxalash va **o‘chirish**.

Ilova botning menyu tugmasidan, asosiy menyudagi «Ilovani ochish» tugmasidan
yoki `/ilova` buyrug‘idan ochiladi. Barcha so‘rovlar Telegram `initData`
imzosi bilan autentifikatsiya qilinadi.

### Uch xil test turi

| Tur | Kim yaratadi | Baholash | Sertifikat |
|-----|--------------|----------|------------|
| **1-tur — Oddiy test** | har qanday ro‘yxatdan o‘tgan foydalanuvchi | to‘g‘ri javoblar soni va foiz | yo‘q |
| **2-tur — Bepul RASH testi** | har qanday ro‘yxatdan o‘tgan foydalanuvchi | Rasch (IRT-1PL) | yo‘q |
| **3-tur — Pullik RASH testi** | faqat asosiy admin | Rasch (IRT-1PL) | **bor** |

### Test tuzilmasi

Milliy sertifikat shabloni — **45 ta savol**:

* **1–32** — A, B, C, D (bitta to‘g‘ri javob);
* **33–35** — A, B, C, D, E, F (moslashtirish: faqat bitta to‘g‘ri javob);
* **36–45** — variantsiz, har birida **a)** va **b)** javob maydoni.

Yoki ixtiyoriy tuzilma: 10, 20, 30, 45, 50, 100 … savol (A/B/C/D).

### Test kodi — oddiy son va qayta ishlatiladi

Testga kirish kodi ishtirokchi uchun qulay bo‘lishi kerak, shuning uchun u
oddiy **ikki yoki uch xonali son**: `32`, `145`. Uchala test turida ham
shunday.

Kod testga **vaqtincha** biriktiriladi:

```
test yaratildi  →  kod band     →  test yakunlandi  →  kod bo‘shadi
                                    (yopildi / arxivlandi /
                                     o‘chirildi / e’lon qilindi)
```

Yakunlangan testning kodi umumiy fondga qaytadi va bot uni yangi testga
bemalol beradi. Bir xil kod bir vaqtning o‘zida faqat bitta yakunlanmagan
testda bo‘lishi mumkin (bu baza darajasidagi cheklov bilan kafolatlanadi),
shuning uchun kod bo‘yicha qidiruv doim to‘g‘ri testni topadi. Yopilgan test
qayta faollashtirilsa va uning kodi allaqachon boshqa testga berilgan bo‘lsa,
unga yangi kod beriladi va bu haqda xabar chiqadi.

### Test tugash vaqti — kalendar bilan

Test yaratishda tugash vaqtini uch xil usulda berish mumkin: tayyor variant
(1 soat, 24 soat, 7 kun …), soatlar sonini qo‘lda yozish yoki **kalendardan
aniq sana, soat va daqiqani tanlash** (masalan, `21:30`). Kalendar botning
o‘zida — oy jadvali → soatlar → daqiqalar (5 daqiqa qadam bilan).

### Rasch (IRT-1PL) modeli

```
P(x = 1 | θ, b) = exp(θ − b) / (1 + exp(θ − b))
```

* savol qiyinligi **b** — javoblar matritsasidan **JMLE** usuli bilan kalibrlanadi
  (qo‘lda kiritilgan qiyinliklarni «qulflab» qo‘yish mumkin);
* qobiliyat **θ** — **Newton-Raphson MLE** orqali topiladi, ekstremal natijalar
  Wright & Stone tuzatmasi bilan;
* standart ball — `90.14 × (θ − θ_min) / (θ_max − θ_min)`, standart chegaralar
  `θ ∈ [−4; +4]`;
* ishonchlilik: KR-20 va ishtirokchilarni ajratish koeffitsiyenti;
* savollar sifati: p-qiymat va nuqtaviy-biserial korrelyatsiya.

### Ball va darajalar

| Ball | Daraja |
|------|--------|
| 70.0 va yuqori | **A+** |
| 65.0 – 69.9 | **A** |
| 60.0 – 64.9 | **B+** |
| 55.0 – 59.9 | **B** |
| 50.0 – 54.9 | **C+** |
| 46.0 – 49.9 | **C** |
| 0 – 45.9 | Daraja olinmadi |

Maksimal standartlashtirilgan ball — **90.14**.

### Umumiy natijalar va ularda ko‘rsatiladigan nom

Test yakunlangach (yopilganda va natijalar e’lon qilinganda) umumiy
natijalar **PDF ko‘rinishida test egasiga va adminlarga avtomatik
yuboriladi**. Jadval ustunlari: `№ · F.I.SH (yoki ID raqami) · BALL ·
FOIZ · DARAJA`.

Nom test turiga qarab tanlanadi:

| Tur | Umumiy natijalarda | Sertifikatda |
|-----|--------------------|--------------|
| **1-tur — Oddiy test** | ism va familiya | — |
| **2-tur — Bepul RASH testi** | ism va familiya | — |
| **3-tur — Pullik RASH testi** | **ID raqami** | ism va familiya |

### Savollar qiyinchiligi diagrammasi — faqat adminga

RASH testlarida har bir savol (ochiq savollarda — har bir **a)** va **b)**
qism) uchun qiyinchilik darajasi ustunli diagrammada ko‘rsatiladi. Ustun
balandligi — savolga **noto‘g‘ri javob bergan** ishtirokchilar ulushi;
rangi darajani bildiradi:

| Ulush | Daraja | Rang |
|-------|--------|------|
| 0 – 29% | Oson | yashil |
| 30 – 59% | O‘rtacha | sariq |
| 60 – 79% | Qiyin | to‘q sariq |
| 80% va yuqori | Juda qiyin | qizil |

Yonida — **ballar taqsimoti** diagrammasi (ball oraliqlari bo‘yicha
ishtirokchilar soni).

Diagramma **ishtirokchilarga ko‘rinmaydi**. U uch joyda beriladi:
boshqaruv panelining natijalar sahifasida (SVG), test yakunlangach
adminlarga yuboriladigan xabarda (PNG) va «Natijalar (PDF)» hisobotida.
Botda esa test egasi «Savollar qiyinchiligi» tugmasi orqali istalgan
paytda oladi.

### Matematik formulalar klaviaturasi (Telegram Mini App)

Ochiq javob maydoni bosilganda ekran pastidan **bitta oynali** klaviatura
chiqadi — barcha belgilar bir joyda, sahifalar orasida o‘tish shart emas:

```
[yopish]  36-savol · a) javob            [ortga] [oldinga] [qo‘yish]

  1  2  3  4  5  6  7  8  9  0
  π  e  a  b  c  x  y  z  .
  (  )  □/□  √□  □^□  □²  □³  ³√□  ⁿ√□
  +  −  sin□  cos□  tan□  cot□
  arcsin□  arccos□  arctan□  arcctg□
  ln□  log□  log□□  exp□
                    ‹   ›   ⏎   ⌫
```

Yuqoridagi qatorda uchta amal bor: **ortga qaytarish**, **oldinga
qaytarish** va **buferdan qo‘yish**. Pastdagi yo‘lakda kursorni siljitish
(`‹ ›`), keyingi maydonga o‘tish (`⏎`) va o‘chirish (`⌫`).

Klaviatura **bitta manbadan** keladi (`static/mathpad/`), shuning uchun u
uchala joyda aynan bir xil: web ilovada test topshirishda, test yaratishdagi
javob kalitlari varaqasida va botning `/app/klaviatura/` sahifasida.

### Javob maydoni — chizilgan formula

Javob maydonining o‘zi kiritilgan ifodani **haqiqiy formula ko‘rinishida**
ko‘rsatadi: kasr ustma-ust, ildiz chiziq ostida, daraja yuqorida.

```
455        ______
───  ·  ⁵⁴√ 5666
4566
```

Maydonning qiymati ilgarigidek oddiy matn bo‘lib qoladi (`455/4566 sqrt(...)`) —
baholash, saqlash va SymPy tekshiruvi shu matn bilan ishlaydi, o‘zgargani
faqat ko‘rinish. Kursor formulaning ichida ko‘rinadi; uni `‹ ›` tugmalari
bilan yoki formulani bosib siljitish mumkin.

To‘ldirilmagan joy **bo‘sh to‘rtburchak** bo‘lib turadi. Masalan, hech
narsa yozmasdan kasr tugmasi bosilsa, darhol ustma-ust ikkita to‘rtburchak
va ular orasida chiziq chiziladi, kursor esa yuqoridagi to‘rtburchakning
ichida turadi:

```
□          ⌐‾‾¬          □
─          |□|          □
□                       (daraja)
kasr       ildiz
```

Xuddi shunday: `√`, `□^□`, `log□(□)` va boshqa tugmalar ham bosilishi
bilan bo‘sh to‘rtburchaklarini ko‘rsatadi. Formula to‘liq to‘ldirilmaguncha
jonli tekshiruv xato haqida ogohlantirmaydi.

**Darajadan chiqish.** Daraja tugmalari ko‘rsatkichni qavs bilan yozadi
(`2^(3)`), shuning uchun uning chegarasi aniq: `›` tugmasi bosilishi bilan
kursor darajadan **pastga tushadi** va keyingi son ko‘rsatkichga qo‘shilib
ketmaydi — `2³·4` bo‘ladi, `2³⁴` emas. Qavslar ekranda ko‘rsatilmaydi
(faqat `2³` ko‘rinadi), qiymat esa SymPy uchun to‘g‘ri matn bo‘lib qoladi.
Xuddi shu qoida ildiz, kasr, modul va logarifmga ham tegishli.

Bo‘sh tuzilma ustida `⌫` bosilsa (masalan `√□` yoki `□^□` xato bosilgan
bo‘lsa), bitta belgi emas — butun tuzilma o‘chadi, ekranda yolg‘iz qavs
qolib ketmaydi.

**Ildiz darajasi.** `ⁿ√□` tugmasida daraja ham bo‘sh to‘rtburchak bo‘lib
turadi — unga istalgan butun son yoziladi (`⁵√32`, `⁴√16`). Kursor avval
ildiz ostidagi katakka tushadi, `›` bilan daraja katagiga o‘tiladi.

**Kasr tugmasi** uch xil ishlaydi:

| Kursordan oldin | Natija |
|-----------------|--------|
| hech narsa yoki amal (`2+`) | bo‘sh kasr chiziladi, yozilgan son o‘z joyida qoladi: `2 + □/□` |
| son yoki ifoda (`455`) | u surat bo‘ladi, kursor maxrajga tushadi: `455/□` |
| tayyor kasr (`455/3`) | eski kasr suratga **ko‘tarilmaydi**, yangisi yonida chiziladi: `455/3 · □/□` |

Har bir maydonning o‘ng chetida ikkita tugma bor: **klaviatura** belgisi
matematik klaviaturani ochadi/yopadi, **ro‘yxat** belgisi esa maydonni
matn ko‘rinishiga o‘tkazadi (nusxa ko‘chirish yoki oddiy klaviatura bilan
tuzatish uchun).

Javoblar **SymPy** yordamida *matematik ekvivalentlik* bo‘yicha tekshiriladi:
`1/2` = `0.5` = `2^-1`, `sin(pi/6)` = `0.5`, `30°` = `pi/6`.

### Javob kalitlari — varaqa ko‘rinishida

Test yaratuvchi to‘g‘ri javoblarni **qatnashchi ko‘radigan varaqaning aynan
o‘zida** belgilaydi: har bir savol uchun A–D (33–35 da A–F) tugmalari, ochiq
savollar uchun esa a) va b) maydonlari va matematik klaviatura. Yuqorida
`belgilangan / jami` hisoblagichi turadi; to‘ldirilmagan savollar yuborishdan
oldin ro‘yxat qilib ko‘rsatiladi.

Uzun kalitni bir marta joylashtirish uchun **«Matn ko‘rinishida»** rejimi
qoldirilgan: `ABCDABCD…` yoki `1-A 2-B`, moslashtirish uchun `A, C, E`,
ochiq javoblar uchun har bir qatorda `12 ; 3/4`.

### Bir martalik ID kodlar (pullik test)

Kod formati: `R7K4-8251`. Hayotiy sikli:

```
Ishlatilmagan  →  Faollashtirilgan  →  Ishlatilgan
```

Kod foydalanuvchi uni kiritgan zahoti **yopilmaydi** — faqat yakuniy javob
bazaga muvaffaqiyatli saqlangandan keyin `Ishlatilgan` holatiga o‘tadi.
Shu sababli internet uzilishi kodni «kuydirmaydi».

Har bir kod uchun kim, qachon va qaysi testga javob yuborgani saqlanadi.
Yaratilgan kodlar adminga **Excel fayl** ko‘rinishida beriladi.

### Avtomatik sertifikat

Natijalar hisoblanib, admin ularni **e'lon qilgandan keyin** har bir huquqli
qatnashchi uchun PDF sertifikat yaratiladi:

* noyob sertifikat raqami (`RM-2026-000123`);
* ism-familiya, test nomi va sanasi;
* RASH balli, foiz, daraja, reyting;
* bo‘limlar bo‘yicha natija;
* tashkilotchi nomi va berilgan sana;
* **QR-kod** — tekshirish sahifasiga havola.

Sertifikat kimlarga berilishini admin belgilaydi: barchaga, yoki belgilangan
minimal ball/darajadan yuqori natija olganlarga.

### Testlarni qo‘shish va o‘chirish

Test yaratish **uch joyda** mavjud: botdagi sehrgar, web ilova va boshqaruv
paneli. Har uchalasi bitta xizmat qatlamidan foydalanadi.

O‘chirish — himoyalangan amal:

* nima yo‘qolishi oldindan ko‘rsatiladi (savollar, urinishlar, ID kodlar,
  sertifikatlar soni);
* topshirilgan javoblar bo‘lsa, tasdiqlash majburiy
  (panelda — test kodini qo‘lda kiritish);
* sertifikat va Excel fayllari diskdan ham tozalanadi;
* o‘chirishdan oldin natijalarni Excel/PDF ko‘rinishida saqlash taklif etiladi.

Shuningdek testning to‘liq **nusxasini** yaratish mumkin — savollar va javob
kalitlari ko‘chiriladi, natijalar esa ko‘chirilmaydi.

### Boshqaruv paneli (Django + o‘z CSS dizayni)

> **Django ning standart admin paneli ishlatilmaydi** — u butunlay olib
> tashlangan. Barcha boshqaruv shu panelda, o‘zbek tilida va bitta dizaynda.

Panelga **ikki xil** kirish mumkin:

* login va parol bilan — `/panel/kirish/`;
* **Telegram orqali** — botdagi «Web panel» tugmasi panelni Web App
  sifatida ochadi va `initData` imzosi bo‘yicha avtomatik kiritadi
  (faqat `ADMIN_IDS` dagi adminlar).

Imkoniyatlari:

* test **yaratish** (tur, tuzilma, kalitlar, sozlamalar bir sahifada);
* testlarni faollashtirish, yopish, hisoblash, e'lon qilish, nusxalash va
  **o‘chirish** (tasdiqlash bilan);
* savollarni **to‘liq tahrirlash**: matn, turi, variantlar, kalit, ochiq
  javoblar, Rasch qiyinligi va «qulflash»;
* **urinishlar** ro‘yxati va tafsiloti: har bir javob, qayta baholash,
  bekor qilish, o‘chirish, sertifikat berish;
* **ID kodlar**: yaratish, Excel eksport, bekor qilish, tiklash;
* **sertifikatlar**: PDF qayta yaratish, bekor qilish, tiklash, o‘chirish;
* **foydalanuvchilar**: tafsilot, bloklash, admin qilish, natijalari va testlari;
* **amallar tarixi** (audit jurnali) — filtrlar bilan;
* reyting, statistika, darajalar taqsimoti, Excel/PDF eksport;
* **savollar qiyinchiligi** va **ballar taqsimoti** diagrammalari
  (natijalar sahifasida, faqat adminlarga).

---

## Tez ishga tushirish

### Windows — bitta buyruq

```powershell
powershell -ExecutionPolicy Bypass -File .\ishga_tushirish.ps1
```

Skript hammasini o‘zi bajaradi: **cloudflared** tunnelini ochadi (kerak
bo‘lsa yuklab oladi), olingan HTTPS manzilni `.env` ga yozadi, migratsiyalarni
qo‘llaydi, Django serverini va Telegram botni ishga tushiradi, so‘ng barcha
manzillarni tekshirib chiqadi. Bot esa Telegram menyu tugmasini avtomatik
web ilovaga bog‘laydi.

To‘xtatish: `powershell -ExecutionPolicy Bypass -File .\toxtatish.ps1`

> Web ilova HTTPS talab qiladi. `ngrok` bepul tarifi brauzer ogohlantirish
> sahifasini ko‘rsatgani uchun Mini App bilan ishlamaydi — shuning uchun
> standart tanlov **cloudflared** (hisob qaydnomasi kerak emas).
> ngrok kerak bo‘lsa: `.\ishga_tushirish.ps1 -UseNgrok`.

### Qo‘lda

```bash
# 1. Bog'liqliklarni o'rnatish
python -m venv env
env\Scripts\activate            # Windows
# source env/bin/activate       # Linux / macOS
pip install -r requirements.txt

# 2. Sozlamalar
copy .env.example .env          # Windows
# cp .env.example .env          # Linux / macOS
#  -> .env ichida BOT_TOKEN, ADMIN_IDS, REQUIRED_CHANNEL ni to'ldiring

# 3. Ma'lumotlar bazasi
python manage.py migrate
python manage.py createsuperuser

# 4. Web serverni ishga tushirish
python manage.py runserver

# 5. Botni ishga tushirish (alohida terminalda)
python run_bot.py
```

Batafsil: [docs/ORNATISH.md](docs/ORNATISH.md)

### Serverga o‘rnatish (production — burgutali.uz)

Ubuntu 22.04/24.04 serverda **bitta skript** hammasini ko‘taradi:
nginx + SSL (Let's Encrypt) + Django web (gunicorn) + Telegram bot —
ikkalasi ham systemd xizmati sifatida, server qayta yonganda avtomatik
ishga tushadi.

```bash
# 1. Loyihani yuklab olish
git clone https://github.com/bekzod-07/burgutali.git
cd burgutali

# 2. Skriptga ruxsat berish va ishga tushirish
chmod +x deploy.sh
sudo ./deploy.sh
#  -> birinchi ishga tushirishda .env yaratiladi va skript to'xtaydi;
#     nano .env  bilan BOT_TOKEN, BOT_USERNAME, ADMIN_IDS ni to'ldiring

# 3. Qayta ishga tushirish — hammasi ko'tariladi
sudo ./deploy.sh
```

> **Eslatma:** SSL olishdan oldin `burgutali.uz` (va ixtiyoriy `www`)
> DNS **A-yozuvi** server IP siga qaratilgan bo‘lishi kerak.

Yangilash (kod o‘zgarganda):

```bash
git pull && sudo ./deploy.sh
```

Foydali buyruqlar:

```bash
systemctl status burgutali-web      # web holati
systemctl status burgutali-bot      # bot holati
journalctl -u burgutali-bot -f      # bot loglari (jonli)
tail -f logs/gunicorn-error.log     # web xato loglari
```

---

## Loyiha tuzilmasi

```
rashmodel_matematikabot/
├── manage.py                  Django boshqaruvi
├── run_bot.py                 Botni ishga tushirish
├── ishga_tushirish.ps1        Tunnel + server + bot — bitta buyruqda
├── toxtatish.ps1              Barcha jarayonlarni to'xtatish
├── tools/
│   ├── cloudflared.exe        HTTPS tunnel (avtomatik yuklanadi)
│   ├── ngrok.exe              muqobil tunnel
│   └── set_public_url.py      .env dagi PUBLIC_BASE_URL ni yangilaydi
├── selftest.py                O'z-o'zini tekshiruv (545 ta tekshiruv)
├── simulate.py                Bot oqimi simulyatsiyasi (157 ta tekshiruv)
│
├── config/                    Django loyihasi
│   ├── settings/              base / dev / prod
│   ├── urls.py
│   ├── wsgi.py
│   └── asgi.py
│
├── core/                      Django'ga bog'liq bo'lmagan yadro
│   ├── constants.py           TZ dagi barcha raqamli talablar
│   ├── env.py                 .env bilan ishlash
│   ├── text_utils.py          matn normalizatsiyasi
│   ├── math_expr.py           SymPy ekvivalentligi (xavfsiz parser)
│   └── django_setup.py        bot uchun django.setup()
│
├── apps/                      Django ilovalari
│   ├── common/                bazaviy modellar, SQLite PRAGMA, bosh sahifa
│   ├── users/                 Telegram foydalanuvchilari, rollar, audit
│   ├── exams/                 testlar, savollar, kalit tahlili, tuzilmalar
│   ├── attempts/              urinishlar, javoblar, baholash, statistika
│   ├── accesscodes/           bir martalik ID kodlar
│   ├── rasch/                 IRT-1PL: estimator, scoring, services
│   ├── certificates/          PDF sertifikat, QR, tekshiruv sahifasi
│   ├── exports/               Excel, PDF hisobotlar va diagrammalar
│   ├── miniapp/               Telegram Mini App (to'liq web ilova)
│   │   ├── api.py             JSON API (test, urinish, natija, CRUD)
│   │   ├── auth.py            initData imzosi va foydalanuvchini aniqlash
│   │   ├── serializers.py     modellarni JSON ga o'girish
│   │   └── static/            app.css, app.js (bir sahifali ilova)
│   └── dashboard/             web boshqaruv paneli (o'z CSS dizayni)
│
├── bot/                       Telegram bot (aiogram 3)
│   ├── config.py              bot sozlamalari
│   ├── loader.py              Bot va Dispatcher
│   ├── main.py                ishga tushirish
│   ├── texts/                 barcha matnlar (common, start, exam, admin)
│   ├── keyboards/             reply, inline, callback fabrikalari
│   ├── states/                FSM holatlari
│   ├── middlewares/           throttling, foydalanuvchi, majburiy obuna
│   ├── services/              ORM ga asinxron ko'prik
│   ├── utils/                 formatlash, obuna, fayllar
│   ├── tasks/                 fon vazifalari
│   └── handlers/
│       ├── start.py           /start va deep-link
│       ├── subscription.py    majburiy obuna
│       ├── registration.py    ism-familiya va telefon
│       ├── menu.py            asosiy menyu
│       ├── create/            test yaratish sehrgari
│       ├── taking/            testga kirish va javob berish
│       ├── results.py         natijalar va reyting
│       ├── certificate.py     sertifikatlar
│       ├── my_tests.py        yaratilgan testlarni boshqarish
│       ├── admin/             administrator paneli
│       ├── errors.py          xatoliklarni ushlash
│       └── fallback.py        noma'lum xabarlar
│
├── templates/
│   ├── base.html              ommaviy sahifalar asosi
│   └── partials/icons.html    SVG ikonkalar to'plami (emoji o'rniga)
├── static/
│   ├── css/site.css           ommaviy sahifalar uslubi
│   └── mathpad/               matematik klaviatura — uchala joy uchun
│       ├── mathpad.css        yagona ko'rinish
│       └── mathpad.js         yagona mantiq
└── docs/                      hujjatlar
```

---

## Tekshirish

```bash
python selftest.py      # 545 ta tekshiruv: modullar, Rasch, oqimlar, web, panel, Mini App API, diagrammalar
python simulate.py      # 157 ta tekshiruv: botning to'liq foydalanuvchi oqimi
python manage.py check  # Django tizim tekshiruvi
```

Tekshiruvlar orasida: SymPy parseriga qarshi 11 ta hujum urinishi, Mini App
API ning autentifikatsiya va huquq chegaralari, test o‘chirish/nusxalash
xavfsizligi, ikonkalar butunligi va **emoji ishlatilmaganligi**.

Ikkala skript ham **alohida vaqtinchalik bazada** ishlaydi — ishchi
ma'lumotlarga tegmaydi.

---

## Texnologiyalar

Python 3.12+ · aiogram 3.29 · Django 4.2 · SQLite/PostgreSQL ·
SymPy · NumPy · SciPy · openpyxl · pandas · ReportLab · qrcode · Pillow

---

## Hujjatlar

* [O‘rnatish va ishga tushirish](docs/ORNATISH.md)
* [Arxitektura](docs/ARXITEKTURA.md)
* [Texnik topshiriqqa moslik jadvali](docs/TZ_MOSLIK.md)
* [Video dars stsenariysi](docs/VIDEO_DARS.md) — sahna-sahna, so‘zma-so‘z matn bilan
* [Avtomatik video dars](docs/VIDEO_DARS_AVTOMATIK.md) — platforma o‘zini o‘zi
  ko‘rsatadigan, **o‘zbekcha diktor ovozi bilan** videoni bir buyruq bilan
  yozib olish (natija: `data/video/dars.mp4`, subtitr va bob taymkodlari)

---

## Namoyish (demo) ma’lumotlari

Video yozish, taqdimot yoki sinov uchun tayyor ma’lumot yaratish:

```bash
python tools/demo_data.py --reset    # 3 ta test, 28 ishtirokchi, 18 sertifikat
python tools/demo_data.py --clean    # faqat demo yozuvlarni o‘chiradi
```

Demo yozuvlar aniq belgilanadi (foydalanuvchilar — Telegram ID 900000000 dan,
testlar — nomi «DEMO» bilan boshlanadi), shuning uchun `--clean` haqiqiy
ma’lumotlarga tegmaydi.
