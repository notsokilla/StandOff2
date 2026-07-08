import asyncio
import logging
import os
import re
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import FSInputFile
from aiogram.client.session.aiohttp import AiohttpSession
from config import BOT_TOKEN, ADMIN_PASSWORD
from database import Database
from keyboards import (
    get_cancel_keyboard, get_quiz_keyboard, get_prize_keyboard, 
    get_start_keyboard, get_admin_keyboard
)
from data.maps_data import QUIZ_QUESTIONS, MAPS_DATA

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# ========== НАСТРОЙКА ПРОКСИ ==========
def get_session():
    """Создаёт сессию с прокси если он указан"""
    proxy_url = os.getenv("PROXY_URL", "").strip()
    
    if not proxy_url:
        logging.warning("⚠️ Прокси не настроен! Если бот не работает - добавьте PROXY_URL в .env")
        return AiohttpSession()
    
    logging.info(f"🔄 Настраивается прокси: {proxy_url}")
    
    try:
        from aiohttp_socks import ProxyConnector
        
        # Парсим URL прокси: socks5://user:pass@ip:port или socks5://ip:port
        match = re.match(
            r'socks5://(?:(?P<user>[^:]+):(?P<pass>[^@]+)@)?(?P<host>[^:]+):(?P<port>\d+)',
            proxy_url
        )
        
        if not match:
            logging.error(f"❌ Неверный формат прокси: {proxy_url}")
            return AiohttpSession()
        
        connector = ProxyConnector(
            host=match.group('host'),
            port=int(match.group('port')),
            username=match.group('user') or None,
            password=match.group('pass') or None,
            rdns=True  # ВАЖНО: DNS резолвится через прокси (обходит блокировки!)
        )
        
        logging.info(f"✅ Прокси настроен: {match.group('host')}:{match.group('port')}")
        return AiohttpSession(connector=connector)
        
    except ImportError:
        logging.error("❌ Модуль aiohttp-socks не установлен!")
        logging.error("❌ Добавьте в requirements.txt: aiohttp-socks>=0.8.0")
        return AiohttpSession()
    except Exception as e:
        logging.error(f"❌ Ошибка настройки прокси: {e}")
        return AiohttpSession()

# Инициализация
bot = Bot(token=BOT_TOKEN, session=get_session())
dp = Dispatcher()
db = Database()

# Машина состояний для теста
class QuizState(StatesGroup):
    answering_question = State()

# Машина состояний для админки
class AdminState(StatesGroup):
    waiting_for_password = State()
    waiting_for_broadcast_text = State()
    waiting_for_broadcast_photo = State()

# Хранилище текущего вопроса для каждого пользователя
user_current_question = {}
user_scores = {}


# ========== ОБРАБОТЧИКИ ПОЛЬЗОВАТЕЛЕЙ ==========

@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    """Обработчик команды /start"""
    await db.add_user(
        user_id=message.from_user.id,
        username=message.from_user.username or "",
        first_name=message.from_user.first_name or "",
        last_name=message.from_user.last_name or ""
    )
    
    await state.clear()
    
    await message.answer(
        "Привет!\n\n"
        "В этом тесте тебе нужно будет ответить на 3 вопроса. "
        "За каждый правильный ответ будет начислен 1 балл.\n\n"
        "Готов начать путь к голде? 🏆",
        reply_markup=get_start_keyboard()
    )


@dp.message(F.text == "Начать тест")
async def start_quiz(message: types.Message, state: FSMContext):
    """Начало теста"""
    await state.set_state(QuizState.answering_question)
    user_current_question[message.from_user.id] = 0
    user_scores[message.from_user.id] = 0
    
    await show_question(message.from_user.id, message.chat.id, 0)


async def show_question(user_id: int, chat_id: int, question_index: int):
    """Показ вопроса"""
    if question_index >= len(QUIZ_QUESTIONS):
        await finish_quiz(user_id, chat_id)
        return
    
    question = QUIZ_QUESTIONS[question_index]
    map_data = MAPS_DATA[question['map_key']]
    
    try:
        photo = FSInputFile(question['photo_path'])
        await bot.send_photo(
            chat_id=chat_id,
            photo=photo,
            caption=f"🤔 {question_index + 1}. Как называется эта карта?"
        )
    except FileNotFoundError:
        await bot.send_message(
            chat_id=chat_id,
            text=f"🤔 {question_index + 1}. Как называется эта карта?\n"
                 "(Фото временно недоступно)"
        )
    except Exception as e:
        logging.error(f"Ошибка при отправке фото: {e}")
        await bot.send_message(
            chat_id=chat_id,
            text=f"🤔 {question_index + 1}. Как называется эта карта?"
        )
    
    await bot.send_message(
        chat_id=chat_id,
        text="Выберите правильный ответ:",
        reply_markup=get_quiz_keyboard(
            map_data['name'],
            map_data['wrong_answer']
        )
    )


async def finish_quiz(user_id: int, chat_id: int):
    """Завершение теста"""
    score = user_scores.get(user_id, 0)
    
    await db.save_quiz_result(user_id, score)
    
    await bot.send_message(
        chat_id=chat_id,
        text="Поздравляю!\n\n"
             f"Ваши баллы за тест: {score}\n\n"
             "Ты заслужил кое-что интересное, нажимай на кнопку \"ПРИЗ\" 👇",
        reply_markup=get_prize_keyboard()
    )
    
    if user_id in user_current_question:
        del user_current_question[user_id]
    if user_id in user_scores:
        del user_scores[user_id]


@dp.callback_query(F.data == "prize")
async def handle_prize(callback: types.CallbackQuery):
    """Обработка кнопки ПРИЗ"""
    user_id = callback.from_user.id
    await db.mark_prize_clicked(user_id)
    
    try:
        photo = FSInputFile(r"data\photos\golf.jpg")
        await callback.message.answer_photo(
            photo=photo,
            caption="🎁 **2500 ГОЛДЫ ЗА 11 РУБЛЕЙ**\n\n"
                    "Забирай свою голду 🎁\n\n"
                    "Ты получаешь 2500 голды всего за 11 рублей от нашего партнера!\n\n"
                    "🔗 Забирай их [здесь](https://clicktosite.ru/fRxvPK)\n\n"
                    "⏰ Время действия предложения всего 6 часов с момента получения этого сообщения ⏰",
            parse_mode="Markdown"
        )
    except FileNotFoundError:
        await callback.message.answer(
            "🎁 **2500 ГОЛДЫ ЗА 11 РУБЛЕЙ**\n\n"
            "Забирай свою голду 🎁\n\n"
            "Ты получаешь 2500 голды всего за 11 рублей от нашего партнера!\n\n"
            "🔗 Забирай их [здесь](https://clicktosite.ru/fRxvPK)\n\n"
            "⏰ Время действия предложения всего 6 часов с момента получения этого сообщения ⏰",
            parse_mode="Markdown"
        )
    
    await callback.answer()


@dp.callback_query(F.data.startswith("answer_"))
async def handle_answer(callback: types.CallbackQuery, state: FSMContext):
    """Обработка ответа на вопрос"""
    answer = callback.data.replace("answer_", "")
    user_id = callback.from_user.id
    chat_id = callback.message.chat.id
    current_question = user_current_question.get(user_id, 0)
    
    if current_question >= len(QUIZ_QUESTIONS):
        await callback.answer()
        return
    
    question = QUIZ_QUESTIONS[current_question]
    map_data = MAPS_DATA[question['map_key']]
    correct_answer = map_data['name']
    
    try:
        if answer == correct_answer:
            user_scores[user_id] = user_scores.get(user_id, 0) + 1
            await callback.message.answer("Правильно! 🔥")
        else:
            await callback.message.answer("К сожалению, это неправильный ответ.")
            await callback.message.answer(
                f"Название карты - {correct_answer} ✅\n\n"
                f"{map_data['description']}"
            )
        
        user_current_question[user_id] = current_question + 1
        await callback.answer()
        await asyncio.sleep(1)
        await show_question(user_id, chat_id, current_question + 1)
        
    except Exception as e:
        logging.error(f"Ошибка при обработке ответа: {e}")
        await callback.answer()


# ========== АДМИН ПАНЕЛЬ ==========

@dp.message(Command("admin"))
async def cmd_admin(message: types.Message, state: FSMContext):
    """Вход в админ панель"""
    await state.set_state(AdminState.waiting_for_password)
    await message.answer("🔐 Введите пароль администратора:")


@dp.message(AdminState.waiting_for_password)
async def check_admin_password(message: types.Message, state: FSMContext):
    """Проверка пароля администратора"""
    if message.text == ADMIN_PASSWORD:
        await state.clear()
        await message.answer(
            "✅ Доступ разрешен!\n\n"
            "Выберите действие:",
            reply_markup=get_admin_keyboard()
        )
    else:
        await message.answer("❌ Неверный пароль!")
        await state.clear()


@dp.callback_query(F.data == "admin_stats")
async def admin_stats(callback: types.CallbackQuery):
    """Показ статистики"""
    total_users, total_tests, prize_clicks = await db.get_stats()
    
    await callback.message.answer(
        f"📊 **Статистика бота**\n\n"
        f"👥 Всего пользователей (нажали /start): {total_users}\n"
        f"📝 Пройдено тестов: {total_tests}\n"
        f"💰 Нажато на кнопку ПРИЗ: {prize_clicks}\n"
        f"📈 Конверсия в ПРИЗ: {(prize_clicks/total_tests*100) if total_tests > 0 else 0:.1f}%",
        parse_mode="Markdown"
    )
    await callback.answer()


@dp.callback_query(F.data == "admin_users")
async def admin_users(callback: types.CallbackQuery):
    """Показ всех пользователей (уникальных)"""
    results = await db.get_all_results()
    
    if not results:
        await callback.message.answer("📭 Пока нет пользователей")
        await callback.answer()
        return
    
    unique_users = {}
    for user_id, username, first_name, last_name, score, completed_at, clicked_prize in results:
        unique_users[user_id] = (user_id, username, first_name, last_name, score, completed_at, clicked_prize)
    
    message_text = "👥 **Пользователи, прошедшие тест:**\n\n"
    
    for i, (user_id, username, first_name, last_name, score, completed_at, clicked_prize) in enumerate(list(unique_users.values())[:20], 1):
        full_name = f"{first_name} {last_name or ''}".strip()
        username_str = f"@{username}" if username else f"ID: {user_id}"
        prize_status = "✅" if clicked_prize else "❌"
        
        message_text += (
            f"{i}. {full_name} ({username_str})\n"
            f"   Баллы: {score}\n"
            f"   Завершен: {completed_at}\n"
            f"   Нажал ПРИЗ: {prize_status}\n\n"
        )
    
    if len(unique_users) > 20:
        message_text += f"... и еще {len(unique_users) - 20} пользователей"
    
    await callback.message.answer(message_text, parse_mode="Markdown")
    await callback.answer()


@dp.callback_query(F.data == "admin_broadcast")
async def start_broadcast(callback: types.CallbackQuery, state: FSMContext):
    """Начало рассылки"""
    await state.set_state(AdminState.waiting_for_broadcast_text)
    await callback.message.answer(
        "📢 **Рассылка сообщений**\n\n"
        "Отправьте текст сообщения, которое будет разослано всем пользователям.\n\n"
        "Чтобы добавить фото, отправьте фото с подписью (или без).\n"
        "Чтобы отправить только текст - просто отправьте текст.\n\n"
        "Для отмены отправьте: /cancel или нажмите ❌ Отменить",
        reply_markup=get_cancel_keyboard(),
        parse_mode="Markdown"
    )
    await callback.answer()


@dp.message(Command("cancel"), AdminState.waiting_for_broadcast_text, AdminState.waiting_for_broadcast_photo)
@dp.message(F.text == "❌ Отменить", AdminState.waiting_for_broadcast_text, AdminState.waiting_for_broadcast_photo)
async def cancel_broadcast(message: types.Message, state: FSMContext):
    """Отмена рассылки"""
    await state.clear()
    await message.answer("❌ Рассылка отменена.", reply_markup=types.ReplyKeyboardRemove())


@dp.message(AdminState.waiting_for_broadcast_text, F.text)
async def process_broadcast_text(message: types.Message, state: FSMContext):
    """Обработка текста рассылки"""
    text = message.text
    if not text:
        await message.answer("⚠️ Сообщение не может быть пустым!")
        return
    
    await state.update_data(broadcast_text=text)
    await state.set_state(AdminState.waiting_for_broadcast_photo)
    
    await message.answer(
        "📷 Теперь отправьте фото (или отправьте /cancel чтобы пропустить фото):",
        reply_markup=types.ReplyKeyboardRemove()
    )


@dp.message(AdminState.waiting_for_broadcast_text, F.photo)
async def process_broadcast_photo_only(message: types.Message, state: FSMContext):
    """Если сразу отправили фото без текста"""
    await message.answer("⚠️ Сначала отправьте текст сообщения!")


@dp.message(AdminState.waiting_for_broadcast_photo, F.photo)
async def process_broadcast_photo(message: types.Message, state: FSMContext):
    """Обработка фото и отправка рассылки"""
    state_data = await state.get_data()
    text = state_data.get("broadcast_text", "")
    caption = message.caption or ""
    full_text = f"{text}\n\n{caption}".strip() if caption else text
    photo_file_id = message.photo[-1].file_id
    
    await send_broadcast(message, full_text, photo_file_id, state)


@dp.message(AdminState.waiting_for_broadcast_photo, F.text)
async def process_broadcast_no_photo(message: types.Message, state: FSMContext):
    """Отправка рассылки без фото"""
    state_data = await state.get_data()
    text = state_data.get("broadcast_text", "")
    await send_broadcast(message, text, None, state)


async def send_broadcast(message: types.Message, text: str, photo_file_id: str | None, state: FSMContext):
    """Функция отправки рассылки"""
    users = await db.get_all_users_for_broadcast()
    
    if not users:
        await message.answer("📭 Нет пользователей для рассылки!")
        await state.clear()
        return
    
    await message.answer(f"🚀 Начинаю рассылку для {len(users)} пользователей...")
    
    success_count = 0
    error_count = 0
    
    for user_id, username in users:
        try:
            if photo_file_id:
                await bot.send_photo(chat_id=user_id, photo=photo_file_id, caption=text)
            else:
                await bot.send_message(chat_id=user_id, text=text)
            success_count += 1
            await asyncio.sleep(0.05)
        except Exception as e:
            error_count += 1
            logging.warning(f"Не удалось отправить сообщение пользователю {user_id}: {e}")
    
    await state.clear()
    await message.answer(
        f"✅ Рассылка завершена!\n\n"
        f"📤 Успешно отправлено: {success_count}\n"
        f"❌ Ошибок: {error_count}\n"
        f"👥 Всего пользователей: {len(users)}",
        reply_markup=get_cancel_keyboard()
    )


# ========== ЗАПУСК БОТА ==========

async def main():
    await db.init_db()
    
    # Проверка подключения
    try:
        me = await bot.get_me()
        logging.info(f"✅ Бот запущен: @{me.username}")
    except Exception as e:
        logging.error(f"❌ Не удалось подключиться к Telegram: {e}")
        logging.error("💡 Проверьте токен и PROXY_URL в .env")
        return
    
    logging.info("Запуск бота...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())