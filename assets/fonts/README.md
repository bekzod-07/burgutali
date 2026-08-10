# Sertifikat shriftlari

Sertifikat PDF sida o‘zbek lotin alifbosidagi maxsus belgilar (`oʻ`, `gʻ`)
to‘g‘ri chiqishi uchun Unicode TTF shrift kerak.

## Tavsiya etiladigan shriftlar

Quyidagi fayllarni shu katalogga joylang:

```
DejaVuSans.ttf
DejaVuSans-Bold.ttf
```

Yuklab olish: <https://dejavu-fonts.github.io/>

## Muqobil variantlar

Katalog bo‘sh bo‘lsa, tizim shriftlari avtomatik izlanadi:

| Tizim | Izlanadigan shriftlar |
|-------|----------------------|
| Windows | `arial.ttf`, `segoeui.ttf`, `tahoma.ttf` |
| Linux | `DejaVuSans.ttf`, `LiberationSans-Regular.ttf`, `FreeSans.ttf` |
| macOS | `/Library/Fonts`, `/System/Library/Fonts` |

Hech qanday shrift topilmasa, ReportLab ning standart `Helvetica` shrifti
ishlatiladi va matn avtomatik ravishda Latin-1 ga moslashtiriladi —
sertifikat baribir yaratiladi, faqat apostroflar oddiy `'` ko‘rinishida chiqadi.

Batafsil: `apps/certificates/fonts.py`
