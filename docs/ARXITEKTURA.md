# Arxitektura

## 1. Umumiy ko‘rinish

```
                   ┌──────────────────────────────┐
   Telegram  ◄────►│  bot/  (aiogram 3)           │
                   │  polling, FSM, handlerlar    │
                   └───────────────┬──────────────┘
                                   │  sync_to_async
                                   ▼
                   ┌──────────────────────────────┐
                   │  apps/  (Django ORM)         │
                   │  biznes-mantiq va modellar   │
                   └───────────────┬──────────────┘
                                   │
                   ┌───────────────┴──────────────┐
                   │  Ma'lumotlar bazasi          │
                   │  SQLite (WAL) yoki Postgres  │
                   └───────────────┬──────────────┘
                                   │
                   ┌───────────────┴──────────────┐
   Brauzer  ◄─────►│  config/ + apps/dashboard    │
                   │  web panel, Mini App, QR     │
                   └──────────────────────────────┘
```

**Asosiy qaror:** bot va web bitta ORM (Django) va bitta bazadan
foydalanadi. TZ da SQLAlchemy ko‘rsatilgan bo‘lsa-da, ikkita ORM ni bitta
sxema ustida ishlatish migratsiya va tranzaksiya muammolarini keltirib
chiqaradi. Yagona ORM — yagona migratsiya tarixi, yagona haqiqat manbai.

Bot jarayoni ishga tushganda `core/django_setup.py` orqali `django.setup()`
chaqiriladi; barcha baza amallari `bot/services/*` da `sync_to_async`
bilan o‘raladi.

---

## 2. Qatlamlar

### 2.1. `core/` — Django'ga bog‘liq bo‘lmagan yadro

| Modul | Vazifasi |
|-------|----------|
| `constants.py` | TZ dagi barcha raqamli talablar: 90.14, daraja jadvali, savol turlari, ID kod alifbosi |
| `env.py` | `.env` bilan ishlash (Django va bot uchun yagona manba) |
| `text_utils.py` | apostroflar, ism-familiya, telefon, HTML ekranlash |
| `answer_check.py` | ochiq javoblarni matn bo‘yicha tekshirish (sinonimlar, apostrof, tinish belgilari) |
| `django_setup.py` | bot jarayonida Django ni ishga tushirish |

`answer_check.py` — ochiq javoblarni baholashning **yagona** manbasi: bot,
web ilova va boshqaruv paneli aynan shu moduldan foydalanadi. Javob matn
sifatida solishtiriladi: katta-kichik harf, apostrof ko‘rinishi va hatto
uning yo‘qligi (`orta` = `o‘rta`), tinish belgilari va ortiqcha probellar
e’tiborga olinmaydi. Kalitdagi sinonimlar `,`, `;` yoki `/` bilan sanaladi
(`osmon, samo, fazo`) va har biri to‘g‘ri javob hisoblanadi.

### 2.2. `apps/` — Django ilovalari

| Ilova | Modellar | Asosiy modullar |
|-------|----------|-----------------|
| `common` | `TimeStampedModel` (abstrakt) | `db_pragmas.py` (SQLite WAL), `views.py` (bosh sahifa) |
| `users` | `BotUser`, `UserAction` | `services.py` |
| `exams` | `Exam`, `Question` | `services.py`, `keys.py`, `structures.py` |
| `attempts` | `Attempt`, `Answer`, `ExamStatistics` | `services.py`, `grading.py` |
| `accesscodes` | `CodeBatch`, `AccessCode` | `services.py`, `generator.py` |
| `rasch` | — | `estimator.py`, `scoring.py`, `services.py` |
| `certificates` | `Certificate` | `services.py`, `pdf.py`, `qr.py`, `fonts.py` |
| `exports` | — | `excel.py`, `pdf_report.py` |
| `miniapp` | — | `views.py`, `auth.py`, shablon + CSS + JS |
| `dashboard` | — | `views.py`, `forms.py`, shablonlar + CSS |

Har bir ilovada **`services.py`** — biznes-mantiqning yagona kirish nuqtasi.
View lar ham, bot ham faqat shu funksiyalarni chaqiradi. Bu takrorlanishni
yo‘q qiladi va mantiqni bitta joyda saqlaydi.

### 2.3. `bot/` — Telegram bot

```
bot/
├── config.py        BotConfig (dataclass, keshlangan)
├── loader.py        Bot + Dispatcher yig'ish
├── main.py          logging, startup, polling
├── texts/           barcha matnlar (kodda matn yozilmaydi)
├── keyboards/       reply, inline, CallbackData fabrikalari
├── states/          FSM holatlari
├── middlewares/     throttling → user → subscription
├── services/        ORM ga asinxron ko'prik
├── utils/           formatlash, obuna, fayllar
├── tasks/           fon vazifalari
└── handlers/        bo'limlar bo'yicha ajratilgan
```

---

## 3. Ma'lumotlar modeli

```
BotUser ──1:N──► Exam ──1:N──► Question
   │               │
   │               ├──1:N──► AccessCode ──N:1──► CodeBatch
   │               ├──1:1──► ExamStatistics
   │               └──1:N──► Attempt ──1:N──► Answer
   │                            │
   └────────────────────────────┴──1:1──► Certificate
```

### Muhim cheklovlar (constraints)

| Cheklov | Maqsad |
|---------|--------|
| `uniq_submitted_attempt_per_user` | bitta foydalanuvchi bitta testga faqat bitta yakuniy javob |
| `uniq_answer_per_question` | bitta savolga bitta javob |
| `uniq_exam_question_order` | savollar tartib raqami takrorlanmaydi |
| `uniq_live_exam_code` | bitta test kodi bir vaqtda faqat bitta **yakunlanmagan** testda (kod qayta ishlatiladi) |
| `AccessCode.code` unique | ID kodlar global noyob |
| `Certificate.number` unique | bitta raqam = bitta natija |

---

## 4. Baholash oqimi

```
1. Answer.selected / text_a / text_b        ← foydalanuvchi javobi
        │
2. attempts/grading.py                       ← kalit yoki matn tekshiruvi ekvivalentligi
        │   grade_attempt() -> responses[0/1]
        ▼
3. rasch/services.py: build_items()          ← savollarni "item" larga yoyish
        │   (ochiq savol = 2 ta item: a va b)
        ▼
4. rasch/estimator.py: calibrate()           ← JMLE, savol qiyinligi b
        │
5. rasch/estimator.py: estimate_theta()      ← Newton-Raphson MLE
        │
6. rasch/scoring.py: theta_to_ball()         ← 0 … 90.14
        │
7. Attempt.ball / grade / rank               ← bazaga saqlash
        │
8. ExamStatistics                            ← KR-20, taqsimot, item statistikasi
```

Oddiy testda (1-tur) 4–6-bosqichlar o‘tkazib yuboriladi — natija
to‘g‘ri javoblar soni va foizdan iborat.

---

## 5. ID kod hayotiy sikli

```
        create_codes()
             │
             ▼
      ┌─────────────┐   activate_code()   ┌──────────────────┐
      │ Ishlatilmagan│ ──────────────────► │ Faollashtirilgan │
      └─────────────┘                      └────────┬─────────┘
             ▲                                      │
             │ release_code()                       │ consume_code()
             │ (foydalanuvchi chiqib ketsa)         │ (yakuniy javob saqlangach)
             └──────────────────────────────────────┤
                                                    ▼
                                            ┌───────────────┐
                                            │  Ishlatilgan  │
                                            └───────────────┘
```

`consume_code()` faqat `submit_attempt()` ichida, urinish `SUBMITTED`
holatida saqlangandan **keyin** chaqiriladi.

---

## 6. Test holatlari

```
DRAFT ──activate──► ACTIVE ──close──► CLOSED ──calculate──► CALCULATED
                       │                                        │
                       └──────────── calculate ─────────────────┤
                                                                ▼
                                                            PUBLISHED
                                                                │
                                                    (sertifikatlar ochiladi)
```

`ARCHIVED` — istalgan holatdan.

Pullik test `ACTIVE` holatiga o‘tishi uchun ID kodlar yaratilgan bo‘lishi shart.

---

## 7. Bot middleware zanjiri

```
Update
  │
  ├─► ThrottlingMiddleware     spam va tez bosishdan himoya
  │
  ├─► UserMiddleware           BotUser ni yuklaydi/yaratadi,
  │                            data["user"], data["config"], data["is_admin"]
  │                            bloklangan foydalanuvchini to'xtatadi
  │
  ├─► SubscriptionMiddleware   majburiy obuna (adminlar mustasno,
  │                            /start va sub: callback lar ozod,
  │                            natija 30 daqiqa keshlanadi)
  │
  └─► Handler
```

---

## 8. Router tartibi

Tartib muhim — birinchi mos kelgan handler ishlaydi:

```
1.  menu          bekor qilish va asosiy menyu tugmalari (StateFilter("*"))
2.  start         /start va deep-link
3.  subscription  a'zolikni tekshirish
4.  registration  ism-familiya va telefon
5.  create        test yaratish sehrgari
6.  taking        testga kirish va javob berish
7.  results       natijalar va reyting
8.  certificate   sertifikatlar
9.  my_tests      yaratilgan testlarni boshqarish
10. admin         administrator paneli
11. fallback      noma'lum xabarlar (eng oxirida)
```

`menu` birinchi bo‘lgani uchun «Bekor qilish» va «Asosiy menyu»
istalgan holatda ishlaydi.

---

## 9. Web ilova (Telegram Mini App)

Mini App — bir sahifali ilova: barcha ekranlar `app.js` da chiziladi,
ma'lumot esa `/app/api/` dan JSON ko‘rinishida olinadi.

```
apps/miniapp/
├── auth.py            initData imzosini tekshirish + resolve_user()
├── api.py             barcha JSON endpointlar (@api_view dekoratori)
├── serializers.py     modellarni JSON ga o'girish
├── views.py           SPA qobig'i va klaviatura sahifasi
├── urls.py            /app/ va /app/api/...
├── templates/miniapp/app.html        qobiq (header + ekran + tabbar)
└── static/miniapp/
    ├── css/app.css    Telegram mavzusiga moslashuvchi uslub
    └── js/app.js      router, ekranlar, ochiq javob maydonlari
```

**Autentifikatsiya.** Har bir API so‘rovi `X-Telegram-Init-Data`
sarlavhasi bilan yuboriladi; server imzoni bot tokeni bilan tekshiradi va
`BotUser` ni topadi. Sessiya ham, CSRF tokeni ham kerak emas. Ishlab
chiqish rejimida `X-Debug-User` sarlavhasi orqali test qilish mumkin
(prod da bu yo‘l yopiq).

**Ekranlar:** bosh sahifa · testlar · test kartochkasi · test topshirish ·
natija · natijalarim · sertifikatlar · testlarim · test yaratish ·
boshqaruv · reyting.

**Asosiy API endpointlar:**

| Endpoint | Vazifasi |
|----------|----------|
| `GET  api/boshlash/` | profil, testlar, natijalar, sertifikatlar, tugallanmagan urinishlar |
| `GET  api/test/<kod>/` | test kartochkasi va ishtirok etish imkoniyati |
| `POST api/test/<kod>/boshlash/` | urinish ochish (pullik testda ID kod) |
| `GET  api/urinish/<id>/` | barcha savollar va saqlangan javoblar |
| `POST api/urinish/<id>/javob/` | bitta javobni saqlash |
| `POST api/urinish/<id>/yuborish/` | yakuniy yuborish |
| `GET  api/urinish/<id>/natija/` | natija, javoblar tahlili, sertifikat holati |
| `POST api/urinish/<id>/sertifikat/` | sertifikat yaratish va havolasini olish |
| `POST api/test-yaratish/` | yangi test (kalitlar bilan) |
| `POST api/test/<kod>/amal/` | faollashtirish / yopish / hisoblash / e'lon / nusxa |
| `POST api/test/<kod>/ochirish/` | testni o‘chirish (tasdiq bilan) |
| `POST api/ifoda/` | ochiq javobni tekshiruvga tayyor ko‘rinishga keltirish |

---

## 9.1. Bot va klaviatura sahifasi

```
Bot                                 Mini App (Django)
 │                                        │
 ├─ reply keyboard + web_app tugmasi ────►│
 │                                        │  foydalanuvchi ifoda kiritadi
 │                                        │
 │                                        ├─ POST /app/api/tekshir/
 │                                        │  (matn tekshiruvi orqali jonli tekshiruv)
 │                                        │
 │◄─── Telegram.WebApp.sendData(JSON) ────┤
 │     {"q": 36, "a": "12", "b": "3/4"}   │
 │                                        │
 └─ F.web_app_data handler ──► javobni saqlaydi
```

`sendData()` faqat **reply**-klaviaturadagi `web_app` tugmasida ishlaydi —
shuning uchun ochiq savol paydo bo‘lganda maxsus klaviatura yuboriladi.

Mini App HTTPS talab qiladi. U mavjud bo‘lmasa, ochiq javoblar oddiy matn
sifatida (`12 ; 3/4`) qabul qilinaveradi — funksionallik yo‘qolmaydi.

---

## 10. Xavfsizlik

| Chora | Qayerda |
|-------|---------|
| Ochiq javob uzunligi cheklanadi (`MAX_INPUT_LENGTH`) | `core/answer_check.py` |
| Mini App `initData` HMAC-SHA256 imzosi | `apps/miniapp/auth.py` |
| Sertifikat QR havolasida taxmin qilib bo‘lmaydigan token | `Certificate.verify_token` |
| ID kodlar `secrets` moduli bilan yaratiladi | `apps/accesscodes/generator.py` |
| Spam himoyasi | `bot/middlewares/throttling_mw.py` |
| Panelga faqat `is_staff` kirishi | `apps/common/mixins.py` |
| Amallar audit jurnali | `apps/users/models.UserAction` |
| Testga egalik tekshiruvi | `exams/services.can_manage()`, `miniapp/api.get_owned_exam()` |
| Bir vaqtda yozishdan himoya | `select_for_update()` + SQLite WAL |
| O‘chirishda tasdiqlash talabi | `exams/services.delete_exam(force=...)` |

---

## 11. Interfeys: emoji o‘rniga ikonkalar

Loyihada **emoji ishlatilmaydi**.

| Muhit | Yechim |
|-------|--------|
| Web (sayt, panel, Mini App) | `templates/partials/icons.html` — 67 ta chiziqli SVG `<symbol>`; `<svg class="icon"><use href="#i-award"></use></svg>` |
| Telegram bot | toza matn; holat belgilari uchun tipografik `✓` `✗` `±` `·`, ro‘yxatlar uchun `•`, tanlov tugmalari uchun `●/○` va `■/□` |

Ikonkalarning rangi va qalinligi CSS dagi `.icon` klassidan meros olinadi
(`fill`/`stroke` — meros qilinadigan xossalar, shuning uchun ular `<use>`
soya daraxtiga ham o‘tadi).

`selftest.py` ikkita doimiy tekshiruvni bajaradi:
ishlatilgan har bir `#i-...` ikonka sprite da mavjudligini, va bot
matnlarida emoji yo‘qligini. `simulate.py` esa haqiqiy oqimda yuborilgan
barcha xabar, tugma va fayl izohlarini emoji uchun tekshiradi.
