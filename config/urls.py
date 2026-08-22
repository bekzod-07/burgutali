"""
Loyihaning asosiy URL xaritasi.

  /                — ommaviy bosh sahifa
  /panel/          — boshqaruv paneli (Django admin o'rniga)
  /app/            — Telegram Mini App (web ilova)
  /verify/<raqam>/ — sertifikatni QR orqali tekshirish

Django ning standart admin paneli ishlatilmaydi: barcha boshqaruv
`apps/dashboard` dagi o'z panelimizda, o'zbek tilida va o'z dizaynida.
"""

from django.conf import settings
from django.conf.urls.static import static
from django.templatetags.static import static as static_url
from django.urls import include, path
from django.views.generic.base import RedirectView

from apps.common import views as common_views

urlpatterns = [
    path("", common_views.home, name="home"),
    path("sog/", common_views.healthcheck, name="healthcheck"),
    # Brauzerlar belgini shu manzildan ham so'raydi — logda 404 qolmasin.
    path(
        "favicon.ico",
        RedirectView.as_view(url=static_url("favicon.svg"), permanent=True),
        name="favicon",
    ),
    path("panel/", include(("apps.dashboard.urls", "dashboard"), namespace="dashboard")),
    path("app/", include(("apps.miniapp.urls", "miniapp"), namespace="miniapp")),
    path("verify/", include(("apps.certificates.urls", "certificates"), namespace="certificates")),
]

handler404 = "apps.common.views.error_404"
handler500 = "apps.common.views.error_500"

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
