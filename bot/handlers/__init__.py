"""
Handler routerlarini Dispatcher ga ulash.

Tartib muhim: umumiy (bekor qilish, asosiy menyu) routerlar birinchi,
noma'lum xabarlarni ushlaydigan router esa eng oxirida turadi.
"""

from __future__ import annotations

from aiogram import Dispatcher


def setup_routers(dispatcher: Dispatcher) -> None:
    """Barcha routerlarni ro'yxatdan o'tkazadi."""
    from . import (
        certificate,
        errors,
        fallback,
        menu,
        my_tests,
        registration,
        results,
        start,
        subscription,
    )
    from .admin import router as admin_router
    from .create import router as create_router
    from .taking import router as taking_router

    dispatcher.include_router(menu.router)
    dispatcher.include_router(start.router)
    dispatcher.include_router(subscription.router)
    dispatcher.include_router(registration.router)
    dispatcher.include_router(create_router)
    dispatcher.include_router(taking_router)
    dispatcher.include_router(results.router)
    dispatcher.include_router(certificate.router)
    dispatcher.include_router(my_tests.router)
    dispatcher.include_router(admin_router)
    dispatcher.include_router(fallback.router)

    errors.setup(dispatcher)


__all__ = ["setup_routers"]
