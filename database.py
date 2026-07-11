import aiosqlite
from typing import List, Tuple, Optional

class Database:
    def __init__(self):
        self.db_path = 'bot_database.db'
    
    async def init_db(self):
        """Инициализация базы данных"""
        async with aiosqlite.connect(self.db_path) as conn:
            cursor = await conn.cursor()
            
            # Таблица пользователей
            await cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Таблица результатов теста
            await cursor.execute('''
                CREATE TABLE IF NOT EXISTS quiz_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    score INTEGER,
                    completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    clicked_prize INTEGER DEFAULT 0,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            ''')
            
            # Таблица шаблонов рассылок
            await cursor.execute('''
                CREATE TABLE IF NOT EXISTS broadcast_templates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    text TEXT NOT NULL,
                    photo_file_id TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            await conn.commit()
    
    async def add_user(self, user_id: int, username: str, first_name: str, last_name: str = None):
        """Добавление/обновление пользователя"""
        async with aiosqlite.connect(self.db_path) as conn:
            cursor = await conn.cursor()
            await cursor.execute('''
                INSERT OR REPLACE INTO users (user_id, username, first_name, last_name)
                VALUES (?, ?, ?, ?)
            ''', (user_id, username, first_name, last_name))
            await conn.commit()
    
    async def save_quiz_result(self, user_id: int, score: int):
        """Сохранение результата теста"""
        async with aiosqlite.connect(self.db_path) as conn:
            cursor = await conn.cursor()
            await cursor.execute('''
                INSERT INTO quiz_results (user_id, score)
                VALUES (?, ?)
            ''', (user_id, score))
            await conn.commit()
    
    async def mark_prize_clicked(self, user_id: int):
        """Отметка, что пользователь нажал на кнопку ПРИЗ"""
        async with aiosqlite.connect(self.db_path) as conn:
            cursor = await conn.cursor()
            await cursor.execute('''
                UPDATE quiz_results 
                SET clicked_prize = 1 
                WHERE user_id = ? AND id = (
                    SELECT MAX(id) FROM quiz_results WHERE user_id = ?
                )
            ''', (user_id, user_id))
            await conn.commit()
    
    async def get_all_results(self) -> List[Tuple]:
        """Получение всех результатов"""
        async with aiosqlite.connect(self.db_path) as conn:
            cursor = await conn.cursor()
            await cursor.execute('''
                SELECT u.user_id, u.username, u.first_name, u.last_name,
                       qr.score, qr.completed_at, qr.clicked_prize
                FROM quiz_results qr
                JOIN users u ON qr.user_id = u.user_id
                ORDER BY qr.completed_at DESC
            ''')
            return await cursor.fetchall()
    
    async def get_stats(self) -> Tuple[int, int, int]:
        """Получение статистики"""
        async with aiosqlite.connect(self.db_path) as conn:
            cursor = await conn.cursor()
            
            await cursor.execute('SELECT COUNT(*) FROM users')
            total_users = (await cursor.fetchone())[0]
            
            await cursor.execute('SELECT COUNT(*) FROM quiz_results')
            total_tests = (await cursor.fetchone())[0]
            
            await cursor.execute('SELECT COUNT(*) FROM quiz_results WHERE clicked_prize = 1')
            prize_clicks = (await cursor.fetchone())[0]
            
            return total_users, total_tests, prize_clicks
    
    async def get_all_users_for_broadcast(self) -> List[Tuple[int, str]]:
        """Получение всех пользователей для рассылки"""
        async with aiosqlite.connect(self.db_path) as conn:
            cursor = await conn.cursor()
            await cursor.execute('SELECT user_id, username FROM users')
            return await cursor.fetchall()
    
    # ========== МЕТОДЫ ДЛЯ ШАБЛОНОВ ==========
    
    async def create_template(self, name: str, text: str, photo_file_id: str = None) -> int:
        """Создание шаблона. Возвращает ID созданного шаблона"""
        async with aiosqlite.connect(self.db_path) as conn:
            cursor = await conn.cursor()
            await cursor.execute('''
                INSERT INTO broadcast_templates (name, text, photo_file_id)
                VALUES (?, ?, ?)
            ''', (name, text, photo_file_id))
            await conn.commit()
            return cursor.lastrowid
    
    async def get_templates(self) -> List[Tuple]:
        """Получение всех шаблонов"""
        async with aiosqlite.connect(self.db_path) as conn:
            cursor = await conn.cursor()
            await cursor.execute('''
                SELECT id, name, text, photo_file_id, created_at
                FROM broadcast_templates
                ORDER BY created_at DESC
            ''')
            return await cursor.fetchall()
    
    async def delete_template(self, template_id: int):
        """Удаление шаблона"""
        async with aiosqlite.connect(self.db_path) as conn:
            cursor = await conn.cursor()
            await cursor.execute('''
                DELETE FROM broadcast_templates WHERE id = ?
            ''', (template_id,))
            await conn.commit()
    
    async def get_template_by_id(self, template_id: int) -> Optional[Tuple]:
        """Получение шаблона по ID"""
        async with aiosqlite.connect(self.db_path) as conn:
            cursor = await conn.cursor()
            await cursor.execute('''
                SELECT id, name, text, photo_file_id, created_at
                FROM broadcast_templates
                WHERE id = ?
            ''', (template_id,))
            return await cursor.fetchone()