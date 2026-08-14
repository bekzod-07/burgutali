# Texnik topshiriqqa moslik jadvali

Ushbu hujjat TZ (SRS + «Rash bot» hujjati) dagi har bir talab qayerda
bajarilganini ko‘rsatadi.

---

## A. SRS — Software Requirements Specification

| № | Talab | Bajarilishi |
|---|-------|-------------|
| 1 | Rasch modeli asosida matematik testlarni Telegram bot orqali baholash | `bot/` + `apps/rasch/` |
| 2 | Rollar: Administrator va Ishtirokchi | `apps/users/models.BotUser.is_admin`, `bot/middlewares/user_mw.py` |
| 3 | Jami 45 ta savol | `core/constants.NATIONAL_TOTAL_QUESTIONS`, `apps/exams/structures.national_specs()` |
| 3 | 1–32: A, B, C, D (bitta javob) | `Question.Kind.SINGLE`, `NATIONAL_SINGLE_RANGE` |
| 3 | 33–35: A–F (moslashtirish — bitta to‘g‘ri javob) | `Question.Kind.MULTI`, `NATIONAL_MULTI_RANGE` |
| 3 | 36–45: variantsiz, a) va b) maydonlar | `Question.Kind.OPEN` + `parts=2`, `NATIONAL_OPEN_RANGE` |
| 4 | Mini App matematik klaviatura | `static/mathpad/` — web ilova, boshqaruv paneli va `/app/klaviatura/` sahifasi uchun **yagona** klaviatura (raqamlar, π, e, a–c, x–z, kasr, ildizlar, darajalar, sin/cos/tan/cot va teskarilari, ln, log, log□, exp, qavslar; ortga/oldinga qaytarish va buferdan qo‘yish) |
| 4 | SymPy orqali ekvivalentlik (1/2 = 0.5, sin(pi/6)=0.5) | `core/math_expr.compare_answer()` |
| 5 | 3000 ta noyob 7 xonali ID | `core/constants.DEFAULT_CODE_BATCH = 3000`; kod formati TZ dagi `R7K4-8251` ko‘rinishida (8 belgi) — «Rash bot» hujjati aynan shu formatni talab qiladi |
| 5 | Har bir ID faqat bir marta ishlatiladi | `AccessCode.Status`, `uniq` cheklov, `consume_code()` |
| 5 | ID ishlatilgach bloklanadi | `apps/accesscodes/services.consume_code()` |
| 5 | Noto‘g‘ri/ishlatilgan ID bilan boshlab bo‘lmaydi | `apps/accesscodes/services.check_code()` |
| 6 | Ism, familiya va ID kiritish | `bot/handlers/registration.py`, `bot/handlers/taking/entry.py` |
| 6 | Ketma-ket 45 ta savol | `bot/handlers/taking/flow.send_question()` |
| 6 | Javoblar bazaga saqlanadi | `apps/attempts/services.save_answer()` — har bir javob darhol |
| 6 | «Javoblaringiz qabul qilindi» | `bot/texts/exam.SUBMITTED` |
| 7 | `P = exp(θ − b) / (1 + exp(θ − b))` | `apps/rasch/estimator.probability()` |
| 7 | Har bir savol uchun `b` saqlanadi | `Question.difficulty`, `Question.difficulty_b` |
| 7 | `θ` MLE yoki teng kuchli usul | `apps/rasch/estimator.estimate_theta()` (Newton-Raphson) |
| 8 | Maksimal standart ball 90.14 | `core/constants.MAX_BALL` |
| 8 | Daraja jadvali (C … A+) | `core/constants.GRADE_TABLE`, `grade_for_ball()` |
| 9 | Test va savollarni boshqarish | `apps/dashboard/views.exam_detail`, `exam_questions` |
| 9 | Javob kalitlarini kiritish | `apps/exams/keys.py`, panel + bot sehrgari |
| 9 | Rasch parametrlarini tahrirlash | `dashboard/exam_questions.html` (qiyinlik + «qulflash») |
| 9 | Excel/PDF eksport | `apps/exports/excel.py`, `apps/exports/pdf_report.py` |
| 9 | Ishtirokchilar statistikasi | `apps/attempts/models.ExamStatistics` |
| 9 | ID larni boshqarish | `apps/dashboard/views.exam_codes`, `bot/handlers/admin/codes.py` |
| 10 | Python 3.12+, Aiogram 3, SymPy, NumPy, SciPy, Pandas, Telegram Bot API, Mini App | `requirements.txt` |
| 10 | PostgreSQL | `DATABASE_URL` orqali; standart holatda SQLite (WAL) |
| 10 | SQLAlchemy | **Django ORM bilan almashtirilgan** — sabab: bitta sxema ustida ikkita ORM ishlatish migratsiya va tranzaksiya muammolarini keltiradi (`docs/ARXITEKTURA.md`, 1-bo‘lim) |
| 11 | Modulli, kengaytiriladigan arxitektura | `core/`, `apps/*/services.py`, `bot/handlers/*` |
| 11 | Kod hujjatlashtirilgan | har bir modul va funksiyada docstring |
| 11 | Xavfsizlik | `docs/ARXITEKTURA.md`, 10-bo‘lim |
| 11 | Zaxiralash mexanizmi | `docs/ORNATISH.md`, 10-bo‘lim |

---

## B. «Rash bot» hujjati

| Band | Talab | Bajarilishi |
|------|-------|-------------|
| 1 | Bot profilidagi «What can this bot do?» matni | `bot/texts/common.BOT_DESCRIPTION` — `set_my_description()` orqali avtomatik o‘rnatiladi |
| 2 | /start matni (aynan) | `bot/texts/start.WELCOME` |
| 2 | «Boshlash» tugmasi | `bot/keyboards/inline.start_button()` |
| 2 | Majburiy obuna @Burgutali | `bot/middlewares/subscription_mw.py`, `bot/utils/subscription.py` |
| 2 | Obuna /start va Boshlash da tekshiriladi | `bot/handlers/start._start_flow()` |
| 2 | «Kanalga a’zo bo‘lish» / «A’zolikni tekshirish» | `bot/keyboards/inline.subscription()` |
| 2 | «A’zolik tasdiqlandi» | `bot/texts/start.SUBSCRIPTION_CONFIRMED` |
| 2 | Obuna hammaga tegishli, adminlar mustasno | `SubscriptionMiddleware` (`is_admin` tekshiruvi) |
| 3 | «Ro‘yxatdan o‘tish» matni | `bot/texts/start.ASK_FULL_NAME` |
| 3 | Ism-familiya bazaga saqlanadi | `apps/users/services.save_full_name()` |
| 3 | Telefon Telegram kontakt tugmasi orqali | `bot/keyboards/reply.phone_request()` (`request_contact=True`) |
| **1-tur** | Oddiy testni har qanday foydalanuvchi yaratadi | `Exam.Type.SIMPLE`, `bot/handlers/create/` |
| 1-tur | Savollar soni: 10, 20, 30, 45, 50, 100 … | `core/constants.SIMPLE_TEST_SIZES` + ixtiyoriy son |
| 1-tur | A, B, C, D variantlar | `Question.Kind.SINGLE` |
| 1-tur | Yaratuvchi kalit kiritadi | `bot/handlers/create/keys.py` |
| 1-tur | Avtomatik tekshiruv | `apps/attempts/grading.py` |
| 1-tur | Natija = to‘g‘ri javoblar soni | `apps/rasch/scoring.simple_percent_score()` |
| 1-tur | RASH ishlatilmaydi | `Exam.uses_rasch` -> `False` |
| 1-tur | To‘g‘ri, noto‘g‘ri va foiz | `bot/texts/exam.SUBMITTED_WITH_RESULT` |
| 1-tur | Yaratuvchi barcha natija va reytingni ko‘radi | `bot/handlers/my_tests.py`, panel |
| 1-tur | Natijani ko‘rinadigan/ko‘rinmaydigan qilish | `Exam.show_results_to_participants` |
| 1-tur | Tugash vaqtini belgilash | `Exam.ends_at` + `auto_close_expired()` |
| 1-tur | Tugagach hamma natija va xatolarini ko‘radi | `apps/attempts/services.answer_review()` |
| **2-tur** | Bepul RASH testini har kim yaratadi | `Exam.Type.RASCH_FREE` |
| 2-tur | Natija RASH modeli asosida | `apps/rasch/services.calculate_exam()` |
| 2-tur | Yaratuvchi parametr va kalit kiritadi | sehrgar + panel |
| 2-tur | Test yakunlangach RASH hisoblanadi | `calculate_exam()` |
| 2-tur | Har bir qatnashchining RASH balli | `Attempt.ball` |
| 2-tur | RASH balliga qarab reyting | `_assign_ranks()` |
| 2-tur | Yaratuvchi statistikani ko‘radi | `ExamStatistics` |
| 2-tur | Sertifikat berilmaydi | `Exam.can_issue_certificate` -> `False` |
| **3-tur** | Faqat asosiy admin yaratadi | `inline.exam_types(is_admin)`, `TE.PAID_ADMIN_ONLY` |
| 3-tur | To‘lov bot orqali emas | to‘lov moduli yo‘q — TZ talabiga muvofiq |
| 3-tur | Admin ID kodlar generatsiya qiladi | `bot/handlers/admin/codes.py` |
| 3-tur | 500 / 1000 / 1500 / 2000 / «Boshqa miqdor» | `inline.code_quantities()` |
| 3-tur | Kodlar tasodifiy va takrorlanmas | `generator.generate_unique_codes()` (`secrets`) |
| 3-tur | Format `R7K4-8251` | `generator.make_code()` |
| 3-tur | Excel fayl: № / ID kod / Holati | `apps/exports/excel.codes_workbook()` |
| 3-tur | «ID kodingizni kiriting» | `bot/texts/exam.ASK_ACCESS_CODE` |
| 3-tur | 1) mavjudmi 2) shu testgami 3) ishlatilganmi | `check_code()` — aynan shu tartibda |
| 3-tur | «ID tasdiqlandi» | `bot/texts/exam.CODE_CONFIRMED` |
| 3-tur | 1 ID = 1 ta yakuniy javob | `uniq_submitted_attempt_per_user` + `consume_code()` |
| 3-tur | Takroriy urinishda xato xabari | `check_code()` -> «avval yuborilgan» |
| 3-tur | Kod kiritilishi bilan kuyib ketmasin | `activate_code()` -> `ACTIVATED` (hali ochiq) |
| 3-tur | Holatlar: Ishlatilmagan → Faollashtirilgan → Ishlatilgan | `AccessCode.Status` |
| 3-tur | Faqat javob saqlangach USED | `submit_attempt()` ichida `consume_code()` |
| 3-tur | Telegram ID, ism, vaqt, test saqlanadi | `AccessCode.telegram_id/full_name/used_at/attempt` |
| **31** | Natijalar e'lon qilingach sertifikat | `check_eligibility()` -> `status == PUBLISHED` |
| 31 | Dizayn Milliy sertifikat uslubida, lekin nusxa emas | `apps/certificates/pdf.py` — o‘z ranglari, emblemasi va nomi |
| 31 | Sertifikat raqami noyob | `Certificate.number` (`RM-YYYY-NNNNNN`) |
| 31 | Ism-familiya | `Certificate.full_name` |
| 31 | Test nomi | `Certificate.exam_title` |
| 31 | Test sanasi | `Certificate.exam_date` |
| 31 | RASH balli | `Certificate.ball` |
| 31 | Foiz ko‘rsatkichi | `Certificate.percent` |
| 31 | Daraja (A+, A, B+, B, C+, C) | `Certificate.grade` |
| 31 | Bo‘limlar bo‘yicha natija | `Certificate.section_scores` (`Question.section`) |
| 31 | Berilgan sana | `Certificate.issued_at` |
| 31 | Tashkilotchi/o‘qituvchi nomi | `Certificate.organizer_name` |
| 31 | QR-kod | `apps/certificates/qr.py` |
| 31 | QR: haqiqiylik, ism, test, natija, sana, raqam | `templates/certificates/verify_detail.html` |
| 31 | 1 raqam = 1 qatnashchi + 1 natija | `OneToOneField(Attempt)` + `unique` raqam |
| 31 | Natija xabari (ball, daraja, reyting) | `bot/texts/exam.RESULT_READY` |
| 31 | «Sertifikatni olish» tugmasi | `bot/texts/exam.BTN_GET_CERTIFICATE` |
| 31 | Bosilganda PDF yuboriladi | `bot/handlers/certificate.get_certificate()` |
| 31 | «Sertifikat berilsinmi? Ha / Yo‘q» | `bot/handlers/create/settings.py` |
| 31 | Kimlarga: hammaga yoki min. ball/darajadan yuqori | `Exam.CertificateScope` |
| 31 | Sertifikat darhol emas: RASH → tasdiq → sertifikat | `publish_results()` -> `issue_for_exam()` |
| 31 | 1-tur yo‘q, 2-tur yo‘q, 3-tur bor | `Exam.can_issue_certificate` |

---

## C. TZ dan ataylab chetlanishlar

| Talab | Nima qilindi | Sabab |
|-------|--------------|-------|
| SQLAlchemy | Django ORM | Bitta sxema ustida ikkita ORM — migratsiya tarixi ikkiga bo‘linadi, tranzaksiyalar bir-birini ko‘rmaydi. Web qismi to‘liq Django bo‘lgani uchun yagona ORM tanlandi. |
| «7 xonali ID» (SRS) | `R7K4-8251` (8 belgi) | «Rash bot» hujjati aynan shu formatni va namunalarni ko‘rsatgan; u kechroq va batafsilroq hujjat. |
| «3000 ta ID» (SRS) | 500/1000/1500/2000/3000/ixtiyoriy | «Rash bot» hujjatidagi variantlar qo‘shildi, 3000 ham saqlab qolindi. |

Barcha chetlanishlar funksionallikni kamaytirmaydi.

---

## D. TZ dan tashqari qo‘shilgan imkoniyatlar

| Imkoniyat | Qayerda |
|-----------|---------|
| **To‘liq web ilova** — testni topshirish, javoblarni tekshirish, natijani ko‘rish va sertifikat yuklab olish tugmalar orqali | `apps/miniapp/api.py`, `static/miniapp/js/app.js` |
| Web ilovada test **yaratish** va **o‘chirish**, boshqaruv ekrani | `api.exam_create`, `api.exam_delete`, `api.exam_action` |
| Panelda test yaratish formasi (tur, tuzilma, kalitlar bir sahifada) | `dashboard/exam_create.html` |
| Testni o‘chirish — nima yo‘qolishi oldindan ko‘rsatiladi, tasdiqlash majburiy | `exams/services.delete_exam()`, `deletion_summary()` |
| Testning to‘liq nusxasini yaratish (savollar va kalitlar bilan) | `exams/services.duplicate_exam()` |
| Botda test o‘chirish va nusxalash tugmalari | `bot/handlers/my_tests.py` |
| Tugallanmagan testni davom ettirish (web ilova bosh sahifasida) | `api.bootstrap` -> `drafts` |
| Emoji o‘rniga SVG ikonkalar tizimi | `templates/partials/icons.html` |
| `/ilova` buyrug‘i va botning doimiy menyu tugmasi | `bot/handlers/menu.open_web_app`, `bot/main.on_startup` |
| SymPy `parse_expr` ichidagi kod bajarish xavfidan himoya | `core/math_expr.is_safe_input()` + cheklangan `global_dict` |

---

## E. Tekshiruv qamrovi

| Skript | Tekshiruvlar | Nimani qamrab oladi |
|--------|--------------|---------------------|
| `selftest.py` | 538 | konstantalar, matn, SymPy (xavfsizlik hujumlari bilan), Rasch algoritmi, kalit tahlili, ID generatori, migratsiyalar, 45-savollik to‘liq oqim, oddiy test, pullik test + sertifikat, eksport, Mini App imzosi, web sahifalar, panel, bot modullari, chegaraviy holatlar, test kodining qayta ishlatilishi, savollar qiyinchiligi diagrammasi |
| `simulate.py` | 157 | botning haqiqiy oqimi: obuna → ro‘yxat → test yaratish → testga kirish → javob berish → yuborish → natija → admin paneli → ID kodlar → hisoblash → e'lon → sertifikat PDF |
