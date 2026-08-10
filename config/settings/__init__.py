"""
Sozlamalar paketi.

`DJANGO_ENV` muhit o'zgaruvchisiga qarab mos sozlamalar yuklanadi:
  * dev  (standart) — ishlab chiqish rejimi;
  * prod             — ishlab chiqarish (production) rejimi.
"""

from core.env import get_str

_ENV = get_str("DJANGO_ENV", "dev").lower()

if _ENV in {"prod", "production"}:
    from .prod import *  # noqa: F401,F403
else:
    from .dev import *  # noqa: F401,F403
