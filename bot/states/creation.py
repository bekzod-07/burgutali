"""Test yaratish sehrgarining holatlari."""

from aiogram.fsm.state import State, StatesGroup


class CreateExamStates(StatesGroup):
    """
    Test yaratish bosqichlari.

    tur -> nom -> tuzilma -> savollar soni -> javob kalitlari ->
    tugash vaqti -> natija ko'rinishi -> sertifikat -> yakun
    """

    choosing_type = State()
    waiting_title = State()
    choosing_structure = State()
    waiting_question_count = State()
    waiting_single_keys = State()
    waiting_multi_keys = State()
    waiting_open_keys = State()
    choosing_duration = State()
    waiting_custom_duration = State()
    choosing_visibility = State()
    choosing_certificate = State()
