"""Ro'yxatdan o'tish holatlari."""

from aiogram.fsm.state import State, StatesGroup


class RegistrationStates(StatesGroup):
    """Ism-familiya va telefon raqamini kiritish bosqichlari."""

    waiting_full_name = State()
    waiting_phone = State()
