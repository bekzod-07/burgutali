"""ID kodlar bilan ishlash (asinxron)."""

from __future__ import annotations

from asgiref.sync import sync_to_async

from apps.accesscodes import services as code_services
from apps.accesscodes.generator import is_valid_format, normalize_code
from apps.accesscodes.models import AccessCode, CodeBatch

# --------------------------------------------------------------------------

create_codes = sync_to_async(code_services.create_codes, thread_sensitive=True)
check_code = sync_to_async(code_services.check_code, thread_sensitive=True)
activate_code = sync_to_async(code_services.activate_code, thread_sensitive=True)
consume_code = sync_to_async(code_services.consume_code, thread_sensitive=True)
release_code = sync_to_async(code_services.release_code, thread_sensitive=True)
find_active_code = sync_to_async(code_services.find_active_code, thread_sensitive=True)
code_statistics = sync_to_async(code_services.code_statistics, thread_sensitive=True)


@sync_to_async(thread_sensitive=True)
def get_code(code_id: int) -> AccessCode | None:
    """ID bo'yicha kodni qaytaradi."""
    return AccessCode.objects.select_related("exam").filter(pk=code_id).first()


@sync_to_async(thread_sensitive=True)
def export_codes_excel(batch: CodeBatch) -> bytes:
    """Partiyadagi kodlarni Excel ko'rinishida qaytaradi."""
    from apps.exports.excel import codes_workbook

    return codes_workbook(batch)


@sync_to_async(thread_sensitive=True)
def sample_codes(batch: CodeBatch, limit: int = 3) -> list[str]:
    """Partiyadan bir nechta namuna kod."""
    return list(batch.codes.order_by("id").values_list("code", flat=True)[:limit])


__all__ = [
    "create_codes",
    "check_code",
    "activate_code",
    "consume_code",
    "release_code",
    "find_active_code",
    "code_statistics",
    "get_code",
    "export_codes_excel",
    "sample_codes",
    "normalize_code",
    "is_valid_format",
]
