"""Test topshirish holatlari."""

from aiogram.fsm.state import State, StatesGroup


class TakingStates(StatesGroup):
    """
    Testga kirish va javob berish bosqichlari.

    kod kiritish -> (pullik testda) ID kod -> savollarga javob berish ->
    yakuniy tasdiqlash -> (esse baholanadigan testda) esse balli
    """

    waiting_exam_code = State()
    waiting_access_code = State()
    answering = State()
    confirming = State()
    waiting_essay = State()
