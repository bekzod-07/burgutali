"""Barcha ilovalar uchun umumiy abstrakt modellar."""

from __future__ import annotations

from django.db import models


class TimeStampedModel(models.Model):
    """Yaratilgan va yangilangan vaqtni avtomatik saqlaydigan bazaviy model."""

    created_at = models.DateTimeField("Yaratilgan vaqt", auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField("Yangilangan vaqt", auto_now=True)

    class Meta:
        abstract = True


class ActiveQuerySet(models.QuerySet):
    """`is_active` maydoni bo'lgan modellar uchun qulay so'rovlar."""

    def active(self):
        return self.filter(is_active=True)

    def inactive(self):
        return self.filter(is_active=False)
