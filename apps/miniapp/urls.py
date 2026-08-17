"""
Mini App URL xaritasi.

  /app/                     — web ilova (bir sahifali)
  /app/klaviatura/          — faqat matematik klaviatura (bot uchun)
  /app/api/...              — JSON API
"""

from django.urls import path

from . import api, views

app_name = "miniapp"

urlpatterns = [
    # --- Sahifalar ---
    path("", views.app_shell, name="app"),
    path("klaviatura/", views.keyboard, name="keyboard"),

    # --- Brauzerdan kirish (Telegram Login Widget) ---
    path("kirish/", views.login_page, name="login"),
    path("tg-kirish/", views.tg_login, name="tg_login"),
    path("chiqish/", views.logout_page, name="logout"),

    # --- API: umumiy ---
    path("api/boshlash/", api.bootstrap, name="api_bootstrap"),
    path("api/profil/", api.profile_update, name="api_profile_update"),
    path("api/tekshir/", views.api_validate, name="api_validate"),
    path("api/ifoda/", api.check_expression, name="api_expression"),

    # --- API: testlar ---
    path("api/testlar/", api.exam_list, name="api_exams"),
    path("api/test/<str:code>/", api.exam_detail, name="api_exam"),
    path("api/test/<str:code>/boshlash/", api.exam_start, name="api_exam_start"),
    path("api/test/<str:code>/reyting/", api.exam_rating, name="api_exam_rating"),

    # --- API: urinishlar ---
    path("api/urinish/<int:attempt_id>/", api.attempt_detail, name="api_attempt"),
    path("api/urinish/<int:attempt_id>/javob/", api.attempt_answer, name="api_attempt_answer"),
    path("api/urinish/<int:attempt_id>/yuborish/", api.attempt_submit, name="api_attempt_submit"),
    path("api/urinish/<int:attempt_id>/bekor/", api.attempt_cancel, name="api_attempt_cancel"),
    path("api/urinish/<int:attempt_id>/natija/", api.attempt_result, name="api_attempt_result"),
    path(
        "api/urinish/<int:attempt_id>/sertifikat/",
        api.attempt_certificate,
        name="api_attempt_certificate",
    ),

    # --- API: sertifikatlar ---
    path("api/sertifikatlar/", api.certificate_list, name="api_certificates"),

    # --- API: mening testlarim ---
    path("api/mening-testlarim/", api.my_exams, name="api_my_exams"),
    path("api/test-yaratish/", api.exam_create, name="api_exam_create"),
    path("api/test/<str:code>/boshqaruv/", api.exam_manage, name="api_exam_manage"),
    path("api/test/<str:code>/amal/", api.exam_action, name="api_exam_action"),
    path("api/test/<str:code>/kodlar/", api.exam_codes, name="api_exam_codes"),
    path("api/test/<str:code>/ochirish/", api.exam_delete, name="api_exam_delete"),
    path(
        "api/test/<str:code>/ochirish-tekshiruv/",
        api.exam_delete_preview,
        name="api_exam_delete_preview",
    ),
]
