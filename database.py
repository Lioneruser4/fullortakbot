import sqlite3
import asyncio
from datetime import datetime, timedelta
import aiosqlite
from config import DB_NAME

class Database:
    def __init__(self):
        self.db_name = DB_NAME
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            # Kullanıcılar tablosu
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                is_premium BOOLEAN DEFAULT 0,
                daily_downloads INTEGER DEFAULT 0,
                last_download_date TEXT
            )
            ''')
            
            # İndirme geçmişi tablosu
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS download_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                file_name TEXT,
                download_date TEXT,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
            ''')
            conn.commit()

    async def _get_connection(self):
        return await aiosqlite.connect(self.db_name)

    async def add_user(self, user_id, is_premium=False):
        async with await self._get_connection() as db:
            await db.execute(
                'INSERT OR IGNORE INTO users (user_id, is_premium) VALUES (?, ?)',
                (user_id, is_premium)
            )
            await db.commit()

    async def is_premium(self, user_id):
        async with await self._get_connection() as db:
            cursor = await db.execute(
                'SELECT is_premium FROM users WHERE user_id = ?',
                (user_id,)
            )
            result = await cursor.fetchone()
            return result[0] if result else False

    async def can_download(self, user_id):
        async with await self._get_connection() as db:
            # Kullanıcıyı ekle (eğer yoksa)
            await self.add_user(user_id)
            
            # Son indirme tarihini kontrol et
            cursor = await db.execute(
                'SELECT last_download_date, daily_downloads FROM users WHERE user_id = ?',
                (user_id,)
            )
            result = await cursor.fetchone()
            
            if not result:
                return False
                
            last_download_date, daily_downloads = result
            today = datetime.now().strftime('%Y-%m-%d')
            
            # Eğer son indirme bugün değilse veya hiç indirme yapılmamışsa
            if not last_download_date or last_download_date != today:
                await db.execute(
                    'UPDATE users SET daily_downloads = 0, last_download_date = ? WHERE user_id = ?',
                    (today, user_id)
                )
                await db.commit()
                return True
                
            # Premium kullanıcı kontrolü
            is_premium = await self.is_premium(user_id)
            if is_premium:
                return True
                
            # Günlük indirme limiti kontrolü
            if daily_downloads < DAILY_DOWNLOAD_LIMIT:
                return True
                
            return False

    async def increment_download_count(self, user_id):
        async with await self._get_connection() as db:
            await db.execute(
                'UPDATE users SET daily_downloads = daily_downloads + 1 WHERE user_id = ?',
                (user_id,)
            )
            await db.execute(
                'UPDATE users SET last_download_date = ? WHERE user_id = ?',
                (datetime.now().strftime('%Y-%m-%d'), user_id)
            )
            await db.commit()

    async def add_to_history(self, user_id, file_name):
        async with await self._get_connection() as db:
            await db.execute(
                'INSERT INTO download_history (user_id, file_name, download_date) VALUES (?, ?, ?)',
                (user_id, file_name, datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
            )
            await db.commit()

    async def get_download_stats(self, user_id):
        async with await self._get_connection() as db:
            cursor = await db.execute(
                'SELECT daily_downloads, last_download_date FROM users WHERE user_id = ?',
                (user_id,)
            )
            result = await cursor.fetchone()
            return result if result else (0, None)

    async def set_premium_status(self, user_id, status):
        async with await self._get_connection() as db:
            await db.execute(
                'UPDATE users SET is_premium = ? WHERE user_id = ?',
                (status, user_id)
            )
            await db.commit()
