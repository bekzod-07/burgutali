"""Sertifikatni tekshirish sahifalarining URL xaritasi."""

from django.urls import path

from . import views

app_name = "certificates"

urlpatterns = [
    path("", views.verify_form, name="form"),
    path("<str:number>/", views.verify_detail, name="detail"),
    path("<str:number>/yuklab-olish/", views.download, name="download"),
]
