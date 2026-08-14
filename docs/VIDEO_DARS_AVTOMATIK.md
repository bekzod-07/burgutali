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

> **Ovozli.** Darsni o'zbek tilida **diktor o'qib boradi**: har bir sahna
> matni Microsoft Edge ning neyron ovozi (`uz-UZ-SardorNeural`) bilan
> sintez qilinadi, sahna esa o'sha gap tugagunicha ekranda turadi. Ovoz
> olinmasa (internet yo'q yoki `edge-tts` o'rnatilmagan), skript jimgina
> ovozsiz videoni yozib beradi.

---

## Tez ishga tushirish

```powershell
# 1. Platforma ishlab turishi kerak
powershell -ExecutionPolicy Bypass -File .\ishga_tushirish.ps1

# 2. Namoyish ma'lumotlari
python tools\demo_data.py --reset

# 3. Video uchun faol test + video foydalanuvchisining eski urinishlarini
#    tozalash (HAR SAFAR yozishdan oldin bajariladi)
python tools\video_prepare.py

# 4. Bot suhbatini yozib olish
python tools\video_bot_dialog.py

# 5. Videoni yozish
python tools\video_lesson.py
```

> **3-qadam majburiy.** Video foydalanuvchisi testni allaqachon
> topshirgan bo'lsa, «Boshlash» tugmasi chiqmaydi va test topshirish
> sahnasi yozilmaydi.

Natija:

| Fayl | Izoh |
|------|------|
| `data/video/dars.mp4` | asosiy fayl (H.264 + AAC ovoz, 1280×720, 25 kadr/sek) |
| `data/video/dars.webm` | brauzer yozgan asl nusxa (ovozsiz, VP8) |
| `data/video/dars_ovoz.wav` | yig'ilgan diktor yo'lagi |
| `data/video/dars.srt` | subtitrlar — diktor matni, taymkodlari bilan |
| `data/video/boblar.txt` | bob taymkodlari — YouTube tavsifiga tayyor |
| `data/video/bot_dialog.json` | yozib olingan bot suhbati |
| `data/video/voice/` | ovoz keshi (bir marta yuklanadi, keyin qayta ishlatiladi) |

---

## Video tuzilishi

Umumiy davomiyligi — **taxminan 18 daqiqa 30 soniya** (diktor matni 62 ta
gap, 14 daqiqa nutq). Taymkodlar har bir yozuvdan keyin
`data/video/boblar.txt` fayliga yoziladi; quyidagilar — oxirgi yozuvdan:

| Vaqt | Bob | Nimalar ko'rsatiladi |
|------|-----|----------------------|
| 00:00 | Kirish | Mavzu va dars rejasi |
| 00:48 | Platforma bilan tanishuv | Ommaviy bosh sahifa: hisoblagichlar, imkoniyatlar, Rasch haqida, baholash shkalasi |
| 02:09 | Telegram bot | Majburiy obuna, ro'yxatdan o'tish, test yaratish sehrgari, testni topshirish, natija va javoblar tahlili |
| 04:37 | Web ilova | Bosh sahifa, tez amallar, kod bo'yicha testga kirish |
| 06:00 | Testni topshirish | 10 savolli testni javoblar varaqasida to'liq topshirish |
| 08:03 | Natija va tahlil | Natija ekrani, «Natijalarim», javoblar tahlili |
| 09:04 | Matematik klaviatura | 45 savolli milliy shablon: ko'p javobli savol, ochiq savol, klaviatura, SymPy tekshiruvi |
| 11:19 | Sertifikat va testlarim | Sertifikatlar bo'limi va o'z testlarini boshqarish |
| 12:04 | Boshqaruv paneli | Kirish, ko'rsatkichlar, testlar, test yaratish, savollarni tahrirlash, Rasch natijalari va qiyinchilik diagrammasi, ID kodlar, urinishlar, sertifikatlar, foydalanuvchilar, amallar tarixi |
| 16:54 | Sertifikatni tekshirish | Ochiq tekshiruv sahifasi: raqam kiritish va natija |
| 17:41 | Xulosa | Nimalar ko'rsatildi va foydali buyruqlar |

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
| `VIDEO_SPEED` | `1.0` | jim tanaffuslar sur'ati: `0.3` — tez sinov |
| `VIDEO_VOICE` | `uz-UZ-SardorNeural` | diktor ovozi (`uz-UZ-MadinaNeural` — ayol) |
| `VIDEO_VOICE_RATE` | `+6%` | gapirish tezligi |
| `VIDEO_VOICE_OFF` | — | `1` bo'lsa ovoz umuman yozilmaydi |
| `VIDEO_VOICE_WAIT` | `1` | `0` — ovoz keshga yig'iladi, lekin sahna kutmaydi |
| `VIDEO_CAPTIONS` | `0` | `1` — ekran ustida matn izohlari ham chiqadi |

Tez sinov (oqim buzilmaganini tekshirish uchun):

```powershell
$env:VIDEO_SPEED="0.3"; $env:VIDEO_VOICE_OFF="1"; python tools\video_lesson.py
```

Ovoz keshini oldindan to'ldirish (birinchi yozuv silliq ketishi uchun):

```powershell
$env:VIDEO_SPEED="0.3"; $env:VIDEO_VOICE_WAIT="0"; python tools\video_lesson.py
```

---

## Ichki qismi qanday ishlaydi

**Izohlar.** Sahna matnini diktor gapirib bergani uchun ekran ustida
hech qanday matn qatlami chiqmaydi — video toza ekran yozuvi bo'lib
qoladi, faqat bosqichlar orasida sarlavha ekranlari ko'rinadi.
`VIDEO_CAPTIONS=1` qilinsa, eski ko'rinish qaytadi: pastdagi izoh
yo'lagi, o'ng yuqoridagi modul yorlig'i va chap tomondagi izoh ustuni
(bu holda web ilova sahifasi o'ng tomonga suriladi, `html.ls-shift`).
Matnli variant kerak bo'lganlar uchun `dars.srt` subtitri har doim
yoziladi.

**Kursor.** Playwright videosida haqiqiy sichqoncha ko'rinmaydi, shuning
uchun sahifaga SVG kursor qo'yiladi: u bosiladigan element ustiga silliq
suriladi, so'ng bosish joyida halqacha animatsiyasi chiqadi va shundan
keyingina haqiqiy bosish bajariladi.

**Telegram suhbati.** `bot_dialog.json` dagi yozuv Telegram ko'rinishidagi
sahifada qayta o'ynatiladi: «yozmoqda...» nuqtalari, xabar pufakchalari,
inline va reply tugmalar. Keyingi qadamda bosiladigan tugma sariq rang
bilan ajratiladi.

**Test topshirish.** Testga **kod orqali** kiriladi — ishtirokchiga
testlar ro'yxati ko'rsatilmaydi. Javoblar varaqasida barcha savollar
bitta ekranda bo'lgani uchun skript savol tartiblarini varaqadan o'qib
oladi va har biriga o'z kaliti bo'yicha javob belgilaydi. 3- va
7-savolga ataylab xato javob beriladi — natija tahlili bo'sh
ko'rinmasligi uchun (yakuniy natija: 8/10, 80%).

**Mini App autentifikatsiyasi.** Ilova faqat Telegram ichida ochiladi,
brauzerda esa `?debug_user=<telegram_id>` parametri bilan kiriladi va
so'rovlarga `X-Debug-User` sarlavhasi qo'shiladi (ikkalasi ham faqat
`DEBUG=True` da ishlaydi — `apps/miniapp/auth.py`). `telegram.org` dagi
haqiqiy skript yozuv vaqtida bloklanadi, o'rniga `window.Telegram.WebApp`
ning minimal taqlidi qo'yiladi.

**MP4.** Playwright video'ni VP8/webm ko'rinishida yozadi, o'zi bilan
kelgan `ffmpeg` da esa H.264 kodlagichi yo'q. Shu sababli `imageio-ffmpeg`
paketidagi to'liq `ffmpeg` ishlatiladi. Agar u topilmasa, video faqat
`webm` formatida qoladi — bu ham brauzerlarda va Telegram'da ochiladi.

---

## Kerakli paketlar

```powershell
pip install playwright imageio-ffmpeg edge-tts
python -m playwright install chromium
```

## Ovoz qanday qo'shiladi

`tools/video_voice.py` uchta ishni bajaradi:

1. **Sintez.** Ekrandagi izoh matni avval diktor uchun tayyorlanadi:
   HTML teglari olib tashlanadi, belgilar so'zga aylantiriladi
   (`θ` → «teta», `90.14` → «to'qson butun o'n to'rt`, `1–32` →
   «1 dan 32 gacha», `KR-20` → «Ka-Er yigirma»). Natija `data/video/voice/`
   ga keshlanadi — ikkinchi yozuvda internet kerak bo'lmaydi.
2. **Vaqt jadvali.** Har bir gap yozuv boshidan qaysi soniyada
   boshlanishi yozib boriladi. Sahna gap tugagunicha ekranda turadi,
   shuning uchun ovoz va tasvir bir-biriga mos keladi. Diktor
   stsenariydagi tanaffusdan uzoqroq gapirsa, ortiqcha vaqt keyingi jim
   tanaffuslardan ushlab qolinadi — «o'lik» kadr qolmaydi.
3. **Yig'ish.** Yozuv tugagach barcha gaplar bitta WAV yo'lagiga
   teriladi va `ffmpeg` bilan videoga qo'shiladi; shu vaqt jadvalidan
   `dars.srt` subtitri ham yoziladi.

Sahna matnini o'zgartirish uchun `tools/video_lesson.py` dagi
`lesson.say(...)`, `lesson.side(...)` va `chat.note(...)` chaqiruvlariga
qarang: `voice="..."` argumenti berilgan bo'lsa, diktor aynan shu matnni
o'qiydi (ekranda esa qisqaroq izoh turadi).

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
