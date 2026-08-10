# Video dars — to'liq stsenariy

**Mavzu:** Rasch Math Platform — Telegram bot, web ilova va boshqaruv paneli
**Davomiyligi:** ~30 daqiqa (8 modul)
**Auditoriya:** o'qituvchilar, test tashkilotchilari, platforma administratorlari

Har bir sahna uchun uchta narsa berilgan:

| Belgi | Ma'nosi |
|-------|---------|
| **EKRAN** | Ekranda nima ko'rinib turishi kerak |
| **HARAKAT** | Sichqoncha bilan nima qilinadi |
| **MATN** | So'zma-so'z aytiladigan gap (o'qib ketaverasiz) |

---

## 0. Yozuvdan oldingi tayyorgarlik

### 0.1. Texnik sozlamalar

| Parametr | Tavsiya |
|----------|---------|
| Dastur | OBS Studio (bepul) |
| Ruxsat | 1920×1080, 30 kadr/sek |
| Mikrofon | Tashqi mikrofon; xonada aks-sado bo'lmasin |
| Brauzer masshtabi | **125%** — matn videoda o'qilarli bo'lsin |
| Sichqoncha | OBS'da «Highlight cursor» yoqilsin |
| Telefon | Telegram ilovasi ochiq, ekran yozuvi yoqilgan (yoki Telegram Desktop) |

### 0.2. Xavfsizlik — yozuvdan oldin albatta

Bu narsalar **ekranga tushmasligi kerak**:

- `.env` faylining ichi (`BOT_TOKEN` — bu parol bilan barobar)
- `logs/` ichidagi fayllar (token log'ga tushishi mumkin)
- Haqiqiy ishtirokchilarning telefon raqamlari va ismlari
- Terminalda `Get-Content .env` kabi buyruqlar

> Agar token tasodifan ekranga tushsa — yozuvni to'xtating, @BotFather'da
> `/revoke` qiling va yangi token oling.

### 0.3. Demo ma'lumotlarni tayyorlash

Bo'sh panel videoda yomon ko'rinadi. Shuning uchun avval demo ma'lumot yarating:

```powershell
python tools\demo_data.py --reset
```

Skript quyidagilarni yaratadi:

- **3 ta test**: oddiy (20 savol), bepul RASH (45 savol, milliy shablon),
  pullik RASH (30 savol, 500 ta ID kod)
- **28 ta ishtirokchi** o'zbekcha ismlar bilan
- **56 ta topshirilgan javob**, hisoblangan natijalar va reyting
- **18 ta sertifikat**

Oxirida ekranga bo'sh ID kod chiqadi — videoda aynan shuni ishlatasiz.

Yozuv tugagach:

```powershell
python tools\demo_data.py --clean
```

### 0.4. Tizimni ishga tushirish

```powershell
powershell -ExecutionPolicy Bypass -File .\ishga_tushirish.ps1
```

Skript tugagach ekrandagi manzillarni **bloknotga ko'chirib qo'ying** — video
davomida kerak bo'ladi.

### 0.5. Yozuvdan oldingi tekshiruv ro'yxati

- [ ] `ishga_tushirish.ps1` «TAYYOR» deb yozdi
- [ ] Botda `/start` ishlayapti
- [ ] Web ilova ochilyapti (menyu tugmasi orqali)
- [ ] Panelga kira olyapsiz
- [ ] Demo ma'lumot yaratilgan
- [ ] Barcha ortiqcha oynalar, xabarnomalar o'chirilgan
- [ ] Brauzerda faqat kerakli ikkita varaq ochiq

---

## 1-MODUL. Kirish va umumiy ko'rinish
**0:00 – 2:30**

### Sahna 1.1 — Salomlashuv (0:00 – 0:35)

**EKRAN:** Platformaning ommaviy bosh sahifasi (`/`)

**MATN:**
> Assalomu alaykum. Ushbu darsda matematika testlarini o'tkazish va Rasch
> modeli asosida baholash platformasi bilan tanishamiz.
>
> Platforma uch qismdan iborat: Telegram bot, web ilova va boshqaruv paneli.
> Dars oxirida siz o'z testingizni yaratib, uni o'tkazib, natijalarni
> hisoblab, sertifikat berishni bilib olasiz.

### Sahna 1.2 — Nima uchun Rasch? (0:35 – 1:30)

**EKRAN:** Bosh sahifadagi «Platforma imkoniyatlari» bloki

**HARAKAT:** Sekin pastga aylantiring

**MATN:**
> Oddiy testda natija — to'g'ri javoblar soni. Lekin bu adolatli emas:
> o'n dona oson savolga javob bergan o'quvchi va o'n dona qiyin savolga
> javob bergan o'quvchi bir xil ball oladi.
>
> Rasch modeli — bu masalani hal qiladi. Har bir savolning qiyinligi
> ma'lumotlardan hisoblanadi, o'quvchining bilim darajasi esa aynan shu
> qiyinlikni hisobga olgan holda baholanadi.
>
> Natijada ball nol dan to'qson butun o'n to'rt gacha bo'lgan shkalaga
> keltiriladi — Milliy sertifikatdagi kabi.

### Sahna 1.3 — Baholash shkalasi (1:30 – 2:00)

**EKRAN:** Bosh sahifadagi «Baholash shkalasi» jadvali

**MATN:**
> Mana daraja jadvali. Yetmish balldan yuqori — A plus. Oltmish besh dan
> yetmish gacha — A. Va hokazo. Qirq olti balldan past bo'lsa, daraja
> berilmaydi. Bu chegaralar texnik topshiriqqa aynan mos.

### Sahna 1.4 — Uch xil test turi (2:00 – 2:30)

**EKRAN:** Bosh sahifa, «Uch xil test turi» kartochkasi

**MATN:**
> Platformada uch xil test bor.
>
> Birinchisi — oddiy test. Uni har qanday ro'yxatdan o'tgan foydalanuvchi
> yaratadi, natija to'g'ri javoblar soni bo'yicha chiqadi.
>
> Ikkinchisi — bepul RASH testi. Bunda natija Rasch modeli bilan hisoblanadi.
>
> Uchinchisi — pullik RASH testi. Uni faqat asosiy admin yaratadi, kirish
> bir martalik ID kod orqali va oxirida sertifikat beriladi.
>
> Endi amalda ko'ramiz.

---

## 2-MODUL. Tizimni ishga tushirish
**2:30 – 5:00**

### Sahna 2.1 — Bitta buyruq (2:30 – 3:30)

**EKRAN:** PowerShell oynasi, loyiha katalogida

**HARAKAT:** Buyruqni yozing va Enter bosing:
```powershell
powershell -ExecutionPolicy Bypass -File .\ishga_tushirish.ps1
```

**MATN:**
> Butun tizim bitta buyruq bilan ishga tushadi. Bu skript oltita ishni
> bajaradi: eski jarayonlarni to'xtatadi, internetga chiqish uchun xavfsiz
> tunnel ochadi, olingan manzilni sozlamalarga yozadi, ma'lumotlar bazasini
> yangilaydi, web serverni va Telegram botni ishga tushiradi, so'ng hammasini
> tekshirib chiqadi.

### Sahna 2.2 — Natijani ko'rish (3:30 – 4:20)

**EKRAN:** Skriptning «TAYYOR» xulosasi

**HARAKAT:** Manzillar ro'yxatini kursor bilan ko'rsating

**MATN:**
> Mana, tayyor. Skript bizga to'rtta manzil berdi.
>
> Birinchisi — web ilova. Ishtirokchilar aynan shu yerda test topshiradi.
>
> Ikkinchisi — boshqaruv paneli.
>
> Uchinchisi — panelga Telegram orqali kirish manzili.
>
> To'rtinchisi — sertifikatni tekshirish sahifasi.
>
> Diqqat: bu manzil har safar o'zgaradi. Skript uni sozlamalarga o'zi
> yozib qo'yadi, shuning uchun siz hech narsa qilishingiz shart emas.

### Sahna 2.3 — Nima uchun tunnel kerak? (4:20 – 5:00)

**EKRAN:** Terminal

**MATN:**
> Telegram web ilovasini ochishi uchun sayt internetdan ko'rinadigan va
> HTTPS protokolida bo'lishi shart. Uy kompyuteri esa internetdan
> ko'rinmaydi. Tunnel aynan shu muammoni hal qiladi.
>
> Doimiy foydalanish uchun o'z domeningizni ulash kerak — bu haqda
> hujjatlarning O'rnatish bo'limida yozilgan.
>
> To'xtatish uchun esa alohida skript bor: toxtatish nuqta pe es bir.

---

## 3-MODUL. Bot: ro'yxatdan o'tish
**5:00 – 7:30**

### Sahna 3.1 — Birinchi ishga tushirish (5:00 – 5:50)

**EKRAN:** Telefon yoki Telegram Desktop, bot suhbati

**HARAKAT:** `/start` yuboring

**MATN:**
> Endi bot tomoniga o'tamiz. Yangi foydalanuvchi botni ochib, start
> tugmasini bosadi.
>
> Birinchi navbatda bot majburiy obunani tekshiradi. Agar foydalanuvchi
> kanalga a'zo bo'lmasa, davom eta olmaydi. Bu qoida hammaga tegishli:
> test topshiradiganlarga ham, test yaratadiganlarga ham. Faqat asosiy
> adminlar bundan mustasno.

### Sahna 3.2 — Obunani tekshirish (5:50 – 6:20)

**HARAKAT:** «Kanalga a'zo bo'lish» → kanalga a'zo bo'ling → «A'zolikni tekshirish»

**MATN:**
> A'zo bo'lgach, tekshirish tugmasini bosamiz. Bot Telegram orqali
> haqiqatan a'zo ekanimizni tekshiradi va davom etishga ruxsat beradi.

### Sahna 3.3 — Ism va telefon (6:20 – 7:30)

**HARAKAT:** «Boshlash» → ism-familiya yozing → telefon tugmasini bosing

**MATN:**
> Endi ro'yxatdan o'tamiz. Avval ism va familiya. E'tibor bering — bot
> faqat bitta so'zni qabul qilmaydi, kamida ikkita so'z kerak. Bu
> sertifikatda to'liq ism chiqishi uchun muhim.
>
> Keyin telefon raqami. Uni qo'lda yozish shart emas — pastdagi maxsus
> tugma orqali Telegram o'zi yuboradi. Bu xato raqam kiritishning oldini
> oladi.
>
> Tayyor. Endi asosiy menyu ochildi. Yuqorida — «Ilovani ochish» tugmasi,
> pastda esa bot orqali bajariladigan amallar.

---

## 4-MODUL. Test yaratish
**7:30 – 12:00**

### Sahna 4.1 — Turini tanlash (7:30 – 8:20)

**HARAKAT:** «Test yaratish» → «1-tur. Oddiy test»

**MATN:**
> Test yaratishni bot orqali ko'ramiz — bu eng tez yo'l.
>
> Bot uchta turni taklif qilyapti. Diqqat qiling: oddiy foydalanuvchida
> faqat ikkita variant ko'rinadi. Uchinchi tur — pullik test — faqat
> asosiy adminda chiqadi.
>
> Biz hozir oddiy testni tanlaymiz.

### Sahna 4.2 — Nom va savollar soni (8:20 – 9:10)

**HARAKAT:** Nom yozing: `Algebra — nazorat ishi` → savollar soni: `10`

**MATN:**
> Test nomini yozamiz. Bu nom sertifikatda ham, reytingda ham chiqadi.
>
> Endi savollar soni. Tayyor variantlar bor — o'n, yigirma, o'ttiz,
> qirq besh, ellik, yuz. Yoki o'zingiz istalgan sonni yozishingiz mumkin.
> Biz o'nta savol tanlaymiz.

### Sahna 4.3 — Javob kaliti (9:10 – 10:20)

**HARAKAT:** Kalit yozing: `ABCDABCDAB`

**MATN:**
> Endi eng muhim qadam — javob kaliti.
>
> Kalitni uch xil ko'rinishda yozish mumkin. Birinchisi — harflarni
> ketma-ket: a be se de a be se de a be. Ikkinchisi — probel bilan
> ajratib. Uchinchisi — raqamlab: bir chiziqcha a, ikki chiziqcha be.
>
> Bot kalit uzunligini tekshiradi. Agar o'nta savolga to'qqizta javob
> yozsangiz, xato haqida aytadi.

> **HARAKAT (ixtiyoriy):** Ataylab `ABCD` yozib, xatoni ko'rsating.
> Bu tomoshabinga tizim xatolarni ushlashini ko'rsatadi.

### Sahna 4.4 — Sozlamalar va yakun (10:20 – 11:20)

**HARAKAT:** Tugash vaqti: «Cheklovsiz» → natija ko'rinishi: «Ha»

**MATN:**
> Tugash vaqtini belgilaymiz. Cheklovsiz qoldirsak, testni qo'lda
> yopamiz. Yoki bir soat, uch soat, bir kun, bir hafta.
>
> Keyingi savol — natija qatnashchilarga ko'rinsinmi. Agar «Ha» desak,
> ishtirokchi test yakunlangach o'z natijasini va qaysi savolda xato
> qilganini ko'ra oladi.
>
> Mana, test tayyor. Bot bizga test kodini berdi. Aynan shu kodni
> ishtirokchilarga tarqatasiz. Pastda havola ham bor — uni bosgan odam
> to'g'ridan-to'g'ri shu testga tushadi.

### Sahna 4.5 — Milliy sertifikat shabloni (11:20 – 12:00)

**HARAKAT:** Yana «Test yaratish» → «2-tur» → «Milliy sertifikat shabloni»

**MATN:**
> Endi RASH testini ko'ramiz. Bu yerda qo'shimcha tanlov paydo bo'ladi —
> milliy sertifikat shabloni.
>
> Bu shablon qirq beshta savoldan iborat. Birinchi o'ttiz ikkitasi — a,
> be, se, de variantli. O'ttiz uchdan o'ttiz beshgacha — a dan ef gacha,
> bir yoki bir nechta to'g'ri javobli. O'ttiz oltidan qirq beshgacha esa
> variantsiz: har birida a va be javob maydonlari.
>
> Ochiq javoblar uchun kalit shunday yoziladi: har bir savol alohida
> qatorda, a va be javoblari nuqta-vergul bilan ajratiladi.

---

## 5-MODUL. Web ilova: test topshirish
**12:00 – 17:30**

### Sahna 5.1 — Ilovani ochish (12:00 – 12:40)

**EKRAN:** Telefon, bot suhbati

**HARAKAT:** Xabar maydoni yonidagi **«Ilova»** tugmasini bosing

**MATN:**
> Endi eng qiziq qismi — web ilova.
>
> Ilovani uch xil ochish mumkin: xabar maydoni yonidagi doimiy tugma
> orqali, asosiy menyudagi «Ilovani ochish» tugmasi orqali yoki slesh
> ilova buyrug'i bilan.
>
> Ilova Telegram ichida ochiladi — hech qayerga chiqish shart emas.

### Sahna 5.2 — Bosh sahifa (12:40 – 13:20)

**EKRAN:** Ilova bosh sahifasi

**HARAKAT:** Pastdagi beshta bo'limni ko'rsating

**MATN:**
> Mana bosh sahifa. Yuqorida ismimiz, pastda uchta ko'rsatkich:
> natijalar soni, sertifikatlar soni va o'zimiz yaratgan testlar soni.
>
> Pastda beshta bo'lim: bosh sahifa, testlar, natijalar, sertifikat va
> testlarim.
>
> Agar tugallanmagan testingiz bo'lsa, u shu yerda birinchi bo'lib
> chiqadi va bir bosishda davom ettirasiz.

### Sahna 5.3 — Testga kirish (13:20 – 14:10)

**HARAKAT:** «Testlar» bo'limi → test kodini kiriting → «Testni topish»

**MATN:**
> Testlar bo'limiga o'tamiz. Yuqorida — test kodi bo'yicha kirish.
> Pastda — ochiq testlar ro'yxati.
>
> Kodni kiritamiz. Ilova test haqidagi ma'lumotni ko'rsatdi: turi,
> savollar soni, maksimal ball, tugash vaqti va nechta odam qatnashgani.
>
> «Testni boshlash» tugmasini bosamiz.

### Sahna 5.4 — Savollarga javob berish (14:10 – 15:30)

**HARAKAT:** Bir nechta savolga javob bering, palitradan sakrab o'ting

**MATN:**
> Mana test ekrani. Yuqorida — progress chizig'i va savollar palitrasi.
> Javob berilgan savollar yashil rangda, joriy savol esa ramka bilan
> ajratilgan.
>
> Javobni tanlaymiz — ilova avtomatik keyingi savolga o'tadi. Har bir
> javob shu zahoti serverga saqlanadi. Ya'ni internet uzilsa yoki ilova
> yopilsa ham, hech narsa yo'qolmaydi.
>
> Palitradagi istalgan raqamni bosib, o'sha savolga qaytishingiz mumkin.

### Sahna 5.5 — Ko'p javobli savol (15:30 – 16:00)

**HARAKAT:** 33-savolga o'ting (milliy shablonli testda)

**MATN:**
> Bu savolda bir nechta to'g'ri javob bo'lishi mumkin. Katakchalar
> to'rtburchak shaklda — bir nechtasini belgilash mumkin.
>
> Muhim qoida: javob **aynan** kalitga mos kelishi kerak. Ortiqcha yoki
> kam belgilangan variant xato hisoblanadi, yarim ball berilmaydi.

### Sahna 5.6 — Matematik klaviatura (16:00 – 17:00)

**HARAKAT:** 36-savolga o'ting, klaviatura bilan `sqrt(2)/2` yozing

**MATN:**
> Va mana eng qiziq qismi — ochiq javobli savollar.
>
> Bu yerda variant yo'q, javobni o'zimiz yozamiz. Buning uchun maxsus
> matematik klaviatura bor: kasr, ildiz, daraja, pi, e, sinus, kosinus,
> tangens, kotangens, logarifm, modul, taqqoslash belgilari.
>
> Yozayotganimizda pastda javobning tahlil qilingan ko'rinishi chiqib
> turadi. Agar ifodada xato bo'lsa, darhol ko'rasiz.
>
> Eng muhimi: tizim javobni **matematik ma'no bo'yicha** tekshiradi.
> Ya'ni bir bo'lingan ikki, nol butun besh va ikkining minus birinchi
> darajasi — bularning hammasi bir xil javob hisoblanadi. O'quvchi
> qanday yozganiga qarab jazolanmaydi.

### Sahna 5.7 — Yakunlash (17:00 – 17:30)

**HARAKAT:** «Testni yakunlash» → tasdiqlash oynasi → «Ha, yuborilsin»

**MATN:**
> Testni yakunlaymiz. Ilova ogohlantiradi: nechta savolga javob berilgan
> va qaysilari javobsiz qolgan.
>
> Tasdiqlaymiz. Javoblar qabul qilindi.
>
> Diqqat: yakuniy javobni faqat bir marta yuborish mumkin. Ortga qaytish
> yo'q.

---

## 6-MODUL. Natijalar, reyting va sertifikat
**17:30 – 21:00**

### Sahna 6.1 — Oddiy testda natija (17:30 – 18:20)

**EKRAN:** Ilovaning natija ekrani

**MATN:**
> Oddiy testda natija darhol chiqadi: to'g'ri javoblar soni, foiz,
> xato va javobsiz savollar.
>
> Pastda — har bir savol bo'yicha tahlil. Yashil katak — to'g'ri javob,
> qizil — xato, sariq — qisman, kulrang — javobsiz.
>
> Undan pastda batafsil jadval: siz nima yozgansiz va to'g'ri javob nima
> edi. Bu o'quvchi uchun eng foydali qism — u xatosini ko'radi va
> tushunadi.

### Sahna 6.2 — RASH testida natija (18:20 – 19:10)

**EKRAN:** RASH testining natija ekrani

**MATN:**
> RASH testida esa vaziyat boshqacha. Test tugashi bilan natija
> chiqmaydi — chunki har bir savolning qiyinligi barcha ishtirokchilarning
> javoblari asosida hisoblanadi.
>
> Shuning uchun ishtirokchi «natijalar hali e'lon qilinmagan» degan
> xabarni ko'radi. Tashkilotchi hisoblab, natijalarni e'lon qilgandan
> keyin esa RASH balli, daraja va reyting o'rni paydo bo'ladi.
>
> Mana bunday: ball yetmish butun etmish ikki, daraja A plus, reyting —
> o'n ikkinchi o'rin.

### Sahna 6.3 — Reyting (19:10 – 19:40)

**HARAKAT:** «Reyting» tugmasini bosing

**MATN:**
> Reytingda birinchi uch o'rin alohida rang bilan ajratilgan, o'zingizning
> o'rningiz esa ko'k fonda belgilanadi.

### Sahna 6.4 — Sertifikat (19:40 – 21:00)

**HARAKAT:** «Sertifikat» bo'limi → «PDF yuklab olish» → PDF'ni oching

**MATN:**
> Endi sertifikat. U faqat pullik RASH testida va faqat natijalar e'lon
> qilingandan keyin beriladi. Bu ataylab shunday: noto'g'ri hisoblangan
> natija bilan sertifikat tarqalib ketmasligi kerak.
>
> Yuklab olamiz. Mana sertifikat.
>
> Unda: noyob raqam, ism-familiya, test nomi va sanasi, RASH balli,
> daraja, reyting o'rni, tashkilotchi nomi va berilgan sana.
>
> Pastki o'ng burchakda QR kod bor. Uni skanerlasak, tekshirish sahifasi
> ochiladi.

**HARAKAT:** QR kodni skanerlang yoki «Haqiqiyligini tekshirish» tugmasini bosing

**MATN:**
> Mana tekshirish sahifasi: sertifikat haqiqiy, ism-familiya, test nomi,
> natija, sana va raqam. Ish beruvchi yoki oliygoh shu orqali
> sertifikatning haqiqiyligini bir soniyada tekshira oladi.
>
> Har bir sertifikat raqami faqat bitta odam va bitta natijaga tegishli.

---

## 7-MODUL. Boshqaruv paneli
**21:00 – 27:00**

### Sahna 7.1 — Panelga kirish (21:00 – 21:50)

**EKRAN:** Bot, «Admin panel» bosilgan

**HARAKAT:** «Web panel» tugmasini bosing

**MATN:**
> Endi boshqaruv paneliga o'tamiz.
>
> Panelga ikki xil kirish mumkin. Birinchisi — login va parol bilan,
> brauzerdan. Ikkinchisi — to'g'ridan-to'g'ri Telegramdan.
>
> Botdagi «Admin panel» ni bosamiz, so'ng «Web panel». Panel Telegram
> ichida ochildi va bizni avtomatik tanidi — login ham, parol ham
> so'ralmadi.
>
> Bu Telegram imzosi orqali ishlaydi. Faqat sozlamalarda admin deb
> belgilangan odamlar kira oladi, boshqalarga ruxsat berilmaydi.

> **Eslatma:** Django'ning standart admin paneli bu loyihada umuman yo'q.
> Barcha boshqaruv — faqat shu panelda, o'zbek tilida.

### Sahna 7.2 — Umumiy ko'rinish (21:50 – 22:30)

**EKRAN:** Panel bosh sahifasi (kompyuterda ochib olish qulayroq)

**MATN:**
> Bosh sahifada asosiy ko'rsatkichlar: foydalanuvchilar soni, ro'yxatdan
> o'tganlar, testlar, sertifikatlar, faol testlar, topshirilgan javoblar
> va ID kodlar holati.
>
> Pastda — so'nggi testlar va so'nggi natijalar. Har biri bosiladigan.

### Sahna 7.3 — Testlar bo'limi (22:30 – 23:40)

**HARAKAT:** «Testlar» → filtrlarni ko'rsating → bitta testni oching

**MATN:**
> Testlar bo'limida barcha testlar ro'yxati. Turi va holati bo'yicha
> filtrlash, nomi yoki kodi bo'yicha qidirish mumkin.
>
> O'ng tomonda har bir test uchun tezkor tugmalar: natijalar, ID kodlar,
> nusxa yaratish va o'chirish.
>
> Testni ochamiz. Yuqorida boshqaruv tugmalari: faollashtirish, yopish,
> natijalarni hisoblash, e'lon qilish, sertifikatlar yaratish va eksport.
>
> Pastda test haqida ma'lumot va statistika: qatnashchilar soni, o'rtacha
> ball, eng yuqori va eng past natija, standart og'ish va ishonchlilik
> koeffitsiyenti.

### Sahna 7.4 — Savollarni tahrirlash (23:40 – 24:40)

**HARAKAT:** «Savollar» → jadvalni ko'rsating → bitta savolni tahrirlash

**MATN:**
> Savollar bo'limi. Bu yerda barcha javob kalitlarini bitta jadvalda
> tez o'zgartirish mumkin.
>
> Qiyinlik ustuni — Rasch parametri. «Qulflash» katagi belgilansa,
> avtomatik kalibrlash bu qiymatni o'zgartirmaydi. Bu ilmiy tilda anchor
> savol deyiladi: qiyinligi oldindan ma'lum bo'lgan savollar.
>
> Har bir savolni to'liq tahrirlash ham mumkin. Bu yerda savol matni,
> turi, variantlar soni, javob kaliti, ochiq javoblar, sonli xatolik
> chegarasi va Rasch parametrlari bor.
>
> «Saqlab, keyingisiga» tugmasi bilan savollarni ketma-ket tahrirlash
> qulay.

### Sahna 7.5 — Natijalar va urinishlar (24:40 – 25:40)

**HARAKAT:** «Natijalar» bo'limi → bitta urinishni oching

**MATN:**
> Natijalar bo'limida barcha urinishlar. Test, holat yoki ism bo'yicha
> filtrlanadi.
>
> Bitta urinishni ochamiz. Chap tomonda ishtirokchi ma'lumotlari, o'ng
> tomonda natija: to'g'ri javoblar, xatolar, foiz, teta qiymati, standart
> ball va daraja.
>
> Pastda har bir savol bo'yicha jadval: nima yozgan, to'g'ri javob nima
> edi va necha ball olgan.
>
> Yuqorida amallar: qayta baholash, sertifikat berish va o'chirish.
> «Qayta baholash» — agar javob kalitini o'zgartirgan bo'lsangiz kerak
> bo'ladi.

### Sahna 7.6 — ID kodlar (25:40 – 26:20)

**HARAKAT:** Pullik testni oching → «ID kodlar»

**MATN:**
> Pullik testda ID kodlar bo'limi bor. Yuqorida statistika: jami kodlar,
> bo'sh, faollashtirilgan va ishlatilganlari.
>
> Yangi kodlar yaratish uchun miqdorni tanlaymiz — besh yuz, ming, ming
> besh yuz, ikki ming yoki uch ming. Yaratilgan kodlar Excel fayl
> ko'rinishida yuklab olinadi.
>
> Pastdagi jadvalda har bir kod: holati, kim ishlatgani, qachon. Kerak
> bo'lsa kodni bekor qilish yoki ishlatilmagan holatiga qaytarish mumkin.

### Sahna 7.7 — Foydalanuvchilar, sertifikatlar, tarix (26:20 – 27:00)

**HARAKAT:** Har bir bo'limni qisqacha ko'rsating

**MATN:**
> Foydalanuvchilar bo'limida har bir odamning to'liq tarixi ko'rinadi:
> topshirgan testlari, yaratgan testlari, sertifikatlari va ID kodlari.
> Shu yerdan bloklash yoki admin qilish mumkin.
>
> Sertifikatlar bo'limida — barcha berilgan sertifikatlar. PDF ni qayta
> yaratish, bekor qilish, tiklash yoki o'chirish mumkin.
>
> Va nihoyat, amallar tarixi. Bu jurnalda kim, qachon, qanday amal
> bajargani yozib boriladi: ro'yxatdan o'tish, test yaratish, ID kod
> ishlatish, sertifikat olish. Bu xavfsizlik uchun juda muhim.

---

## 8-MODUL. Pullik test: to'liq sikl
**27:00 – 30:00**

### Sahna 8.1 — ID kod hayotiy sikli (27:00 – 28:10)

**EKRAN:** Panel, ID kodlar jadvali

**MATN:**
> Endi pullik testning eng muhim mexanizmini tushuntiraman — ID kod
> hayotiy sikli.
>
> Kod uchta holatda bo'ladi: ishlatilmagan, faollashtirilgan va
> ishlatilgan.
>
> Foydalanuvchi kodni kiritganda u faqat **faollashtirilgan** holatga
> o'tadi. Bu paytda kod hali «kuygan» emas.
>
> Va faqat yakuniy javob bazaga muvaffaqiyatli saqlangandan keyingina kod
> **ishlatilgan** deb belgilanadi.
>
> Nima uchun shunday? Tasavvur qiling: odam kodni kiritdi va shu payt
> interneti uzildi. Agar kod darhol yopilib qolsa, u pulini bekorga
> to'lagan bo'lardi. Bizda esa u qaytib kirib, testni davom ettiradi.

### Sahna 8.2 — Bir kod — bir javob (28:10 – 28:50)

**HARAKAT:** Ishlatilgan kodni yana kiritib ko'ring

**MATN:**
> Ikkinchi muhim qoida: bir ID kod — faqat bitta yakuniy javob.
>
> Ishlatilgan kodni qayta kiritsak, bot rad etadi. Bazada esa qaysi kod
> orqali qaysi Telegram foydalanuvchi, qanday ism bilan, qaysi vaqtda va
> qaysi testga javob yuborgani saqlanib qoladi.

### Sahna 8.3 — Natijalarni e'lon qilish (28:50 – 29:30)

**HARAKAT:** Panel → test → «Natijalarni hisoblash» → «Natijalarni e'lon qilish»

**MATN:**
> Test tugagach ketma-ketlik shunday: avval testni yopamiz, keyin
> natijalarni hisoblaymiz.
>
> Shu paytda Rasch modeli ishlaydi: har bir savolning qiyinligi
> kalibrlanadi, har bir ishtirokchining teta qiymati topiladi va u ballga
> aylantiriladi.
>
> Natijalarni ko'rib chiqamiz. Agar hammasi joyida bo'lsa — e'lon
> qilamiz. Shu paytda barcha qatnashchilarga botdan xabar boradi va
> sertifikatlar avtomatik yaratiladi.

### Sahna 8.4 — Yakun (29:30 – 30:00)

**EKRAN:** Panel bosh sahifasi

**MATN:**
> Xulosa qilib aytganda: platforma test yaratishdan tortib sertifikat
> berishgacha bo'lgan butun jarayonni qamrab oladi.
>
> Ishtirokchi uchun — qulay web ilova. Tashkilotchi uchun — to'liq
> boshqaruv paneli. Baholash esa xalqaro amaliyotda tan olingan Rasch
> modeli asosida.
>
> Savollaringiz bo'lsa, izohlarda yozing. Diqqatingiz uchun rahmat.

---

## 9. Montaj bo'yicha maslahatlar

| Nima | Qanday |
|------|--------|
| Kutish paytlari | Hisoblash va yuklashlarni 2× tezlashtiring |
| Muhim tugmalar | Zoom qiling yoki doira bilan belgilang |
| Bo'limlar orasi | 0.5 soniyalik qora kadr yoki sarlavha |
| Musiqa | Juda past ovozda (−25 dB), gap paytida yanada past |
| Subtitr | Avtomatik subtitr yoqing — o'zbekcha atamalar noto'g'ri chiqsa qo'lda tuzating |

### Ekranga chiqadigan sarlavhalar (title card)

```
1. Rasch Math Platform
2. Tizimni ishga tushirish
3. Ro'yxatdan o'tish
4. Test yaratish
5. Web ilovada test topshirish
6. Natijalar va sertifikat
7. Boshqaruv paneli
8. Pullik test va ID kodlar
```

---

## 10. YouTube uchun tayyor matnlar

### Sarlavha

```
Rasch Math Platform — Telegram bot orqali test o'tkazish va IRT baholash (to'liq dars)
```

### Tavsif

```
Matematika testlarini Telegram bot orqali o'tkazish va Rasch (IRT-1PL)
modeli asosida baholash platformasi bilan tanishamiz.

Darsda ko'rib chiqamiz:
- uch xil test turi va ular qanday farq qiladi
- Milliy sertifikat formatidagi 45 savolli test
- web ilovada test topshirish va matematik klaviatura
- javoblarni matematik ekvivalentlik bo'yicha tekshirish
- Rasch modeli: savol qiyinligi va o'quvchi darajasi
- 90.14 ballik shkala va darajalar
- QR kodli avtomatik sertifikat
- bir martalik ID kodlar va ularning hayotiy sikli
- to'liq boshqaruv paneli

Boblar:
00:00 Kirish va umumiy ko'rinish
02:30 Tizimni ishga tushirish
05:00 Botda ro'yxatdan o'tish
07:30 Test yaratish
12:00 Web ilovada test topshirish
17:30 Natijalar, reyting va sertifikat
21:00 Boshqaruv paneli
27:00 Pullik test va ID kodlar
```

### Teglar

```
rasch model, irt, milliy sertifikat, telegram bot, test platformasi,
matematika testi, django, telegram mini app, online test, ta'lim
```

---

## 11. Yozuvdan keyin

```powershell
python tools\demo_data.py --clean
powershell -ExecutionPolicy Bypass -File .\toxtatish.ps1
```

Va yana bir bor tekshiring: videoda `.env`, token yoki haqiqiy telefon
raqamlari ko'rinib qolmaganmi.
