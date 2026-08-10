# Avtomatik yozilgan video dars

`docs/VIDEO_DARS.md` — bu **odam** yozadigan darsning stsenariysi: sahna-sahna,
so'zma-so'z matn bilan. Ushbu hujjat esa boshqa narsa haqida: platforma
**o'zini o'zi ko'rsatadigan** videoni brauzer orqali avtomatik yozib oladi.

Video ichida hech qanday montaj yoki soxta ekran yo'q — bu haqiqiy, ishlab
turgan tizimning yozuvi:

* web sahifalar **haqiqiy serverdan** ochiladi;
* test **haqiqatan topshiriladi**, natija bazaga yoziladi;
* Telegram suhbatidagi har bir gap va tugma **botning o'z handler'laridan**
  olingan (`aiogram` dispatcher'iga haqiqiy `Update` yuboriladi, faqat
  Telegram serveri o'rniga xotiradagi sessiya ishlatiladi).

> **Ovoz yo'q.** Skript ekranni yozadi, gapirmaydi. Izohlar ekranning
> chap tomonida va pastida matn ko'rinishida chiqadi. Ovozli dars kerak
> bo'lsa — `docs/VIDEO_DARS.md` dagi so'zma-so'z matnni shu videoning
> ustidan o'qib chiqish yetarli: sahnalar tartibi bir xil.

---

## Tez ishga tushirish

```powershell
# 1. Platforma ishlab turishi kerak
powershell -ExecutionPolicy Bypass -File .\ishga_tushirish.ps1

# 2. Namoyish ma'lumotlari
python tools\demo_data.py --reset

# 3. Video uchun faol test (ochiq savollar va matematik klaviatura uchun)
python tools\video_prepare.py

# 4. Bot suhbatini yozib olish
python tools\video_bot_dialog.py

# 5. Videoni yozish
python tools\video_lesson.py
```

Natija:

| Fayl | Izoh |
|------|------|
| `data/video/dars.mp4` | asosiy fayl (H.264, 1280×720, 25 kadr/sek) |
| `data/video/dars.webm` | brauzer yozgan asl nusxa (VP8) |
| `data/video/boblar.txt` | bob taymkodlari — YouTube tavsifiga tayyor |
| `data/video/bot_dialog.json` | yozib olingan bot suhbati |

---

## Video tuzilishi

Umumiy davomiyligi — **taxminan 9 daqiqa 25 soniya**. Taymkodlar har bir
yozuvdan keyin `data/video/boblar.txt` fayliga yoziladi; quyidagilar —
oxirgi yozuvdan:

| Vaqt | Bob | Nimalar ko'rsatiladi |
|------|-----|----------------------|
| 00:00 | Kirish | Mavzu va dars rejasi |
| 00:12 | Platforma bilan tanishuv | Ommaviy bosh sahifa: hisoblagichlar, imkoniyatlar, Rasch haqida, baholash shkalasi |
| 00:52 | Telegram bot | Majburiy obuna, ro'yxatdan o'tish, test yaratish sehrgari, testni topshirish, natija va javoblar tahlili |
| 03:15 | Web ilova | Bosh sahifa, tez amallar, testlar ro'yxati |
| 03:44 | Testni topshirish | 10 savolli testni to'liq topshirish — javob darhol saqlanadi |
| 04:32 | Natija va tahlil | Natija ekrani, «Natijalarim», javoblar tahlili |
| 05:05 | Matematik klaviatura | 45 savolli milliy shablon: ko'p javobli savol, ochiq savol, klaviatura, SymPy tekshiruvi |
| 06:19 | Sertifikat va testlarim | Sertifikatlar bo'limi va o'z testlarini boshqarish |
| 06:36 | Boshqaruv paneli | Kirish, ko'rsatkichlar, testlar, Rasch hisobi, ID kodlar, urinishlar, sertifikatlar, foydalanuvchilar, amallar tarixi |
| 08:37 | Sertifikatni tekshirish | Ochiq tekshiruv sahifasi: raqam kiritish va natija |
| 09:07 | Xulosa | Nimalar ko'rsatildi va foydali buyruqlar |

---

## Skriptlar

### `tools/video_prepare.py`

Videoda **ochiq savollar** va **matematik klaviatura** ko'rinishi uchun
faol (hali hech kim topshirmagan) 45 savolli milliy shablon testini
yaratadi. Demo ma'lumotdagi testlar allaqachon yakunlangan bo'lgani uchun
ular bu ish uchun yaramaydi.

Shuningdek video foydalanuvchisining faol testlardagi eski urinishlarini
tozalaydi — videoni qayta yozganda test «allaqachon topshirilgan» holatda
qolib ketmasin. Yakunlangan demo testlardagi natijalarga tegilmaydi.

Yaratilgan test nomi `DEMO` bilan boshlanadi, shuning uchun
`python tools/demo_data.py --clean` uni ham o'chiradi.

### `tools/video_bot_dialog.py`

Botning to'liq foydalanuvchi oqimini o'tkazadi va suhbatni
`data/video/bot_dialog.json` fayliga yozadi. Telegram serveriga
murojaat qilinmaydi: `Bot.session` xotiradagi soxta sessiya bilan
almashtiriladi, lekin **handler'lar, middleware'lar va matnlar haqiqiy**.

Oqim: `/start` → majburiy obuna → ro'yxatdan o'tish → test yaratish
sehrgari → testni topshirish → natija → javoblar tahlili.

Skript ishchi bazada ishlaydi, foydalanuvchilari `900000801` va
`900000802` — demo diapazonda, ya'ni `demo_data.py --clean` ularni
tozalaydi.

### `tools/video_lesson.py`

Asosiy skript. Playwright orqali Chromium'ni boshqaradi va butun
jarayonni video qilib yozadi.

Sozlamalar (muhit o'zgaruvchilari orqali):

| O'zgaruvchi | Standart | Vazifasi |
|-------------|----------|----------|
| `VIDEO_SITE` | `http://127.0.0.1:8000` | qaysi manzil yoziladi |
| `VIDEO_SPEED` | `1.0` | sur'at: `0.3` — tez sinov, `1.3` — sekinroq |

Tez sinov (oqim buzilmaganini tekshirish uchun):

```powershell
$env:VIDEO_SPEED="0.3"; python tools\video_lesson.py
```

---

## Ichki qismi qanday ishlaydi

**Izohlar.** Har bir sahifaga JavaScript orqali uchta qatlam qo'shiladi:
pastdagi izoh paneli, o'ng yuqoridagi modul yorlig'i va (web ilova
sahnalarida) chap tomondagi izoh ustuni. Sahifa almashganda ular qayta
qo'yiladi.

**Kursor.** Playwright videosida haqiqiy sichqoncha ko'rinmaydi, shuning
uchun sahifaga SVG kursor qo'yiladi: u bosiladigan element ustiga silliq
suriladi, so'ng bosish joyida halqacha animatsiyasi chiqadi va shundan
keyingina haqiqiy bosish bajariladi.

**Telegram suhbati.** `bot_dialog.json` dagi yozuv Telegram ko'rinishidagi
sahifada qayta o'ynatiladi: «yozmoqda...» nuqtalari, xabar pufakchalari,
inline va reply tugmalar. Keyingi qadamda bosiladigan tugma sariq rang
bilan ajratiladi.

**Test topshirish.** Joriy savol raqami ekrandan o'qiladi va javob aynan
o'sha savolning kalitiga qarab tanlanadi. Ilovaning o'ziga xos xususiyati
hisobga olingan: bitta javobli savolda javob tanlangach ilova **o'zi**
keyingi savolga o'tadi, shuning uchun «Keyingi» tugmasi bosilmaydi.
3- va 7-savolga ataylab xato javob beriladi — natija tahlili bo'sh
ko'rinmasligi uchun (yakuniy natija: 8/10, 80%).

**Mini App autentifikatsiyasi.** Brauzerda Telegram yo'q, shuning uchun
`X-Debug-User` sarlavhasi ishlatiladi (faqat `DEBUG=True` da ishlaydi —
`apps/miniapp/auth.py`). Sahifaga `window.Telegram.WebApp` ning minimal
taqlidi ham qo'yiladi.

**MP4.** Playwright video'ni VP8/webm ko'rinishida yozadi, o'zi bilan
kelgan `ffmpeg` da esa H.264 kodlagichi yo'q. Shu sababli `imageio-ffmpeg`
paketidagi to'liq `ffmpeg` ishlatiladi. Agar u topilmasa, video faqat
`webm` formatida qoladi — bu ham brauzerlarda va Telegram'da ochiladi.

---

## Kerakli paketlar

```powershell
pip install playwright imageio-ffmpeg
python -m playwright install chromium
```

---

## Yozuvdan keyin

```powershell
python tools\demo_data.py --clean
powershell -ExecutionPolicy Bypass -File .\toxtatish.ps1
```

Videoda `.env` fayli, `BOT_TOKEN` yoki haqiqiy foydalanuvchilarning
telefon raqamlari ko'rinmaydi: skript faqat ilova sahifalarini ochadi,
terminal esa umuman yozilmaydi. Panelga kirishda parol yozilayotgani
ko'rinadi, lekin maydon nuqtalar bilan to'ladi — bu demo hisob
(`demo_admin`), haqiqiy parol emas.
