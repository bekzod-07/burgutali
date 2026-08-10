"""View lar uchun umumiy mixin va dekoratorlar."""

from __future__ import annotations

from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied


def staff_required(view_func):
    """Faqat xodim (staff) huquqiga ega foydalanuvchilarga ruxsat beradi."""

    @wraps(view_func)
    @login_required
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_staff:
            raise PermissionDenied("Bu sahifaga kirish huquqingiz yo'q.")
        return view_func(request, *args, **kwargs)

    return _wrapped


def superuser_required(view_func):
    """Faqat superuser (asosiy admin) uchun."""

    @wraps(view_func)
    @login_required
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_superuser:
            raise PermissionDenied("Bu amal faqat asosiy admin uchun.")
        return view_func(request, *args, **kwargs)

    return _wrapped
