from aiogram.types import InlineKeyboardMarkup, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
import random

def get_cancel_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура с кнопкой отмены"""
    builder = ReplyKeyboardBuilder()
    builder.button(text="❌ Отменить")
    builder.adjust(1)
    return builder.as_markup(resize_keyboard=True)

def get_quiz_keyboard(correct_answer: str, wrong_answer: str) -> InlineKeyboardMarkup:
    """Клавиатура для вопроса теста"""
    builder = InlineKeyboardBuilder()
    answers = [correct_answer, wrong_answer]
    random.shuffle(answers)
    for answer in answers:
        builder.button(text=answer, callback_data=f"answer_{answer}")
    builder.adjust(1)
    return builder.as_markup()

def get_prize_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура с кнопкой ПРИЗ"""
    builder = InlineKeyboardBuilder()
    builder.button(text="ПРИЗ 💰", callback_data="prize")
    builder.adjust(1)
    return builder.as_markup()

def get_start_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура для старта"""
    builder = ReplyKeyboardBuilder()
    builder.button(text="Начать тест")
    builder.adjust(1)
    return builder.as_markup(resize_keyboard=True)

def get_admin_main_keyboard() -> InlineKeyboardMarkup:
    """Главное меню админа"""
    builder = InlineKeyboardBuilder()
    builder.button(text="📊 Статистика", callback_data="admin_stats")
    builder.button(text="👥 Пользователи", callback_data="admin_users_page_1")
    builder.button(text="📨 Рассылки", callback_data="admin_broadcast")
    builder.adjust(2)
    return builder.as_markup()

def get_users_pagination_keyboard(current_page: int, total_pages: int) -> InlineKeyboardMarkup:
    """Клавиатура пагинации пользователей"""
    builder = InlineKeyboardBuilder()
    if current_page > 1:
        builder.button(text="⬅️ Назад", callback_data=f"admin_users_page_{current_page - 1}")
    builder.button(text=f"📄 {current_page}/{total_pages}", callback_data="ignore")
    if current_page < total_pages:
        builder.button(text="Вперед ➡️", callback_data=f"admin_users_page_{current_page + 1}")
    builder.adjust(3)
    return builder.as_markup()

# ========== НОВЫЕ ФУНКЦИИ ДЛЯ РАССЫЛОК ==========

def get_broadcast_menu_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура меню рассылок"""
    builder = InlineKeyboardBuilder()
    for msg_id in range(1, 6):  # 5 готовых рассылок
        builder.button(text=f"📨 Рассылка #{msg_id}", callback_data=f"broadcast_{msg_id}")
    builder.button(text="⬅️ Назад", callback_data="admin_main")
    builder.adjust(1)
    return builder.as_markup()

def get_broadcast_confirm_keyboard(broadcast_id: int) -> InlineKeyboardMarkup:
    """Клавиатура подтверждения рассылки"""
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Отправить всем", callback_data=f"broadcast_confirm_{broadcast_id}")
    builder.button(text="❌ Отмена", callback_data="admin_broadcast")
    builder.adjust(2)
    return builder.as_markup()