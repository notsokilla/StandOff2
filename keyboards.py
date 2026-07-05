from aiogram.types import InlineKeyboardMarkup, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
import random


def get_quiz_keyboard(correct_answer: str, wrong_answer: str) -> InlineKeyboardMarkup:
    """Клавиатура для вопроса теста"""
    builder = InlineKeyboardBuilder()
    
    # Перемешиваем ответы для случайного порядка
    answers = [correct_answer, wrong_answer]
    random.shuffle(answers)
    
    for answer in answers:
        builder.button(text=answer, callback_data=f"answer_{answer}")
    
    builder.adjust(1)
    return builder.as_markup()

def get_cancel_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура с кнопкой отмены"""
    builder = ReplyKeyboardBuilder()
    builder.button(text="❌ Отменить")
    builder.adjust(1)
    return builder.as_markup(resize_keyboard=True)


def get_prize_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура с кнопкой ПРИЗ"""
    builder = InlineKeyboardBuilder()
    builder.button(text="ПРИЗ ", callback_data="prize")
    builder.adjust(1)
    return builder.as_markup()


def get_start_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура для старта"""
    builder = ReplyKeyboardBuilder()
    builder.button(text="Начать тест")
    builder.adjust(1)
    return builder.as_markup(resize_keyboard=True)


def get_admin_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура админ панели"""
    builder = InlineKeyboardBuilder()
    builder.button(text="📊 Статистика", callback_data="admin_stats")
    builder.button(text="👥 Все пользователи", callback_data="admin_users")
    builder.button(text="📢 Рассылка", callback_data="admin_broadcast")
    builder.adjust(1)
    return builder.as_markup()