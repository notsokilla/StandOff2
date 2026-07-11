import asyncio
import logging
import os
import random
from pathlib import Path
from datetime import datetime
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.utils.keyboard import InlineKeyboardBuilder
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
import pytz
from config import BOT_TOKEN, ADMIN_PASSWORD
from database import Database
from keyboards import (
    get_cancel_keyboard, get_quiz_keyboard, get_prize_keyboard, 
    get_start_keyboard, get_admin_main_keyboard, get_users_pagination_keyboard
)
from data.maps_data import QUIZ_QUESTIONS, MAPS_DATA

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_session():
    proxy_url = os.getenv("PROXY_URL", "").strip()
    if not proxy_url:
        logging.warning("⚠️ Прокси не настроен!")
        return AiohttpSession()
    logging.info(f"🔄 Настраивается прокси: {proxy_url}")
    try:
        return AiohttpSession(proxy=proxy_url)
    except Exception as e:
        logging.error(f"❌ Ошибка настройки прокси: {e}")
        return AiohttpSession()

bot = Bot(token=BOT_TOKEN, session=get_session())
dp = Dispatcher()
db = Database()
scheduler = AsyncIOScheduler(timezone=pytz.UTC)

class QuizState(StatesGroup):
    answering_question = State()

class AdminState(StatesGroup):
    waiting_for_password = State()

user_current_question = {}
user_scores = {}

BROADCAST_MESSAGES = [
    {"id": 1, "text": "Alexander, ты ПОБЕДИТЕЛЬ на голду!\n\nМы выбрали всего 3 человека, которым дадим 2500 голды за 11 рублей!\n\nПереходи [сюда](https://clicktosite.ru/fRxvPK)!"},
    {"id": 2, "text": "⚠️ Alexander, тебя выбрал бот для выдачи голды!\n\nТебе нереально повезло, ведь ты получаешь 2500 голды за 11 рублей! 💰\n\n🔗 [Ссылка](https://clicktosite.ru/fRxvPK)"},
    {"id": 3, "text": "Alexander, поздравляем! Ваш аккаунт вошёл в пятёрку победителей!\n\nВы вошли в пятёрку людей, которые получают 2500 голды\n\nРандом список составлен:\n1) Alexander\n2) Григорий\n3) Андрей К.\n4) Alwayswannafly\n5) Миша\n\n\n\nПереходи по [ссылке](https://clicktosite.ru/fRxvPK) и забирай голду всего за 11 рублей!"},
    {"id": 4, "text": "Ты получаешь 2500 голды, поздравляю! 🔥\n\n⚡ Ты был выбран нашим ботом\n🎁 Ты получаешь 2500 голды всего за 11 рублей!\n\n🔗 [Здесь](https://clicktosite.ru/fRxvPK)\n\nСписок счастливчиков состоит всего из трех людей:\n1) Alexander\n2) Виктор\n3) Игорь"},
    {"id": 5, "text": "Ты получаешь голду прямо сейчас 💰\n\nМы отдаем тебе 2500 голды за 11 рублей 🎁 Переходи по [ссылке](https://clicktosite.ru/fRxvPK), регистрируйся и забирай голду!\n\n🔥 Поспеши - такая халява бывает очень редко!"}
]

RANDOM_NAMES = [
    "Виктор", "Григорий", "Андрей К.", "Alwayswannafly", 
    "Миша", "Игорь", "Дмитрий", "Алексей", "Максим", "Артем", "Иван",
    "Николай", "Владимир", "Сергей", "Павел", "Роман", "Егор", "Тимофей", 
    "Денис", "Вячеслав", "Константин", "Анатолий", "Юрий", "Владислав"
]

def personalize_message(text: str, username: str) -> str:
    """Персонализация сообщения с подстановкой имени пользователя"""
    # Заменяем ПЕРВОЕ вхождение "Alexander" на username
    text = text.replace("Alexander", username, 1)
    
    # Заменяем ОСТАЛЬНЫЕ вхождения на случайные имена
    random_names = [n for n in RANDOM_NAMES if n != "Alexander"]
    
    for name in random_names:
        if "Alexander" in text:
            text = text.replace("Alexander", name, 1)
        else:
            break
    return text

def get_broadcast_menu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for msg in BROADCAST_MESSAGES:
        builder.button(text=f"📨 Рассылка #{msg['id']}", callback_data=f"broadcast_{msg['id']}")
    builder.button(text="⬅️ Назад", callback_data="admin_main")
    builder.adjust(1)
    return builder.as_markup()

def get_broadcast_confirm_keyboard(broadcast_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Отправить всем", callback_data=f"broadcast_confirm_{broadcast_id}")
    builder.button(text="❌ Отмена", callback_data="admin_broadcast")
    builder.adjust(2)
    return builder.as_markup()

async def send_auto_broadcast(broadcast_id: int = None):
    if broadcast_id and 1 <= broadcast_id <= len(BROADCAST_MESSAGES):
        broadcast = BROADCAST_MESSAGES[broadcast_id - 1]
    elif os.getenv("AUTO_BROADCAST_TYPE", "random").lower() == "random":
        broadcast = random.choice(BROADCAST_MESSAGES)
    else:
        broadcast = BROADCAST_MESSAGES[0]
    
    users = await db.get_all_users_for_broadcast()
    if not users:
        logging.warning("⚠️ Нет пользователей для авто-рассылки")
        return
    
    logging.info(f"🚀 Авто-рассылка #{broadcast['id']} для {len(users)} пользователей")
    success_count, error_count = 0, 0
    
    for user_id, username in users:
        try:
            user_display_name = username if username else f"Пользователь #{user_id}"
            personalized_text = personalize_message(broadcast["text"], user_display_name)
            await bot.send_message(chat_id=user_id, text=personalized_text, parse_mode="Markdown")
            success_count += 1
            await asyncio.sleep(0.05)
        except Exception as e:
            error_count += 1
            logging.warning(f"Не удалось отправить пользователю {user_id}: {e}")
    
    admin_id = os.getenv("ADMIN_USER_ID")
    if admin_id:
        try:
            await bot.send_message(
                chat_id=int(admin_id),
                text=f"✅ **Авто-рассылка завершена**\n\n📨 Рассылка #{broadcast['id']}\n📤 Успешно: {success_count}\n❌ Ошибок: {error_count}\n👥 Всего: {len(users)}\n🕐 {datetime.now().strftime('%H:%M %d.%m.%Y')}",
                parse_mode="Markdown"
            )
        except:
            pass
    logging.info(f"✅ Авто-рассылка: {success_count} успешно, {error_count} ошибок")

def setup_auto_broadcast():
    if os.getenv("AUTO_BROADCAST_ENABLED", "false").lower() != "true":
        logging.info("⏭️ Авто-рассылка отключена")
        return
    try:
        test_interval = os.getenv("AUTO_BROADCAST_TEST_SECONDS")
        if test_interval:
            interval_seconds = int(test_interval)
            scheduler.add_job(send_auto_broadcast, trigger=IntervalTrigger(seconds=interval_seconds), id="auto_broadcast", name="Авто-рассылка (тест)", replace_existing=True, max_instances=1)
            logging.info(f"⏰ Тест авто-рассылки: каждые {interval_seconds} сек.")
        else:
            interval_hours = float(os.getenv("AUTO_BROADCAST_INTERVAL_HOURS", "4"))
            if interval_hours < 0.003:
                interval_hours = 0.003
            scheduler.add_job(send_auto_broadcast, trigger=IntervalTrigger(hours=interval_hours), id="auto_broadcast", name="Авто-рассылка", replace_existing=True, max_instances=1)
            logging.info(f"⏰ Авто-рассылка: каждые {interval_hours} ч.")
    except Exception as e:
        logging.error(f"❌ Ошибка: {e}")

@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await db.add_user(user_id=message.from_user.id, username=message.from_user.username or "", first_name=message.from_user.first_name or "", last_name=message.from_user.last_name or "")
    await state.clear()
    await message.answer("Привет!\n\nВ этом тесте тебе нужно будет ответить на 3 вопроса. За каждый правильный ответ будет начислен 1 балл.\n\nГотов начать путь к голде? 🏆", reply_markup=get_start_keyboard())

@dp.message(F.text == "Начать тест")
async def start_quiz(message: types.Message, state: FSMContext):
    await state.set_state(QuizState.answering_question)
    user_current_question[message.from_user.id] = 0
    user_scores[message.from_user.id] = 0
    await show_question(message.from_user.id, message.chat.id, 0)

async def show_question(user_id: int, chat_id: int, question_index: int):
    if question_index >= len(QUIZ_QUESTIONS):
        await finish_quiz(user_id, chat_id)
        return
    question = QUIZ_QUESTIONS[question_index]
    map_data = MAPS_DATA[question['map_key']]
    try:
        photo = FSInputFile(question['photo_path'])
        await bot.send_photo(chat_id=chat_id, photo=photo, caption=f"🤔 {question_index + 1}. Как называется эта карта?")
    except FileNotFoundError:
        await bot.send_message(chat_id=chat_id, text=f"🤔 {question_index + 1}. Как называется эта карта?\n(Фото временно недоступно)")
    except Exception as e:
        logging.error(f"Ошибка при отправке фото: {e}")
        await bot.send_message(chat_id=chat_id, text=f"🤔 {question_index + 1}. Как называется эта карта?")
    await bot.send_message(chat_id=chat_id, text="Выберите правильный ответ:", reply_markup=get_quiz_keyboard(map_data['name'], map_data['wrong_answer']))

async def finish_quiz(user_id: int, chat_id: int):
    score = user_scores.get(user_id, 0)
    await db.save_quiz_result(user_id, score)
    await bot.send_message(chat_id=chat_id, text=f"Поздравляю!\n\nВаши баллы за тест: {score}\n\nТы заслужил кое-что интересное, нажимай на кнопку \"ПРИЗ\" 👇", reply_markup=get_prize_keyboard())
    if user_id in user_current_question:
        del user_current_question[user_id]
    if user_id in user_scores:
        del user_scores[user_id]

@dp.callback_query(F.data == "prize")
async def handle_prize(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    await db.mark_prize_clicked(user_id)
    try:
        photo_path = Path("data/photos/golf.jpg")
        if not photo_path.exists():
            raise FileNotFoundError(f"Фото не найдено: {photo_path}")
        photo = FSInputFile(str(photo_path))
        await callback.message.answer_photo(photo=photo, caption="🎁 **2500 ГОЛДЫ ЗА 11 РУБЛЕЙ**\n\nЗабирай свою голду 🎁\n\nТы получаешь 2500 голды всего за 11 рублей от нашего партнера!\n\n🔗 Забирай их [здесь](https://clicktosite.ru/fRxvPK)\n\n⏰ Время действия предложения всего 6 часов с момента получения этого сообщения ⏰", parse_mode="Markdown")
    except FileNotFoundError as e:
        logging.warning(f"⚠️ Фото не найдено: {e}")
        await callback.message.answer("🎁 **2500 ГОЛДЫ ЗА 11 РУБЛЕЙ**\n\nЗабирай свою голду 🎁\n\nТы получаешь 2500 голды всего за 11 рублей от нашего партнера!\n\n🔗 Забирай их [здесь](https://clicktosite.ru/fRxvPK)\n\n⏰ Время действия предложения всего 6 часов с момента получения этого сообщения ⏰", parse_mode="Markdown")
    except Exception as e:
        logging.error(f"❌ Ошибка при отправке ПРИЗа: {e}")
        await callback.message.answer("🎁 **2500 ГОЛДЫ ЗА 11 РУБЛЕЙ**\n\n🔗 Забирай их [здесь](https://clicktosite.ru/fRxvPK)", parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(F.data.startswith("answer_"))
async def handle_answer(callback: types.CallbackQuery, state: FSMContext):
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
            await callback.message.answer(f"Название карты - {correct_answer} ✅\n\n{map_data['description']}")
        user_current_question[user_id] = current_question + 1
        await callback.answer()
        await asyncio.sleep(1)
        await show_question(user_id, chat_id, current_question + 1)
    except Exception as e:
        logging.error(f"Ошибка при обработке ответа: {e}")
        await callback.answer()

@dp.message(Command("admin"))
async def cmd_admin(message: types.Message, state: FSMContext):
    await state.set_state(AdminState.waiting_for_password)
    await message.answer("🔐 Введите пароль администратора:")

@dp.message(AdminState.waiting_for_password)
async def check_admin_password(message: types.Message, state: FSMContext):
    if message.text == ADMIN_PASSWORD:
        await state.clear()
        await message.answer("✅ Доступ разрешен!\n\nВыберите действие:", reply_markup=get_admin_main_keyboard())
    else:
        await message.answer("❌ Неверный пароль!")
        await state.clear()

@dp.callback_query(F.data == "admin_main")
async def admin_main_menu(callback: types.CallbackQuery):
    await callback.message.edit_text("✅ Доступ разрешен!\n\nВыберите действие:", reply_markup=get_admin_main_keyboard())
    await callback.answer()

@dp.callback_query(F.data == "admin_stats")
async def admin_stats(callback: types.CallbackQuery):
    total_users, total_tests, prize_clicks = await db.get_stats()
    await callback.message.answer(f"📊 **Статистика бота**\n\n👥 Всего пользователей (нажали /start): {total_users}\n📝 Пройдено тестов: {total_tests}\n💰 Нажато на кнопку ПРИЗ: {prize_clicks}\n📈 Конверсия в ПРИЗ: {(prize_clicks/total_tests*100) if total_tests > 0 else 0:.1f}%", parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(F.data.startswith("admin_users_page_"))
async def admin_users_paginated(callback: types.CallbackQuery):
    page = int(callback.data.split("_")[-1])
    per_page = 10
    results = await db.get_all_results()
    if not results:
        await callback.message.answer("📭 Пока нет пользователей")
        await callback.answer()
        return
    unique_users = {}
    for user_id, username, first_name, last_name, score, completed_at, clicked_prize in results:
        unique_users[user_id] = (user_id, username, first_name, last_name, score, completed_at, clicked_prize)
    users_list = list(unique_users.values())
    total_users = len(users_list)
    total_pages = (total_users + per_page - 1) // per_page
    if page < 1: page = 1
    if page > total_pages: page = total_pages
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    page_users = users_list[start_idx:end_idx]
    message_text = f"👥 **Пользователи (стр. {page}/{total_pages})**\n\n"
    for i, (user_id, username, first_name, last_name, score, completed_at, clicked_prize) in enumerate(page_users, start_idx + 1):
        full_name = f"{first_name} {last_name or ''}".strip()
        username_str = f"@{username}" if username else f"ID: {user_id}"
        prize_status = "✅" if clicked_prize else "❌"
        message_text += f"{i}. {full_name} ({username_str})\n   Баллы: {score} | ПРИЗ: {prize_status}\n\n"
    if len(unique_users) > 20:
        message_text += f"... и еще {len(unique_users) - 20} пользователей"
    await callback.message.answer(message_text, parse_mode="Markdown", reply_markup=get_users_pagination_keyboard(page, total_pages))
    await callback.answer()

@dp.callback_query(F.data == "admin_broadcast")
async def admin_broadcast_menu(callback: types.CallbackQuery):
    await callback.message.answer("📨 **Готовые рассылки**\n\nВыберите рассылку для отправки:", reply_markup=get_broadcast_menu_keyboard(), parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(F.data.startswith("broadcast_confirm_"))
async def broadcast_execute(callback: types.CallbackQuery):
    try:
        broadcast_id = int(callback.data.split("_")[-1])
    except (ValueError, IndexError):
        await callback.message.answer("❌ Ошибка: неверный ID рассылки")
        await callback.answer()
        return
    broadcast = next((msg for msg in BROADCAST_MESSAGES if msg["id"] == broadcast_id), None)
    if not broadcast:
        await callback.message.answer("❌ Рассылка не найдена!")
        await callback.answer()
        return
    users = await db.get_all_users_for_broadcast()
    if not users:
        await callback.message.answer("📭 Нет пользователей для рассылки!")
        await callback.answer()
        return
    await callback.message.answer(f"🚀 Начинаю рассылку #{broadcast_id} для {len(users)} пользователей...")
    success_count, error_count = 0, 0
    for user_id, username in users:
        try:
            user_display_name = username if username else f"Пользователь #{user_id}"
            personalized_text = personalize_message(broadcast["text"], user_display_name)
            await bot.send_message(chat_id=user_id, text=personalized_text, parse_mode="Markdown")
            success_count += 1
            await asyncio.sleep(0.05)
        except Exception as e:
            error_count += 1
            logging.warning(f"Не удалось отправить пользователю {user_id}: {e}")
    await callback.message.answer(f"✅ Рассылка #{broadcast_id} завершена!\n\n📤 Успешно: {success_count}\n❌ Ошибок: {error_count}\n👥 Всего: {len(users)}", reply_markup=get_admin_main_keyboard())
    await callback.answer()

@dp.callback_query(F.data.startswith("broadcast_"))
async def broadcast_preview(callback: types.CallbackQuery):
    try:
        broadcast_id = int(callback.data.split("_")[-1])
    except (ValueError, IndexError):
        await callback.message.answer("❌ Ошибка: неверный ID рассылки")
        await callback.answer()
        return
    broadcast = next((msg for msg in BROADCAST_MESSAGES if msg["id"] == broadcast_id), None)
    if not broadcast:
        await callback.message.answer("❌ Рассылка не найдена!")
        await callback.answer()
        return
    users = await db.get_all_users_for_broadcast()
    await callback.message.answer(f"📨 **Рассылка #{broadcast_id}**\n\n📝 Текст:\n{broadcast['text'][:300]}{'...' if len(broadcast['text']) > 300 else ''}\n\n👥 Получателей: {len(users)}\n\nСообщение будет персонализировано для каждого пользователя.", reply_markup=get_broadcast_confirm_keyboard(broadcast_id), parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(F.data == "admin_broadcast_test")
async def admin_broadcast_test(callback: types.CallbackQuery):
    admin_id = callback.from_user.id
    broadcast = random.choice(BROADCAST_MESSAGES)
    personalized_text = personalize_message(broadcast["text"], callback.from_user.username or f"Пользователь #{admin_id}")
    await callback.message.answer(f"🧪 **Тест рассылки #{broadcast['id']}**\n\n{personalized_text}", parse_mode="Markdown")
    await callback.answer()

async def main():
    await db.init_db()
    setup_auto_broadcast()
    scheduler.start()
    try:
        me = await bot.get_me()
        logging.info(f"✅ Бот запущен: @{me.username}")
    except Exception as e:
        logging.error(f"❌ Не удалось подключиться к Telegram: {e}")
        logging.error("💡 Проверьте токен и PROXY_URL в .env")
        return
    logging.info("🚀 Запуск polling...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())