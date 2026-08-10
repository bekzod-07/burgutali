"""FSM holatlari (aiogram `StatesGroup`)."""

from .admin import AdminStates  # noqa: F401
from .creation import CreateExamStates  # noqa: F401
from .registration import RegistrationStates  # noqa: F401
from .taking import TakingStates  # noqa: F401

__all__ = [
    "RegistrationStates",
    "CreateExamStates",
    "TakingStates",
    "AdminStates",
]
