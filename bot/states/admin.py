"""Administrator paneli holatlari."""

from aiogram.fsm.state import State, StatesGroup


class AdminStates(StatesGroup):
    """ID kodlar yaratish va boshqa administrator amallari."""

    waiting_code_quantity = State()
