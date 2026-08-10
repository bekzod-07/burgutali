"""
Boshqaruv panelining URL xaritasi.

Django ning standart admin paneli ishlatilmaydi — barcha boshqaruv shu
yerda: testlar, savollar, urinishlar, ID kodlar, sertifikatlar,
foydalanuvchilar va amallar tarixi.
"""

from django.urls import path

from . import views

app_name = "dashboard"

urlpatterns = [
    # --- Autentifikatsiya ---
    path("kirish/", views.LoginView.as_view(), name="login"),
    path("chiqish/", views.logout_view, name="logout"),
    path("tg/", views.telegram_entry, name="telegram_entry"),
    path("tg-kirish/", views.telegram_login, name="telegram_login"),

    # --- Asosiy ---
    path("", views.index, name="index"),

    # --- Testlar ---
    path("testlar/", views.exam_list, name="exam_list"),
    path("testlar/yangi/", views.exam_create, name="exam_create"),
    path("testlar/<int:pk>/", views.exam_detail, name="exam_detail"),
    path("testlar/<int:pk>/ochirish/", views.exam_delete, name="exam_delete"),
    path("testlar/<int:pk>/nusxa/", views.exam_duplicate, name="exam_duplicate"),
    path("testlar/<int:pk>/savollar/", views.exam_questions, name="exam_questions"),
    path(
        "testlar/<int:pk>/savollar/<int:question_id>/",
        views.question_edit,
        name="question_edit",
    ),
    path("testlar/<int:pk>/natijalar/", views.exam_results, name="exam_results"),
    path("testlar/<int:pk>/kodlar/", views.exam_codes, name="exam_codes"),
    path("testlar/<int:pk>/amal/<str:action>/", views.exam_action, name="exam_action"),

    # --- Eksport ---
    path("testlar/<int:pk>/eksport/natijalar.xlsx", views.export_results_excel, name="export_results_excel"),
    path("testlar/<int:pk>/eksport/natijalar.pdf", views.export_results_pdf, name="export_results_pdf"),
    path("testlar/<int:pk>/eksport/ishtirokchilar.xlsx", views.export_participants_excel, name="export_participants"),
    path("partiya/<int:pk>/eksport/kodlar.xlsx", views.export_codes_excel, name="export_codes"),

    # --- Urinishlar (natijalar) ---
    path("urinishlar/", views.attempt_list, name="attempt_list"),
    path("urinish/<int:pk>/", views.attempt_detail, name="attempt_detail"),
    path("urinish/<int:pk>/amal/<str:action>/", views.attempt_action, name="attempt_action"),

    # --- ID kodlar ---
    path("kod/<int:pk>/amal/<str:action>/", views.code_action, name="code_action"),

    # --- Sertifikatlar ---
    path("sertifikatlar/", views.certificate_list, name="certificate_list"),
    path(
        "sertifikat/<int:pk>/amal/<str:action>/",
        views.certificate_action,
        name="certificate_action",
    ),

    # --- Foydalanuvchilar ---
    path("foydalanuvchilar/", views.user_list, name="user_list"),
    path("foydalanuvchi/<int:pk>/", views.user_detail, name="user_detail"),
    path(
        "foydalanuvchi/<int:pk>/amal/<str:action>/",
        views.user_action,
        name="user_action",
    ),

    # --- Amallar tarixi ---
    path("tarix/", views.audit_list, name="audit_list"),
]
