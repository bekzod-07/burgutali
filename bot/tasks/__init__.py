"""Bot fon vazifalari."""

from .scheduler import start_scheduler  # noqa: F401

__all__ = ["start_scheduler"]

# Eslatma: `broadcast` moduli ataylab shu yerda import qilinmaydi — u
# Django modellariga tayanadi va `start_scheduler` ichida, muhit tayyor
# bo'lgandan keyin yuklanadi.
