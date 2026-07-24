import asyncio
import html
import logging
import os
import random
import sqlite3
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union

from aiogram import Bot, Dispatcher, F, Router
from aiogram.enums import ChatMemberStatus, ChatType, ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    CallbackQuery,
    ChatMemberUpdated,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TOKEN")
OWNER_ID = os.getenv("OWNER_ID")
CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME", "@gift_e_z")
DATABASE_PATH = os.getenv("DATABASE", "database.db")

if not TOKEN or not OWNER_ID:
    raise ValueError("Ошибка: TOKEN и OWNER_ID должны быть указаны в файле .env")

try:
    OWNER_ID = int(OWNER_ID)
except ValueError:
    raise ValueError("Ошибка: OWNER_ID должен быть целым числом")

# Инициализация бота и диспетчера
bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())
router = Router()
dp.include_router(router)

# Кэш для защиты от спама в группах (anti-flood)
user_last_reward_time: Dict[int, datetime] = {}
user_last_msg_time: Dict[int, datetime] = {}


# ==============================================================================
# ВСПОМОГАТЕЛЬНЫЙ АСИНХРОННЫЙ АДАПТЕР ДЛЯ SQLITE3
# ==============================================================================

def _db_execute(query: str, params: tuple = (), fetchone: bool = False, fetchall: bool = False, commit: bool = True):
    with sqlite3.connect(DATABASE_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(query, params)
        last_id = cursor.lastrowid
        row_count = cursor.rowcount

        result = None
        if fetchone:
            row = cursor.fetchone()
            result = dict(row) if row else None
        elif fetchall:
            rows = cursor.fetchall()
            result = [dict(r) for r in rows]
        else:
            result = last_id if last_id and last_id > 0 else row_count

        if commit:
            conn.commit()
        return result


async def db_query(query: str, params: tuple = (), fetchone: bool = False, fetchall: bool = False, commit: bool = True):
    return await asyncio.to_thread(_db_execute, query, params, fetchone, fetchall, commit)


# ==============================================================================
# СИСТЕМА ЛОКАЛИЗАЦИИ И СТРОКИ ТЕКСТОВ
# ==============================================================================

STRINGS = {
    "ru": {
        "currency": "Звезды",
        "select_lang": "👋 Пожалуйста, выберите язык / Please select a language:",
        "lang_set": "🌐 Язык успешно изменен на Русский!",
        "sub_required": (
            "⚠️ Для использования GiftEz Stars необходимо подписаться на наш официальный канал {channel}.\n\n"
            "После подписки нажмите кнопку «Проверить подписку»."
        ),
        "btn_sub": "📢 Подписаться",
        "btn_check_sub": "✅ Проверить подписку",
        "btn_back": "🔙 Назад",
        "btn_profile": "👤 Профиль",
        "btn_earn": "💰 Заработать",
        "btn_ref": "👥 Реферальная система",
        "btn_channel": "📢 Наш канал",
        "btn_admin": "⚙️ Админ-панель",
        "btn_withdraw": "⭐ Вывести Звезды",
        "btn_bonus": "🎁 Ежедневный бонус",
        "btn_change_lang": "🌐 Сменить язык",
        "btn_open_chat": "💬 Открыть чат",
        "main_menu_text": "🌟 <b>Главное меню GiftEz Stars</b>\n\nВыберите нужный раздел в меню ниже:",
        "profile_text": (
            "👤 <b>Имя:</b> {name}\n"
            "🆔 <b>ID:</b> <code>{user_id}</code>\n"
            "⭐ <b>Баланс:</b> {balance:.3f} {currency}\n"
            "👥 <b>Приглашено рефералов:</b> {ref_count}\n"
            "📅 <b>Регистрация:</b> {reg_date}\n"
            "🌐 <b>Язык:</b> {lang_name}"
        ),
        "ref_text": (
            "👥 <b>Реферальная система</b>\n\n"
            "Приглашайте друзей и получайте бонус за каждого зарегистрированного реферала!\n\n"
            "🎁 <b>Награда:</b> от 0.001 до 10.0 {currency} (случайным образом)\n"
            "👥 <b>Ваших рефералов:</b> {ref_count}\n\n"
            "🔗 <b>Ваша реферальная ссылка:</b>\n<code>{ref_link}</code>"
        ),
        "earn_text": (
            "💰 <b>Заработок Звезд</b>\n\n"
            "Общайтесь в наших подключенных группах и получайте Звезды за активность!\n"
            "Накапливайте баланс и обменивайте его на настоящие Telegram Stars."
        ),
        "no_groups": "К сожалению, пока нет доступных подключенных групп.",
        "select_group": "💬 Выберите группу для общения и заработка:",
        "bonus_cooldown": "⏳ Следующий ежедневный бонус будет доступен через:\n\n<b>{hours} ч. {minutes} мин.</b>",
        "bonus_received": "🎁 <b>Ежедневный бонус получен!</b>\n\nВам начислено: <b>+{amount:.3f} {currency}</b>",
        "bonus_disabled": "🎁 Ежедневный бонус временно отключен администрацией.",
        "withdraw_disabled": "⚠️ Выводы временно недоступны.",
        "withdraw_menu": "⭐ <b>Вывод Звезд</b>\n\nВыберите сумму для создания заявки на вывод:",
        "withdraw_insufficient": "❌ <b>Недостаточно Звезд</b>\n\nВаш баланс: {balance:.3f} {currency}\nНеобходимо: {required} {currency}",
        "withdraw_cooldown": "⏳ Новую заявку можно создать через:\n\n<b>{minutes} мин. {seconds} сек.</b>",
        "withdraw_created": "📤 <b>Заявка на вывод создана!</b>\n\nСумма: <b>{amount} {currency}</b>\nСтатус: 🟡 <b>Новая</b>\n\nАдминистрация проверит её в ближайшее время.",
        "withdraw_user_notif_ok": "✅ Ваша заявка на вывод #{withdraw_id} на сумму {amount} {currency} успешно выполнена!",
        "withdraw_user_notif_reject": "❌ Ваша заявка на вывод #{withdraw_id} на сумму {amount} {currency} была отклонена.\n\n<b>Причина:</b> {reason}",
        "withdraw_user_notif_hold": "🟠 Ваша заявка на вывод #{withdraw_id} на сумму {amount} {currency} временно отложена.",
        "sub_check_failed": "❌ Вы всё еще не подписаны на канал {channel}. Подпишитесь и попробуйте снова!",
        "banned_text": "🚫 <b>Вы заблокированы в боте.</b>\n\nПричина: {reason}",
        "group_not_subbed": "⚠️ {name}, для получения Звезд необходимо подписаться на канал {channel}!",
        "group_reward_msg": "🎉 {name}, вам начислено <b>+{amount:.3f}</b> {currency} за активность в чате!",
        "admin_only_add": "❌ Добавлять бота в группы могут только администраторы группы.",
        "group_connected": "✅ <b>GiftEz Stars успешно подключен!</b>\n\nТеперь пользователи могут получать Звезды за активность в этом чате.",
        "group_already_connected": "ℹ️ Эта группа уже подключена к системе.",
        # Админка
        "admin_menu_title": "⚙️ <b>Админ-панель Управления</b>",
        "admin_btn_users": "👥 Пользователи",
        "admin_btn_withdraws": "📤 Активные заявки",
        "admin_btn_history": "📚 История выводов",
        "admin_btn_broadcast": "📢 Рассылка",
        "admin_btn_ban": "🚫 Бан / Разбан",
        "admin_btn_balance": "⭐ Управление балансом",
        "admin_btn_chances": "🎲 Шансы сообщений",
        "admin_btn_ref_chances": "👥 Настройки рефералов",
        "admin_btn_bonus_cfg": "🎁 Ежедневный бонус",
        "admin_btn_modules": "⚙️ Модули",
        "admin_btn_admins": "👮 Администраторы",
        "admin_btn_groups": "🏠 Группы",
        "admin_btn_settings": "⚙️ Настройки",
        "admin_btn_stats": "📊 Статистика",
        "no_permission": "❌ У вас нет прав для выполнения данного действия.",
    },
    "en": {
        "currency": "Stars",
        "select_lang": "👋 Please select a language / Пожалуйста, выберите язык:",
        "lang_set": "🌐 Language successfully changed to English!",
        "sub_required": (
            "⚠️ To use GiftEz Stars, you must subscribe to our official channel {channel}.\n\n"
            "After subscribing, click the «Check Subscription» button."
        ),
        "btn_sub": "📢 Subscribe",
        "btn_check_sub": "✅ Check Subscription",
        "btn_back": "🔙 Back",
        "btn_profile": "👤 Profile",
        "btn_earn": "💰 Earn",
        "btn_ref": "👥 Referral System",
        "btn_channel": "📢 Our Channel",
        "btn_admin": "⚙️ Admin Panel",
        "btn_withdraw": "⭐ Withdraw Stars",
        "btn_bonus": "🎁 Daily Bonus",
        "btn_change_lang": "🌐 Change Language",
        "btn_open_chat": "💬 Open Chat",
        "main_menu_text": "🌟 <b>GiftEz Stars Main Menu</b>\n\nSelect a section from the menu below:",
        "profile_text": (
            "👤 <b>Name:</b> {name}\n"
            "🆔 <b>ID:</b> <code>{user_id}</code>\n"
            "⭐ <b>Balance:</b> {balance:.3f} {currency}\n"
            "👥 <b>Invited Referrals:</b> {ref_count}\n"
            "📅 <b>Registered:</b> {reg_date}\n"
            "🌐 <b>Language:</b> {lang_name}"
        ),
        "ref_text": (
            "👥 <b>Referral System</b>\n\n"
            "Invite friends and earn bonus for each registered user!\n\n"
            "🎁 <b>Reward:</b> from 0.001 to 10.0 {currency} (random)\n"
            "👥 <b>Your Referrals:</b> {ref_count}\n\n"
            "🔗 <b>Your Referral Link:</b>\n<code>{ref_link}</code>"
        ),
        "earn_text": (
            "💰 <b>Earn Stars</b>\n\n"
            "Chat in our connected groups and receive Stars for your activity!\n"
            "Accumulate balance and exchange it for real Telegram Stars."
        ),
        "no_groups": "Unfortunately, there are no connected groups available yet.",
        "select_group": "💬 Select a group to chat and earn:",
        "bonus_cooldown": "⏳ Next daily bonus will be available in:\n\n<b>{hours} h. {minutes} min.</b>",
        "bonus_received": "🎁 <b>Daily Bonus Claimed!</b>\n\nYou received: <b>+{amount:.3f} {currency}</b>",
        "bonus_disabled": "🎁 Daily bonus is temporarily disabled by administration.",
        "withdraw_disabled": "⚠️ Withdrawals are temporarily unavailable.",
        "withdraw_menu": "⭐ <b>Withdraw Stars</b>\n\nSelect amount to create a withdrawal request:",
        "withdraw_insufficient": "❌ <b>Not enough Stars</b>\n\nYour balance: {balance:.3f} {currency}\nRequired: {required} {currency}",
        "withdraw_cooldown": "⏳ You can create a new request in:\n\n<b>{minutes} min. {seconds} sec.</b>",
        "withdraw_created": "📤 <b>Withdrawal Request Created!</b>\n\nAmount: <b>{amount} {currency}</b>\nStatus: 🟡 <b>New</b>\n\nAdmins will review it shortly.",
        "withdraw_user_notif_ok": "✅ Your withdrawal request #{withdraw_id} for {amount} {currency} has been approved!",
        "withdraw_user_notif_reject": "❌ Your withdrawal request #{withdraw_id} for {amount} {currency} was rejected.\n\n<b>Reason:</b> {reason}",
        "withdraw_user_notif_hold": "🟠 Your withdrawal request #{withdraw_id} for {amount} {currency} is put on hold.",
        "sub_check_failed": "❌ You are still not subscribed to {channel}. Please subscribe and try again!",
        "banned_text": "🚫 <b>You are banned in the bot.</b>\n\nReason: {reason}",
        "group_not_subbed": "⚠️ {name}, you must subscribe to {channel} to earn Stars!",
        "group_reward_msg": "🎉 {name}, you received <b>+{amount:.3f}</b> {currency} for chat activity!",
        "admin_only_add": "❌ Only group administrators can add this bot.",
        "group_connected": "✅ <b>GiftEz Stars successfully connected!</b>\n\nUsers can now earn Stars for activity in this chat.",
        "group_already_connected": "ℹ️ This group is already connected.",
        # Admin
        "admin_menu_title": "⚙️ <b>Admin Control Panel</b>",
        "admin_btn_users": "👥 Users",
        "admin_btn_withdraws": "📤 Active Requests",
        "admin_btn_history": "📚 Withdrawal History",
        "admin_btn_broadcast": "📢 Broadcast",
        "admin_btn_ban": "🚫 Ban / Unban",
        "admin_btn_balance": "⭐ Manage Balance",
        "admin_btn_chances": "🎲 Message Chances",
        "admin_btn_ref_chances": "👥 Referral Settings",
        "admin_btn_bonus_cfg": "🎁 Daily Bonus Config",
        "admin_btn_modules": "⚙️ Modules",
        "admin_btn_admins": "👮 Administrators",
        "admin_btn_groups": "🏠 Groups",
        "admin_btn_settings": "⚙️ Settings",
        "admin_btn_stats": "📊 Statistics",
        "no_permission": "❌ You do not have permission to perform this action.",
    },
}

ALL_PERMISSIONS = [
    "view_users", "edit_balance", "ban_users", "unban_users",
    "broadcast", "manage_chances", "manage_bonus", "manage_withdraws",
    "view_history", "view_active_withdraws", "manage_modules",
    "manage_settings", "view_stats", "manage_admins", "manage_groups", "full_access"
]


def get_str(key: str, lang: str = "ru", **kwargs) -> str:
    lang_code = lang if lang in STRINGS else "ru"
    template = STRINGS[lang_code].get(key, STRINGS["ru"].get(key, key))
    escaped_kwargs = {
        k: (v if k == "name" else (html.escape(str(v)) if isinstance(v, str) else v))
        for k, v in kwargs.items()
    }
    return template.format(**escaped_kwargs)


async def safe_edit_text(message: Message, text: str, reply_markup: Optional[InlineKeyboardMarkup] = None,
                         parse_mode: str = ParseMode.HTML):
    """Безопасная обертка над edit_text для игнорирования TelegramBadRequest при отсутствии изменений."""
    try:
        await message.edit_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            pass
        else:
            raise e


# ==============================================================================
# БАЗА ДАННЫХ И МИГРАЦИИ
# ==============================================================================

async def add_column_if_not_exists(table: str, column: str, col_type: str):
    """Безопасно добавляет новую колонку, если её ещё нет в таблице."""
    rows = await db_query(f"PRAGMA table_info({table})", fetchall=True) or []
    columns = [row["name"] for row in rows]
    if column not in columns:
        await db_query(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")


async def init_db():
    queries = [
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER UNIQUE,
            username TEXT,
            first_name TEXT,
            balance REAL DEFAULT 0.0,
            referrer_id INTEGER DEFAULT 0,
            language TEXT DEFAULT 'ru',
            register_date TEXT,
            last_activity TEXT,
            last_bonus TEXT,
            is_banned INTEGER DEFAULT 0,
            ban_until TEXT
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS groups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER UNIQUE,
            title TEXT,
            added_by INTEGER,
            created_at TEXT,
            status INTEGER DEFAULT 1
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS withdraws (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount REAL,
            status TEXT DEFAULT 'new',
            created_at TEXT,
            updated_at TEXT,
            admin_id INTEGER DEFAULT 0,
            reject_reason TEXT DEFAULT ''
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER UNIQUE,
            created_at TEXT,
            added_by INTEGER
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS permissions (
            admin_id INTEGER,
            permission_name TEXT,
            enabled INTEGER DEFAULT 1,
            PRIMARY KEY (admin_id, permission_name)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            admin_id INTEGER,
            user_id INTEGER,
            action TEXT,
            old_value TEXT,
            new_value TEXT,
            created_at TEXT
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS bonus_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount REAL,
            created_at TEXT
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS messages_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            group_id INTEGER,
            created_at TEXT
        )
        """
    ]

    for q in queries:
        await db_query(q)

    # Автоматическая миграция реферального поля
    await add_column_if_not_exists("users", "referrer_id", "INTEGER DEFAULT 0")

    default_settings = {
        "mod_rewards": "1",
        "mod_withdraws": "1",
        "mod_bonus": "1",
        "mod_sub_check": "1",
        "mod_groups": "1",
        "mod_broadcast": "1",
        "min_msg_len": "5",
        "antiflood_cooldown": "30",
        "withdraw_cooldown": "300",
        "msg_reward_chance": "15",
        "rng_0.001_0.01": "80",
        "rng_0.01_0.10": "70",
        "rng_0.10_0.50": "20",
        "rng_0.50_1.00": "7",
        "rng_1.00_2.00": "2",
        "rng_2.00_3.00": "0.8",
        "rng_3.00_4.00": "0.15",
        "rng_4.00_5.00": "0.05",
        "bonus_min": "0.01",
        "bonus_max": "2.00",
        # Шансы реферальных диапазонов (в процентах)
        "ref_rng_0.001_0.10": "60",
        "ref_rng_0.10_1.00": "25",
        "ref_rng_1.00_2.00": "8",
        "ref_rng_2.00_3.00": "4",
        "ref_rng_3.00_4.00": "1.5",
        "ref_rng_4.00_5.00": "0.8",
        "ref_rng_5.00_6.00": "0.4",
        "ref_rng_6.00_7.00": "0.2",
        "ref_rng_7.00_8.00": "0.08",
        "ref_rng_8.00_9.00": "0.015",
        "ref_rng_9.00_10.00": "0.005",
    }

    for k, v in default_settings.items():
        await db_query("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v))

    now_str = datetime.now().isoformat()
    await db_query("INSERT OR IGNORE INTO admins (telegram_id, created_at, added_by) VALUES (?, ?, ?)",
                   (OWNER_ID, now_str, OWNER_ID))

    for perm in ALL_PERMISSIONS:
        await db_query("INSERT OR IGNORE INTO permissions (admin_id, permission_name, enabled) VALUES (?, ?, 1)",
                       (OWNER_ID, perm))


# Вспомогательные функции взаимодействия с БД

async def get_setting(key: str, default: str = "") -> str:
    res = await db_query("SELECT value FROM settings WHERE key = ?", (key,), fetchone=True)
    return res["value"] if res else default


async def set_setting(key: str, value: str):
    await db_query("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))


async def get_user(telegram_id: int) -> Optional[Dict[str, Any]]:
    return await db_query("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,), fetchone=True)


async def create_user(telegram_id: int, username: Optional[str], first_name: Optional[str], referrer_id: int = 0) -> \
Dict[str, Any]:
    now = datetime.now().isoformat()
    await db_query("""
        INSERT INTO users (telegram_id, username, first_name, referrer_id, register_date, last_activity)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (telegram_id, username or "", first_name or "", referrer_id, now, now))

    # Реферальная награда пригласившему
    if referrer_id > 0 and referrer_id != telegram_id:
        ref_user = await get_user(referrer_id)
        if ref_user:
            ref_ranges = [
                (0.001, 0.1, float(await get_setting("ref_rng_0.001_0.10", "60"))),
                (0.1, 1.0, float(await get_setting("ref_rng_0.10_1.00", "25"))),
                (1.0, 2.0, float(await get_setting("ref_rng_1.00_2.00", "8"))),
                (2.0, 3.0, float(await get_setting("ref_rng_2.00_3.00", "4"))),
                (3.0, 4.0, float(await get_setting("ref_rng_3.00_4.00", "1.5"))),
                (4.0, 5.0, float(await get_setting("ref_rng_4.00_5.00", "0.8"))),
                (5.0, 6.0, float(await get_setting("ref_rng_5.00_6.00", "0.4"))),
                (6.0, 7.0, float(await get_setting("ref_rng_6.00_7.00", "0.2"))),
                (7.0, 8.0, float(await get_setting("ref_rng_7.00_8.00", "0.08"))),
                (8.0, 9.0, float(await get_setting("ref_rng_8.00_9.00", "0.015"))),
                (9.0, 10.0, float(await get_setting("ref_rng_9.00_10.00", "0.005"))),
            ]
            weights = [r[2] for r in ref_ranges]
            sel = random.choices(ref_ranges, weights=weights, k=1)[0]
            ref_reward = round(random.uniform(sel[0], sel[1]), 3)

            await update_user_balance(referrer_id, ref_reward)
            try:
                msg = f"🎉 По вашей реферальной ссылке зарегистрировался новый пользователь!\n🎁 Вам начислено <b>+{ref_reward:.3f} Stars</b>"
                await bot.send_message(referrer_id, msg, parse_mode=ParseMode.HTML)
            except Exception:
                pass

    return await get_user(telegram_id)


async def update_user_activity(telegram_id: int):
    now = datetime.now().isoformat()
    await db_query("UPDATE users SET last_activity = ? WHERE telegram_id = ?", (now, telegram_id))


async def update_user_balance(telegram_id: int, delta: float) -> float:
    await db_query("UPDATE users SET balance = balance + ? WHERE telegram_id = ?", (delta, telegram_id))
    res = await db_query("SELECT balance FROM users WHERE telegram_id = ?", (telegram_id,), fetchone=True)
    return res["balance"] if res else 0.0


async def set_user_language(telegram_id: int, lang: str):
    await db_query("UPDATE users SET language = ? WHERE telegram_id = ?", (lang, telegram_id))


async def is_admin(telegram_id: int) -> bool:
    if telegram_id == OWNER_ID:
        return True
    res = await db_query("SELECT id FROM admins WHERE telegram_id = ?", (telegram_id,), fetchone=True)
    return res is not None


async def has_perm(telegram_id: int, perm_name: str) -> bool:
    if telegram_id == OWNER_ID:
        return True
    res = await db_query("SELECT enabled FROM permissions WHERE admin_id = ? AND permission_name = ?",
                         (telegram_id, perm_name), fetchone=True)
    if res and res["enabled"] == 1:
        return True
    res_full = await db_query("SELECT enabled FROM permissions WHERE admin_id = ? AND permission_name = 'full_access'",
                              (telegram_id,), fetchone=True)
    return res_full is not None and res_full["enabled"] == 1


async def log_admin_action(admin_id: int, user_id: int, action: str, old_val: str, new_val: str):
    now = datetime.now().isoformat()
    await db_query("""
        INSERT INTO history (admin_id, user_id, action, old_value, new_value, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (admin_id, user_id, action, str(old_val), str(new_val), now))


# ==============================================================================
# ПРОВЕРКА ПОДПИСКИ И БАНА
# ==============================================================================

async def check_channel_subscription(user_id: int) -> bool:
    mod_sub = await get_setting("mod_sub_check", "1")
    if mod_sub == "0":
        return True
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_USERNAME, user_id=user_id)
        return member.status in [
            ChatMemberStatus.MEMBER,
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.CREATOR,
        ]
    except Exception as e:
        logging.error(f"Ошибка проверки подписки пользователя {user_id}: {e}")
        return True


async def check_user_ban_status(user: Dict[str, Any]) -> bool:
    if not user.get("is_banned"):
        return False
    ban_until_str = user.get("ban_until")
    if ban_until_str:
        try:
            ban_until = datetime.fromisoformat(ban_until_str)
            if datetime.now() > ban_until:
                await db_query("UPDATE users SET is_banned = 0, ban_until = NULL WHERE telegram_id = ?",
                               (user["telegram_id"],))
                return False
        except ValueError:
            pass
    return True


# ==============================================================================
# КЛАВИАТУРЫ ПОЛЬЗОВАТЕЛЯ
# ==============================================================================

def get_lang_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🇷🇺 Русский", callback_data="set_lang:ru"),
            InlineKeyboardButton(text="🇬🇧 English", callback_data="set_lang:en")
        ]
    ])


def get_sub_keyboard(lang: str) -> InlineKeyboardMarkup:
    url = f"https://t.me/{CHANNEL_USERNAME.replace('@', '')}"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_str("btn_sub", lang), url=url)],
        [InlineKeyboardButton(text=get_str("btn_check_sub", lang), callback_data="check_subscription")]
    ])


async def get_main_menu_keyboard(telegram_id: int, lang: str) -> InlineKeyboardMarkup:
    kb = [
        [
            InlineKeyboardButton(text=get_str("btn_profile", lang), callback_data="menu_profile"),
            InlineKeyboardButton(text=get_str("btn_earn", lang), callback_data="menu_earn"),
        ],
        [InlineKeyboardButton(text=get_str("btn_channel", lang),
                              url=f"https://t.me/{CHANNEL_USERNAME.replace('@', '')}")]
    ]
    if await is_admin(telegram_id):
        kb.append([InlineKeyboardButton(text=get_str("btn_admin", lang), callback_data="admin_main")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


async def get_profile_keyboard(telegram_id: int, lang: str) -> InlineKeyboardMarkup:
    kb = [
        [InlineKeyboardButton(text=get_str("btn_withdraw", lang), callback_data="user_withdraw")],
        [InlineKeyboardButton(text=get_str("btn_bonus", lang), callback_data="user_bonus")],
        [InlineKeyboardButton(text=get_str("btn_ref", lang), callback_data="menu_ref")],
        [InlineKeyboardButton(text=get_str("btn_change_lang", lang), callback_data="user_change_lang")],
        [InlineKeyboardButton(text=get_str("btn_back", lang), callback_data="menu_main")]
    ]
    if await is_admin(telegram_id):
        kb.insert(4, [InlineKeyboardButton(text=get_str("btn_admin", lang), callback_data="admin_main")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def get_withdraw_amounts_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⭐ 13", callback_data="withdraw_req:13"),
            InlineKeyboardButton(text="⭐ 21", callback_data="withdraw_req:21"),
            InlineKeyboardButton(text="⭐ 43", callback_data="withdraw_req:43")
        ],
        [InlineKeyboardButton(text=get_str("btn_back", lang), callback_data="menu_profile")]
    ])


# ==============================================================================
# СОСТОЯНИЯ FSM
# ==============================================================================

class AdminFSM(StatesGroup):
    waiting_reject_reason = State()
    waiting_broadcast_msg = State()
    waiting_add_admin_id = State()
    waiting_balance_user_id = State()
    waiting_balance_amount = State()
    waiting_ban_user_id = State()
    waiting_ban_time = State()
    waiting_ban_reason = State()
    waiting_unban_user_id = State()
    waiting_setting_value = State()


# ==============================================================================
# ОБРАБОТЧИКИ ПОЛЬЗОВАТЕЛЕСКОЙ ЧАСТИ
# ==============================================================================

@router.message(CommandStart(), F.chat.type == ChatType.PRIVATE)
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    user = await get_user(user_id)

    # Обработка реферальной глубокой ссылки
    referrer_id = 0
    args = message.text.split()
    if len(args) > 1 and args[1].startswith("ref_"):
        try:
            possible_ref = int(args[1].replace("ref_", ""))
            if possible_ref != user_id:
                referrer_id = possible_ref
        except ValueError:
            pass

    if not user:
        user = await create_user(user_id, message.from_user.username, message.from_user.first_name, referrer_id)
        await message.answer(
            get_str("select_lang", "ru"),
            reply_markup=get_lang_keyboard(),
            parse_mode=ParseMode.HTML
        )
        return

    await update_user_activity(user_id)

    if await check_user_ban_status(user):
        await message.answer(
            get_str("banned_text", user["language"], reason=user.get("ban_until") or "Нарушение правил"),
            parse_mode=ParseMode.HTML)
        return

    is_subbed = await check_channel_subscription(user_id)
    if not is_subbed:
        await message.answer(
            get_str("sub_required", user["language"], channel=CHANNEL_USERNAME),
            reply_markup=get_sub_keyboard(user["language"]),
            parse_mode=ParseMode.HTML
        )
        return

    await message.answer(
        get_str("main_menu_text", user["language"]),
        reply_markup=await get_main_menu_keyboard(user_id, user["language"]),
        parse_mode=ParseMode.HTML
    )


@router.callback_query(F.data.startswith("set_lang:"))
async def process_set_language(callback: CallbackQuery):
    await callback.answer()
    lang = callback.data.split(":")[1]
    user_id = callback.from_user.id
    await set_user_language(user_id, lang)

    is_subbed = await check_channel_subscription(user_id)
    if not is_subbed:
        await safe_edit_text(
            callback.message,
            get_str("sub_required", lang, channel=CHANNEL_USERNAME),
            reply_markup=get_sub_keyboard(lang),
            parse_mode=ParseMode.HTML
        )
    else:
        await safe_edit_text(
            callback.message,
            get_str("main_menu_text", lang),
            reply_markup=await get_main_menu_keyboard(user_id, lang),
            parse_mode=ParseMode.HTML
        )


@router.callback_query(F.data == "check_subscription")
async def process_check_subscription(callback: CallbackQuery):
    user_id = callback.from_user.id
    user = await get_user(user_id)
    lang = user["language"] if user else "ru"

    is_subbed = await check_channel_subscription(user_id)
    if is_subbed:
        await callback.answer("✅ Подписка подтверждена!")
        await safe_edit_text(
            callback.message,
            get_str("main_menu_text", lang),
            reply_markup=await get_main_menu_keyboard(user_id, lang),
            parse_mode=ParseMode.HTML
        )
    else:
        await callback.answer(get_str("sub_check_failed", lang, channel=CHANNEL_USERNAME), show_alert=True)


@router.callback_query(F.data == "menu_main")
async def process_menu_main(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.answer()
    user_id = callback.from_user.id
    user = await get_user(user_id)
    lang = user["language"] if user else "ru"

    await safe_edit_text(
        callback.message,
        get_str("main_menu_text", lang),
        reply_markup=await get_main_menu_keyboard(user_id, lang),
        parse_mode=ParseMode.HTML
    )


@router.callback_query(F.data == "menu_profile")
async def process_menu_profile(callback: CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    user = await get_user(user_id)
    if not user:
        return
    lang = user["language"]

    reg_date = user["register_date"].split("T")[0] if "T" in user["register_date"] else user["register_date"]
    lang_name = "Русский 🇷🇺" if lang == "ru" else "English 🇬🇧"
    currency = get_str("currency", lang)

    ref_res = await db_query("SELECT COUNT(*) as c FROM users WHERE referrer_id = ?", (user_id,), fetchone=True)
    ref_count = ref_res["c"] if ref_res else 0

    text = get_str(
        "profile_text",
        lang,
        name=html.escape(user["first_name"] or ""),
        user_id=user["telegram_id"],
        balance=user["balance"],
        currency=currency,
        ref_count=ref_count,
        reg_date=reg_date,
        lang_name=lang_name
    )

    await safe_edit_text(
        callback.message,
        text,
        reply_markup=await get_profile_keyboard(user_id, lang),
        parse_mode=ParseMode.HTML
    )


@router.callback_query(F.data == "menu_ref")
async def process_menu_ref(callback: CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    user = await get_user(user_id)
    if not user:
        return
    lang = user["language"]
    currency = get_str("currency", lang)

    bot_info = await bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start=ref_{user_id}"

    ref_res = await db_query("SELECT COUNT(*) as c FROM users WHERE referrer_id = ?", (user_id,), fetchone=True)
    ref_count = ref_res["c"] if ref_res else 0

    text = get_str(
        "ref_text",
        lang,
        currency=currency,
        ref_count=ref_count,
        ref_link=ref_link
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_str("btn_back", lang), callback_data="menu_profile")]
    ])
    await safe_edit_text(callback.message, text, reply_markup=kb, parse_mode=ParseMode.HTML)


@router.callback_query(F.data == "user_change_lang")
async def process_user_change_lang(callback: CallbackQuery):
    await callback.answer()
    await safe_edit_text(
        callback.message,
        get_str("select_lang", "ru"),
        reply_markup=get_lang_keyboard(),
        parse_mode=ParseMode.HTML
    )


@router.callback_query(F.data == "menu_earn")
async def process_menu_earn(callback: CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    user = await get_user(user_id)
    lang = user["language"] if user else "ru"

    groups = await db_query("SELECT * FROM groups WHERE status = 1", fetchall=True)

    kb = []
    if groups:
        for g in groups:
            kb.append(
                [InlineKeyboardButton(text=f"💬 {g['title']}", url=f"https://t.me/{CHANNEL_USERNAME.replace('@', '')}")])
    kb.append([InlineKeyboardButton(text=get_str("btn_channel", lang),
                                    url=f"https://t.me/{CHANNEL_USERNAME.replace('@', '')}")])
    kb.append([InlineKeyboardButton(text=get_str("btn_back", lang), callback_data="menu_main")])

    text = get_str("earn_text", lang)
    await safe_edit_text(
        callback.message,
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb),
        parse_mode=ParseMode.HTML
    )


# ==============================================================================
# ЕЖЕДНЕВНЫЙ БОНУС
# ==============================================================================

@router.callback_query(F.data == "user_bonus")
async def process_user_bonus(callback: CallbackQuery):
    user_id = callback.from_user.id
    user = await get_user(user_id)
    if not user:
        return
    lang = user["language"]
    currency = get_str("currency", lang)

    mod_bonus = await get_setting("mod_bonus", "1")
    if mod_bonus == "0":
        await callback.answer(get_str("bonus_disabled", lang), show_alert=True)
        return

    last_bonus_str = user.get("last_bonus")
    now = datetime.now()

    if last_bonus_str:
        try:
            last_bonus_time = datetime.fromisoformat(last_bonus_str)
            next_bonus_time = last_bonus_time + timedelta(hours=24)
            if now < next_bonus_time:
                await callback.answer()
                diff = next_bonus_time - now
                hours, remainder = divmod(int(diff.total_seconds()), 3600)
                minutes, _ = divmod(remainder, 60)
                text = get_str("bonus_cooldown", lang, hours=hours, minutes=minutes)
                kb = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text=get_str("btn_back", lang), callback_data="menu_profile")]])
                await safe_edit_text(callback.message, text, reply_markup=kb, parse_mode=ParseMode.HTML)
                return
        except ValueError:
            pass

    await callback.answer()
    b_min = float(await get_setting("bonus_min", "0.01"))
    b_max = float(await get_setting("bonus_max", "2.00"))
    reward = round(random.uniform(b_min, b_max), 3)

    await db_query("UPDATE users SET balance = balance + ?, last_bonus = ? WHERE telegram_id = ?",
                   (reward, now.isoformat(), user_id))
    await db_query("INSERT INTO bonus_history (user_id, amount, created_at) VALUES (?, ?, ?)",
                   (user_id, reward, now.isoformat()))

    text = get_str("bonus_received", lang, amount=reward, currency=currency)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=get_str("btn_back", lang), callback_data="menu_profile")]])
    await safe_edit_text(callback.message, text, reply_markup=kb, parse_mode=ParseMode.HTML)


# ==============================================================================
# ВЫВОД ЗВЕЗД
# ==============================================================================

@router.callback_query(F.data == "user_withdraw")
async def process_user_withdraw_menu(callback: CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    user = await get_user(user_id)
    lang = user["language"] if user else "ru"

    await safe_edit_text(
        callback.message,
        get_str("withdraw_menu", lang),
        reply_markup=get_withdraw_amounts_keyboard(lang),
        parse_mode=ParseMode.HTML
    )


@router.callback_query(F.data.startswith("withdraw_req:"))
async def process_create_withdraw(callback: CallbackQuery):
    try:
        amount = float(callback.data.split(":")[1])
    except (ValueError, IndexError):
        await callback.answer("⚠️ Некорректная сумма вывода", show_alert=True)
        return

    user_id = callback.from_user.id
    user = await get_user(user_id)
    if not user:
        await callback.answer("⚠️ Пользователь не найден", show_alert=True)
        return

    lang = user["language"]
    currency = get_str("currency", lang)

    if await get_setting("mod_withdraws", "1") == "0":
        await callback.answer(get_str("withdraw_disabled", lang), show_alert=True)
        return

    cooldown_sec = int(await get_setting("withdraw_cooldown", "300"))
    now = datetime.now()

    last_req = await db_query("SELECT created_at FROM withdraws WHERE user_id = ? ORDER BY id DESC LIMIT 1", (user_id,),
                              fetchone=True)
    if last_req and last_req.get("created_at"):
        try:
            last_req_time = datetime.fromisoformat(last_req["created_at"])
            if now - last_req_time < timedelta(seconds=cooldown_sec):
                await callback.answer()
                remaining = timedelta(seconds=cooldown_sec) - (now - last_req_time)
                mins, secs = divmod(int(remaining.total_seconds()), 60)
                text = get_str("withdraw_cooldown", lang, minutes=mins, seconds=secs)
                kb = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text=get_str("btn_back", lang), callback_data="user_withdraw")]])
                await safe_edit_text(callback.message, text, reply_markup=kb, parse_mode=ParseMode.HTML)
                return
        except ValueError:
            pass

    # Атомарное списание средств
    rows_affected = await db_query(
        "UPDATE users SET balance = balance - ? WHERE telegram_id = ? AND balance >= ?",
        (amount, user_id, amount)
    )

    if not rows_affected or rows_affected == 0:
        user_updated = await get_user(user_id)
        current_bal = user_updated["balance"] if user_updated else 0.0
        await callback.answer()
        text = get_str("withdraw_insufficient", lang, balance=current_bal, currency=currency, required=amount)
        kb = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text=get_str("btn_back", lang), callback_data="user_withdraw")]])
        await safe_edit_text(callback.message, text, reply_markup=kb, parse_mode=ParseMode.HTML)
        return

    now_str = now.isoformat()
    withdraw_id = await db_query("""
        INSERT INTO withdraws (user_id, amount, status, created_at, updated_at)
        VALUES (?, ?, 'new', ?, ?)
    """, (user_id, amount, now_str, now_str))

    await callback.answer()
    text = get_str("withdraw_created", lang, amount=amount, currency=currency)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=get_str("btn_back", lang), callback_data="menu_profile")]])

    try:
        await safe_edit_text(callback.message, text, reply_markup=kb, parse_mode=ParseMode.HTML)
    except Exception:
        pass

    clean_first_name = html.escape(user.get('first_name') or '')
    clean_username = html.escape(user.get('username') or 'нет')

    admin_text = (
        f"📤 <b>Новая заявка на вывод #{withdraw_id}</b>\n\n"
        f"👤 <b>Пользователь:</b> {clean_first_name}\n"
        f"📛 <b>Username:</b> @{clean_username}\n"
        f"🆔 <b>ID:</b> <code>{user['telegram_id']}</code>\n"
        f"⭐ <b>Сумма:</b> {amount} {currency}\n"
        f"📅 <b>Дата:</b> {now_str.split('T')[0]}"
    )
    admin_kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Выполнить", callback_data=f"adm_wd_approve:{withdraw_id}"),
            InlineKeyboardButton(text="🟠 Отложить", callback_data=f"adm_wd_hold:{withdraw_id}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"adm_wd_reject:{withdraw_id}")
        ]
    ])

    admins = await db_query("SELECT telegram_id FROM admins", fetchall=True) or []
    for adm in admins:
        if await has_perm(adm["telegram_id"], "manage_withdraws"):
            try:
                await bot.send_message(adm["telegram_id"], admin_text, reply_markup=admin_kb, parse_mode=ParseMode.HTML)
            except Exception:
                pass


# ==============================================================================
# НАГРАДЫ ЗА СООБЩЕНИЯ В ГРУППАХ
# ==============================================================================

@router.message(
    F.chat.type.in_([ChatType.GROUP, ChatType.SUPERGROUP]), ~F.sender_chat
)
async def handle_group_message(message: Message):
    if not message.from_user or message.from_user.is_bot:
        return

    chat_id = message.chat.id
    user_id = message.from_user.id
    now = datetime.now()

    group = await db_query("SELECT status FROM groups WHERE chat_id = ?", (chat_id,), fetchone=True)
    if not group or group["status"] == 0:
        return

    if await get_setting("mod_rewards", "1") == "0":
        return

    user = await get_user(user_id)
    if not user:
        user = await create_user(user_id, message.from_user.username, message.from_user.first_name)

    await update_user_activity(user_id)

    if await check_user_ban_status(user):
        return

    is_subbed = await check_channel_subscription(user_id)
    if not is_subbed:
        last_warn = user_last_msg_time.get(user_id)
        if not last_warn or (now - last_warn > timedelta(minutes=5)):
            user_last_msg_time[user_id] = now
            name_link = f'<a href="tg://user?id={user_id}">{html.escape(message.from_user.first_name)}</a>'
            text = get_str("group_not_subbed", user["language"], name=name_link, channel=CHANNEL_USERNAME)
            await message.reply(text, parse_mode=ParseMode.HTML)
        return

    msg_text = message.text or message.caption or ""
    min_len = int(await get_setting("min_msg_len", "5"))
    if len(msg_text) < min_len:
        return

    cooldown_sec = int(await get_setting("antiflood_cooldown", "30"))
    last_reward = user_last_reward_time.get(user_id)
    if last_reward and (now - last_reward < timedelta(seconds=cooldown_sec)):
        return

    chance = float(await get_setting("msg_reward_chance", "15"))
    if chance <= 0.0 or (chance < 100.0 and random.uniform(0.0, 100.0) > chance):
        return

    ranges = [
        (0.001, 0.01, float(await get_setting("rng_0.001_0.01", "80"))),
        (0.01, 0.10, float(await get_setting("rng_0.01_0.10", "70"))),
        (0.10, 0.50, float(await get_setting("rng_0.10_0.50", "20"))),
        (0.50, 1.00, float(await get_setting("rng_0.50_1.00", "7"))),
        (1.00, 2.00, float(await get_setting("rng_1.00_2.00", "2"))),
        (2.00, 3.00, float(await get_setting("rng_2.00_3.00", "0.8"))),
        (3.00, 4.00, float(await get_setting("rng_3.00_4.00", "0.15"))),
        (4.00, 5.00, float(await get_setting("rng_4.00_5.00", "0.05"))),
    ]

    weights = [r[2] for r in ranges]
    selected_range = random.choices(ranges, weights=weights, k=1)[0]
    reward = round(random.uniform(selected_range[0], selected_range[1]), 3)

    await update_user_balance(user_id, reward)
    user_last_reward_time[user_id] = now

    await db_query("INSERT INTO messages_history (user_id, group_id, created_at) VALUES (?, ?, ?)",
                   (user_id, chat_id, now.isoformat()))

    currency = get_str("currency", user["language"])
    name_link = f'<a href="tg://user?id={user_id}">{html.escape(message.from_user.first_name)}</a>'
    text = get_str("group_reward_msg", user["language"], name=name_link, amount=reward, currency=currency)
    await message.reply(text, parse_mode=ParseMode.HTML)


# ==============================================================================
# ПОДКЛЮЧЕНИЕ ГРУППЫ БОТОМ
# ==============================================================================

@router.my_chat_member(F.chat.type.in_([ChatType.GROUP, ChatType.SUPERGROUP]))
async def process_bot_added_to_group(event: ChatMemberUpdated):
    if event.new_chat_member.status in [ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR]:
        added_by_user = event.from_user
        chat_id = event.chat.id
        title = event.chat.title or "Группа"

        try:
            member = await bot.get_chat_member(chat_id=chat_id, user_id=added_by_user.id)
            if member.status not in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR]:
                await bot.send_message(chat_id, get_str("admin_only_add", "ru"))
                await bot.leave_chat(chat_id)
                return
        except Exception:
            return

        now_str = datetime.now().isoformat()
        row = await db_query("SELECT id FROM groups WHERE chat_id = ?", (chat_id,), fetchone=True)
        if row:
            await bot.send_message(chat_id, get_str("group_already_connected", "ru"))
            return

        await db_query("""
            INSERT INTO groups (chat_id, title, added_by, created_at, status)
            VALUES (?, ?, ?, ?, 1)
        """, (chat_id, title, added_by_user.id, now_str))

        await bot.send_message(chat_id, get_str("group_connected", "ru"), parse_mode=ParseMode.HTML)


# ==============================================================================
# АДМИН-ПАНЕЛЬ
# ==============================================================================

async def build_admin_main_kb(admin_id: int, lang: str) -> InlineKeyboardMarkup:
    kb = []
    r1 = []
    if await has_perm(admin_id, "view_users"):
        r1.append(InlineKeyboardButton(text=get_str("admin_btn_users", lang), callback_data="adm_users_page:1"))
    if await has_perm(admin_id, "view_active_withdraws"):
        r1.append(InlineKeyboardButton(text=get_str("admin_btn_withdraws", lang), callback_data="adm_withdraws_act:1"))
    if r1: kb.append(r1)

    r2 = []
    if await has_perm(admin_id, "view_history"):
        r2.append(InlineKeyboardButton(text=get_str("admin_btn_history", lang), callback_data="adm_withdraws_hist:1"))
    if await has_perm(admin_id, "broadcast"):
        r2.append(InlineKeyboardButton(text=get_str("admin_btn_broadcast", lang), callback_data="adm_broadcast"))
    if r2: kb.append(r2)

    r3 = []
    if await has_perm(admin_id, "ban_users"):
        r3.append(InlineKeyboardButton(text=get_str("admin_btn_ban", lang), callback_data="adm_ban_menu"))
    if await has_perm(admin_id, "edit_balance"):
        r3.append(InlineKeyboardButton(text=get_str("admin_btn_balance", lang), callback_data="adm_balance_menu"))
    if r3: kb.append(r3)

    r4 = []
    if await has_perm(admin_id, "manage_chances"):
        r4.append(InlineKeyboardButton(text=get_str("admin_btn_chances", lang), callback_data="adm_chances_menu"))
        r4.append(
            InlineKeyboardButton(text=get_str("admin_btn_ref_chances", lang), callback_data="adm_ref_chances_menu"))
    if r4: kb.append(r4)

    r5 = []
    if await has_perm(admin_id, "manage_bonus"):
        r5.append(InlineKeyboardButton(text=get_str("admin_btn_bonus_cfg", lang), callback_data="adm_bonus_menu"))
    if await has_perm(admin_id, "manage_modules"):
        r5.append(InlineKeyboardButton(text=get_str("admin_btn_modules", lang), callback_data="adm_modules_menu"))
    if r5: kb.append(r5)

    r6 = []
    if await has_perm(admin_id, "manage_admins"):
        r6.append(InlineKeyboardButton(text=get_str("admin_btn_admins", lang), callback_data="adm_admins_menu"))
    if await has_perm(admin_id, "manage_groups"):
        r6.append(InlineKeyboardButton(text=get_str("admin_btn_groups", lang), callback_data="adm_groups_menu"))
    if r6: kb.append(r6)

    r7 = []
    if await has_perm(admin_id, "manage_settings"):
        r7.append(InlineKeyboardButton(text=get_str("admin_btn_settings", lang), callback_data="adm_settings_menu"))
    if await has_perm(admin_id, "view_stats"):
        r7.append(InlineKeyboardButton(text=get_str("admin_btn_stats", lang), callback_data="adm_stats"))
    if r7: kb.append(r7)

    kb.append([InlineKeyboardButton(text=get_str("btn_back", lang), callback_data="menu_main")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


@router.callback_query(F.data == "admin_main")
async def process_admin_main(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    user_id = callback.from_user.id
    if not await is_admin(user_id):
        await callback.answer(get_str("no_permission", "ru"), show_alert=True)
        return

    await callback.answer()
    user = await get_user(user_id)
    lang = user["language"] if user else "ru"

    await safe_edit_text(
        callback.message,
        get_str("admin_menu_title", lang),
        reply_markup=await build_admin_main_kb(user_id, lang),
        parse_mode=ParseMode.HTML
    )


# --- УПРАВЛЕНИЕ ШАНСАМИ И РЕФЕРАЛАМИ В АДМИНКЕ ---
@router.callback_query(F.data == "adm_ref_chances_menu")
async def process_adm_ref_chances_menu(callback: CallbackQuery):
    admin_id = callback.from_user.id
    if not await has_perm(admin_id, "manage_chances"):
        await callback.answer(get_str("no_permission", "ru"), show_alert=True)
        return

    await callback.answer()
    ref_keys = [
        ("ref_rng_0.001_0.10", "Диапазон 0.001 - 0.1 Stars"),
        ("ref_rng_0.10_1.00", "Диапазон 0.1 - 1 Stars"),
        ("ref_rng_1.00_2.00", "Диапазон 1 - 2 Stars"),
        ("ref_rng_2.00_3.00", "Диапазон 2 - 3 Stars"),
        ("ref_rng_3.00_4.00", "Диапазон 3 - 4 Stars"),
        ("ref_rng_4.00_5.00", "Диапазон 4 - 5 Stars"),
        ("ref_rng_5.00_6.00", "Диапазон 5 - 6 Stars"),
        ("ref_rng_6.00_7.00", "Диапазон 6 - 7 Stars"),
        ("ref_rng_7.00_8.00", "Диапазон 7 - 8 Stars"),
        ("ref_rng_8.00_9.00", "Диапазон 8 - 9 Stars"),
        ("ref_rng_9.00_10.00", "Диапазон 9 - 10 Stars"),
    ]

    text = "👥 <b>Настройка шансов реферальной системы (в %):</b>\n\n"
    kb = []
    for key, label in ref_keys:
        val = await get_setting(key, "0")
        text += f"🔹 {label}: <b>{val}%</b>\n"
        kb.append([InlineKeyboardButton(text=f"✏️ {label} ({val}%)", callback_data=f"adm_set_val:{key}")])

    kb.append([InlineKeyboardButton(text="🔙 Назад", callback_data="admin_main")])
    await safe_edit_text(callback.message, text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb),
                         parse_mode=ParseMode.HTML)


# --- СБРОС ТАЙМЕРОВ ---
@router.callback_query(F.data.startswith("adm_reset_bonus:"))
async def process_adm_reset_bonus(callback: CallbackQuery):
    admin_id = callback.from_user.id
    if not await is_admin(admin_id):
        await callback.answer(get_str("no_permission", "ru"), show_alert=True)
        return

    target_id = int(callback.data.split(":")[1])
    await db_query("UPDATE users SET last_bonus = NULL WHERE telegram_id = ?", (target_id,))
    await callback.answer("✅ Ежедневный бонус сброшен! Можно забрать снова.", show_alert=True)
    await process_adm_user_info(callback)


@router.callback_query(F.data.startswith("adm_reset_wd_cd:"))
async def process_adm_reset_wd_cd(callback: CallbackQuery):
    admin_id = callback.from_user.id
    if not await is_admin(admin_id):
        await callback.answer(get_str("no_permission", "ru"), show_alert=True)
        return

    target_id = int(callback.data.split(":")[1])
    # Убираем задержку вывода путем обновления времени последней заявки
    old_time = (datetime.now() - timedelta(days=1)).isoformat()
    await db_query("UPDATE withdraws SET created_at = ? WHERE user_id = ?", (old_time, target_id))
    await callback.answer("✅ Кулдаун на вывод сброшен!", show_alert=True)
    await process_adm_user_info(callback)


# --- УПРАВЛЕНИЕ ГРУППАМИ ---
@router.callback_query(F.data == "adm_groups_menu")
async def process_adm_groups_menu(callback: CallbackQuery):
    admin_id = callback.from_user.id
    if not await has_perm(admin_id, "manage_groups"):
        await callback.answer(get_str("no_permission", "ru"), show_alert=True)
        return

    await callback.answer()
    groups_list = await db_query("SELECT * FROM groups ORDER BY id DESC", fetchall=True) or []

    text = "🏠 <b>Управление подключенными группами:</b>\n\n"
    kb = []

    if not groups_list:
        text += "<i>Подключенных групп пока нет.</i>"
    else:
        for g in groups_list:
            st_icon = "🟢" if g["status"] == 1 else "🔴"
            title = html.escape(g["title"] or "Без названия")
            text += f"{st_icon} <b>{title}</b> | ID: <code>{g['chat_id']}</code>\n"
            kb.append([InlineKeyboardButton(text=f"⚙️ {st_icon} {title}", callback_data=f"adm_group_info:{g['id']}")])

    kb.append([InlineKeyboardButton(text="🔙 Назад", callback_data="admin_main")])
    await safe_edit_text(callback.message, text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb),
                         parse_mode=ParseMode.HTML)


@router.callback_query(F.data.startswith("adm_group_info:"))
async def process_adm_group_info(callback: CallbackQuery):
    admin_id = callback.from_user.id
    if not await has_perm(admin_id, "manage_groups"):
        await callback.answer(get_str("no_permission", "ru"), show_alert=True)
        return

    group_id = int(callback.data.split(":")[1])
    group = await db_query("SELECT * FROM groups WHERE id = ?", (group_id,), fetchone=True)
    if not group:
        await callback.answer("Группа не найдена", show_alert=True)
        return

    await callback.answer()
    st_text = "🟢 Активна (награды выдаются)" if group["status"] == 1 else "🔴 Отключена"
    toggle_btn_text = "🔴 Отключить группу" if group["status"] == 1 else "🟢 Включить группу"

    text = (
        f"🏠 <b>Детали группы:</b>\n\n"
        f"📌 <b>Название:</b> {html.escape(group['title'] or '')}\n"
        f"🆔 <b>Chat ID:</b> <code>{group['chat_id']}</code>\n"
        f"👤 <b>Добавил ID:</b> <code>{group['added_by']}</code>\n"
        f"📅 <b>Дата создания:</b> {group['created_at'].split('T')[0]}\n"
        f"⚙️ <b>Статус:</b> {st_text}"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=toggle_btn_text, callback_data=f"adm_group_toggle:{group['id']}")],
        [InlineKeyboardButton(text="🗑 Удалить группу", callback_data=f"adm_group_delete:{group['id']}")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="adm_groups_menu")]
    ])
    await safe_edit_text(callback.message, text, reply_markup=kb, parse_mode=ParseMode.HTML)


@router.callback_query(F.data.startswith("adm_group_toggle:"))
async def process_adm_group_toggle(callback: CallbackQuery):
    admin_id = callback.from_user.id
    if not await has_perm(admin_id, "manage_groups"):
        await callback.answer(get_str("no_permission", "ru"), show_alert=True)
        return

    group_id = int(callback.data.split(":")[1])
    group = await db_query("SELECT status FROM groups WHERE id = ?", (group_id,), fetchone=True)
    if not group:
        await callback.answer("Группа не найдена", show_alert=True)
        return

    new_st = 0 if group["status"] == 1 else 1
    await db_query("UPDATE groups SET status = ? WHERE id = ?", (new_st, group_id))
    await log_admin_action(admin_id, 0, "toggle_group_status", str(group["status"]), str(new_st))

    await callback.answer("Статус группы изменен!")
    await process_adm_group_info(callback)


@router.callback_query(F.data.startswith("adm_group_delete:"))
async def process_adm_group_delete(callback: CallbackQuery):
    admin_id = callback.from_user.id
    if not await has_perm(admin_id, "manage_groups"):
        await callback.answer(get_str("no_permission", "ru"), show_alert=True)
        return

    group_id = int(callback.data.split(":")[1])
    await db_query("DELETE FROM groups WHERE id = ?", (group_id,))
    await log_admin_action(admin_id, 0, "delete_group", str(group_id), "deleted")

    await callback.answer("Группа успешно удалена из базы!", show_alert=True)
    await process_adm_groups_menu(callback)


# --- СТАТИСТИКА ---
@router.callback_query(F.data == "adm_stats")
async def process_adm_stats(callback: CallbackQuery):
    user_id = callback.from_user.id
    if not await has_perm(user_id, "view_stats"):
        await callback.answer(get_str("no_permission", "ru"), show_alert=True)
        return

    await callback.answer()
    user = await get_user(user_id)
    lang = user["language"] if user else "ru"

    total_users = (await db_query("SELECT COUNT(*) as c FROM users", fetchone=True))["c"]
    total_refs = (await db_query("SELECT COUNT(*) as c FROM users WHERE referrer_id > 0", fetchone=True))["c"]
    total_msgs = (await db_query("SELECT COUNT(*) as c FROM messages_history", fetchone=True))["c"]
    total_stars_res = await db_query("SELECT SUM(balance) as s FROM users", fetchone=True)
    total_stars = total_stars_res["s"] if total_stars_res and total_stars_res["s"] else 0.0
    total_bonuses = (await db_query("SELECT COUNT(*) as c FROM bonus_history", fetchone=True))["c"]
    total_wd = (await db_query("SELECT COUNT(*) as c FROM withdraws", fetchone=True))["c"]
    ok_wd = (await db_query("SELECT COUNT(*) as c FROM withdraws WHERE status = 'approved'", fetchone=True))["c"]
    err_wd = (await db_query("SELECT COUNT(*) as c FROM withdraws WHERE status = 'rejected'", fetchone=True))["c"]
    hold_wd = (await db_query("SELECT COUNT(*) as c FROM withdraws WHERE status = 'hold'", fetchone=True))["c"]
    banned_users = (await db_query("SELECT COUNT(*) as c FROM users WHERE is_banned = 1", fetchone=True))["c"]
    total_admins = (await db_query("SELECT COUNT(*) as c FROM admins", fetchone=True))["c"]
    total_groups = (await db_query("SELECT COUNT(*) as c FROM groups WHERE status = 1", fetchone=True))["c"]

    text = (
        f"📊 <b>Системная Статистика</b>\n\n"
        f"👥 <b>Всего пользователей:</b> {total_users}\n"
        f"🔗 <b>Приглашено по рефералам:</b> {total_refs}\n"
        f"💬 <b>Обработано сообщений:</b> {total_msgs}\n"
        f"⭐ <b>Всего Звезд на балансах:</b> {total_stars:.3f}\n"
        f"🎁 <b>Выдано ежедневных бонусов:</b> {total_bonuses}\n"
        f"📤 <b>Всего заявок на вывод:</b> {total_wd}\n"
        f"  └ 🟢 Выполнено: {ok_wd}\n"
        f"  └ 🔴 Отклонено: {err_wd}\n"
        f"  └ 🟠 Отложено: {hold_wd}\n"
        f"🚫 <b>Заблокировано пользователей:</b> {banned_users}\n"
        f"👮 <b>Администраторов:</b> {total_admins}\n"
        f"🏠 <b>Подключенных групп:</b> {total_groups}"
    )
    kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=get_str("btn_back", lang), callback_data="admin_main")]])
    await safe_edit_text(callback.message, text, reply_markup=kb, parse_mode=ParseMode.HTML)


# --- СПИСОК ПОЛЬЗОВАТЕЛЕЙ ---
@router.callback_query(F.data.startswith("adm_users_page:"))
async def process_adm_users_page(callback: CallbackQuery):
    user_id = callback.from_user.id
    if not await has_perm(user_id, "view_users"):
        await callback.answer(get_str("no_permission", "ru"), show_alert=True)
        return

    await callback.answer()
    page = int(callback.data.split(":")[1])
    limit = 10
    offset = (page - 1) * limit

    user = await get_user(user_id)
    lang = user["language"] if user else "ru"

    total_count = (await db_query("SELECT COUNT(*) as c FROM users", fetchone=True))["c"]
    users_list = await db_query("SELECT * FROM users ORDER BY id DESC LIMIT ? OFFSET ?", (limit, offset),
                                fetchall=True) or []

    text = f"👥 <b>Список пользователей (Страница {page})</b>\n\n"
    kb = []
    for u in users_list:
        c_name = html.escape(u['first_name'] or 'Без имени')
        c_username = html.escape(u['username'] or 'нет')
        text += f"👤 <b>{c_name}</b> | @{c_username} | <code>{u['telegram_id']}</code> | ⭐ {u['balance']:.3f}\n"
        kb.append([InlineKeyboardButton(text=f"👤 {u['first_name'] or 'User'} ({u['telegram_id']})",
                                        callback_data=f"adm_user_info:{u['telegram_id']}")])

    nav = []
    if page > 1:
        nav.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"adm_users_page:{page - 1}"))
    if offset + limit < total_count:
        nav.append(InlineKeyboardButton(text="➡️ Вперед", callback_data=f"adm_users_page:{page + 1}"))
    if nav:
        kb.append(nav)

    kb.append([InlineKeyboardButton(text=get_str("btn_back", lang), callback_data="admin_main")])
    await safe_edit_text(callback.message, text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb),
                         parse_mode=ParseMode.HTML)


@router.callback_query(F.data.startswith("adm_user_info:"))
async def process_adm_user_info(callback: CallbackQuery):
    admin_id = callback.from_user.id
    target_id = int(callback.data.split(":")[1])
    u = await get_user(target_id)
    if not u:
        await callback.answer("Пользователь не найден", show_alert=True)
        return

    await callback.answer()
    admin = await get_user(admin_id)
    lang = admin["language"] if admin else "ru"

    status = "🚫 Заблокирован" if u["is_banned"] else "✅ Активен"
    c_name = html.escape(u['first_name'] or 'Без имени')
    c_username = html.escape(u['username'] or 'нет')

    ref_res = await db_query("SELECT COUNT(*) as c FROM users WHERE referrer_id = ?", (target_id,), fetchone=True)
    ref_count = ref_res["c"] if ref_res else 0

    referrer_info = "Нет"
    if u["referrer_id"] > 0:
        ref_u = await get_user(u["referrer_id"])
        if ref_u:
            ref_name = html.escape(ref_u['first_name'] or 'Без имени')
            referrer_info = f"{ref_name} (<code>{u['referrer_id']}</code>)"
        else:
            referrer_info = f"<code>{u['referrer_id']}</code>"

    text = (
        f"👤 <b>Информация о пользователе</b>\n\n"
        f"👤 <b>Имя:</b> {c_name}\n"
        f"📛 <b>Username:</b> @{c_username}\n"
        f"🆔 <b>ID:</b> <code>{u['telegram_id']}</code>\n"
        f"⭐ <b>Баланс:</b> {u['balance']:.3f}\n"
        f"👥 <b>Пригласил рефералов:</b> {ref_count}\n"
        f"🔗 <b>Пригласивший реферер:</b> {referrer_info}\n"
        f"📅 <b>Регистрация:</b> {u['register_date']}\n"
        f"🌐 <b>Язык:</b> {u['language']}\n"
        f"📌 <b>Статус:</b> {status}\n"
        f"⏱ <b>Активность:</b> {u['last_activity']}"
    )

    kb = []
    if await has_perm(admin_id, "edit_balance"):
        kb.append([
            InlineKeyboardButton(text="⭐ Выдать/Списать баланс", callback_data=f"adm_user_bal_edit:{u['telegram_id']}")
        ])

    # Кнопки сброса таймеров
    kb.append([
        InlineKeyboardButton(text="🎁 Сбросить таймер бонуса", callback_data=f"adm_reset_bonus:{u['telegram_id']}"),
        InlineKeyboardButton(text="⏳ Сбросить кулдаун вывода", callback_data=f"adm_reset_wd_cd:{u['telegram_id']}")
    ])

    if await has_perm(admin_id, "ban_users") and not u["is_banned"]:
        kb.append([InlineKeyboardButton(text="🚫 Забанить", callback_data=f"adm_user_ban_act:{u['telegram_id']}")])
    if await has_perm(admin_id, "unban_users") and u["is_banned"]:
        kb.append([InlineKeyboardButton(text="✅ Разбанить", callback_data=f"adm_user_unban_act:{u['telegram_id']}")])

    kb.append([InlineKeyboardButton(text=get_str("btn_back", lang), callback_data="adm_users_page:1")])
    await safe_edit_text(callback.message, text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb),
                         parse_mode=ParseMode.HTML)


# --- ВЫВОДЫ ЗАЯВКИ ---
@router.callback_query(F.data.startswith("adm_withdraws_act:"))
async def process_adm_withdraws_active(callback: CallbackQuery):
    admin_id = callback.from_user.id
    if not await has_perm(admin_id, "view_active_withdraws"):
        await callback.answer(get_str("no_permission", "ru"), show_alert=True)
        return

    await callback.answer()
    admin = await get_user(admin_id)
    lang = admin["language"] if admin else "ru"

    items = await db_query("SELECT * FROM withdraws WHERE status IN ('new', 'hold') ORDER BY id DESC", fetchall=True)

    if not items:
        text = "📤 <b>Активных заявок на вывод нет.</b>"
        kb = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text=get_str("btn_back", lang), callback_data="admin_main")]])
        await safe_edit_text(callback.message, text, reply_markup=kb, parse_mode=ParseMode.HTML)
        return

    text = "📤 <b>Список активных заявок:</b>\n\n"
    kb = []
    for item in items:
        u = await get_user(item["user_id"])
        uname = f"@{html.escape(u['username'])}" if u and u['username'] else "Н/Д"
        st = "🟡 Новая" if item["status"] == "new" else "🟠 Отложена"
        text += f"Заявка #{item['id']} | {uname} | ⭐ {item['amount']} | {st}\n"
        kb.append([InlineKeyboardButton(text=f"Управление #{item['id']} ({item['amount']} ⭐)",
                                        callback_data=f"adm_wd_manage:{item['id']}")])

    kb.append([InlineKeyboardButton(text=get_str("btn_back", lang), callback_data="admin_main")])
    await safe_edit_text(callback.message, text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb),
                         parse_mode=ParseMode.HTML)


@router.callback_query(F.data.startswith("adm_wd_manage:"))
async def process_adm_wd_manage(callback: CallbackQuery):
    await callback.answer()
    wd_id = int(callback.data.split(":")[1])
    wd = await db_query("SELECT * FROM withdraws WHERE id = ?", (wd_id,), fetchone=True)
    if not wd:
        await callback.answer("Заявка не найдена", show_alert=True)
        return

    u = await get_user(wd["user_id"])
    c_name = html.escape(u['first_name']) if u and u['first_name'] else 'Н/Д'
    c_uname = html.escape(u['username']) if u and u['username'] else 'Н/Д'

    text = (
        f"📤 <b>Управление заявкой #{wd['id']}</b>\n\n"
        f"👤 <b>Имя:</b> {c_name}\n"
        f"📛 <b>Username:</b> @{c_uname}\n"
        f"🆔 <b>ID:</b> <code>{wd['user_id']}</code>\n"
        f"⭐ <b>Сумма:</b> {wd['amount']}\n"
        f"📅 <b>Дата:</b> {wd['created_at']}\n"
        f"📌 <b>Статус:</b> {wd['status']}"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Выполнить", callback_data=f"adm_wd_approve:{wd['id']}"),
            InlineKeyboardButton(text="🟠 Отложить", callback_data=f"adm_wd_hold:{wd['id']}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"adm_wd_reject:{wd['id']}")
        ],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="adm_withdraws_act:1")]
    ])
    await safe_edit_text(callback.message, text, reply_markup=kb, parse_mode=ParseMode.HTML)


@router.callback_query(F.data.startswith("adm_wd_approve:"))
async def process_adm_wd_approve(callback: CallbackQuery):
    admin_id = callback.from_user.id
    if not await has_perm(admin_id, "manage_withdraws"):
        await callback.answer(get_str("no_permission", "ru"), show_alert=True)
        return

    wd_id = int(callback.data.split(":")[1])
    wd = await db_query("SELECT * FROM withdraws WHERE id = ?", (wd_id,), fetchone=True)
    if not wd or wd["status"] in ["approved", "rejected"]:
        await callback.answer("⚠️ Эта заявка уже обработана!", show_alert=True)
        return

    now_str = datetime.now().isoformat()
    await db_query("UPDATE withdraws SET status = 'approved', updated_at = ?, admin_id = ? WHERE id = ?",
                   (now_str, admin_id, wd_id))
    await log_admin_action(admin_id, wd["user_id"], "approve_withdraw", wd["status"], "approved")

    u = await get_user(wd["user_id"])
    if u:
        try:
            msg = get_str("withdraw_user_notif_ok", u["language"], withdraw_id=wd_id, amount=wd["amount"],
                          currency=get_str("currency", u["language"]))
            await bot.send_message(u["telegram_id"], msg, parse_mode=ParseMode.HTML)
        except Exception:
            pass

    await callback.answer("✅ Заявка помечена как выполненная!")
    await safe_edit_text(callback.message, f"✅ Заявка #{wd_id} успешно выполнена.")


@router.callback_query(F.data.startswith("adm_wd_hold:"))
async def process_adm_wd_hold(callback: CallbackQuery):
    admin_id = callback.from_user.id
    if not await has_perm(admin_id, "manage_withdraws"):
        await callback.answer(get_str("no_permission", "ru"), show_alert=True)
        return

    wd_id = int(callback.data.split(":")[1])
    wd = await db_query("SELECT * FROM withdraws WHERE id = ?", (wd_id,), fetchone=True)
    if not wd or wd["status"] in ["approved", "rejected"]:
        await callback.answer("⚠️ Эта заявка уже обработана!", show_alert=True)
        return

    now_str = datetime.now().isoformat()
    await db_query("UPDATE withdraws SET status = 'hold', updated_at = ?, admin_id = ? WHERE id = ?",
                   (now_str, admin_id, wd_id))
    await log_admin_action(admin_id, wd["user_id"], "hold_withdraw", wd["status"], "hold")

    u = await get_user(wd["user_id"])
    if u:
        try:
            msg = get_str("withdraw_user_notif_hold", u["language"], withdraw_id=wd_id, amount=wd["amount"],
                          currency=get_str("currency", u["language"]))
            await bot.send_message(u["telegram_id"], msg, parse_mode=ParseMode.HTML)
        except Exception:
            pass

    await callback.answer("🟠 Заявка временно отложена.")
    await safe_edit_text(callback.message, f"🟠 Заявка #{wd_id} отложена.")


@router.callback_query(F.data.startswith("adm_wd_reject:"))
async def process_adm_wd_reject(callback: CallbackQuery, state: FSMContext):
    admin_id = callback.from_user.id
    if not await has_perm(admin_id, "manage_withdraws"):
        await callback.answer(get_str("no_permission", "ru"), show_alert=True)
        return

    wd_id = int(callback.data.split(":")[1])
    wd = await db_query("SELECT status FROM withdraws WHERE id = ?", (wd_id,), fetchone=True)
    if not wd or wd["status"] in ["approved", "rejected"]:
        await callback.answer("⚠️ Эта заявка уже обработана!", show_alert=True)
        return

    await callback.answer()
    await state.update_data(reject_wd_id=wd_id)
    await state.set_state(AdminFSM.waiting_reject_reason)
    await safe_edit_text(callback.message, "❌ Введите причину отказа для пользователя:")


@router.message(AdminFSM.waiting_reject_reason)
async def process_reject_reason_input(message: Message, state: FSMContext):
    admin_id = message.from_user.id

    if not await has_perm(admin_id, "manage_withdraws"):
        await message.answer(get_str("no_permission", "ru"))
        await state.clear()
        return

    data = await state.get_data()
    wd_id = data.get("reject_wd_id")

    if not wd_id:
        await message.answer("⚠️ Ошибка: идентификатор заявки не найден.")
        await state.clear()
        return

    raw_reason = message.text or "Не указана"
    reason = html.escape(raw_reason.strip())
    now_str = datetime.now().isoformat()

    wd = await db_query("SELECT * FROM withdraws WHERE id = ?", (wd_id,), fetchone=True)

    if not wd:
        await message.answer("⚠️ Заявка не найдена.")
        await state.clear()
        return

    if wd["status"] in ["approved", "rejected"]:
        await message.answer("⚠️ Эта заявка уже была обработана ранее.")
        await state.clear()
        return

    await db_query("UPDATE users SET balance = balance + ? WHERE telegram_id = ?", (wd["amount"], wd["user_id"]))
    await db_query("""
        UPDATE withdraws SET status = 'rejected', reject_reason = ?, updated_at = ?, admin_id = ? WHERE id = ?
    """, (reason, now_str, admin_id, wd_id))

    await log_admin_action(admin_id, wd["user_id"], "reject_withdraw", wd["status"], f"rejected ({reason})")

    u = await get_user(wd["user_id"])
    if u:
        try:
            msg = get_str(
                "withdraw_user_notif_reject",
                u["language"],
                withdraw_id=wd_id,
                amount=wd["amount"],
                currency=get_str("currency", u["language"]),
                reason=reason
            )
            await bot.send_message(u["telegram_id"], msg, parse_mode=ParseMode.HTML)
        except Exception:
            pass

    await state.clear()
    await message.answer(
        f"❌ Заявка #{wd_id} отклонена. Средства ({wd['amount']}) вернулись на баланс пользователя.",
        reply_markup=await build_admin_main_kb(admin_id, "ru")
    )


# --- ИСТОРИЯ ВЫВОДОВ ---
@router.callback_query(F.data.startswith("adm_withdraws_hist:"))
async def process_adm_withdraws_history(callback: CallbackQuery):
    admin_id = callback.from_user.id
    if not await has_perm(admin_id, "view_history"):
        await callback.answer(get_str("no_permission", "ru"), show_alert=True)
        return

    await callback.answer()
    admin = await get_user(admin_id)
    lang = admin["language"] if admin else "ru"

    items = await db_query("SELECT * FROM withdraws ORDER BY id DESC LIMIT 20", fetchall=True) or []

    text = "📚 <b>История выводов (Последние 20):</b>\n\n"
    for item in items:
        created = item['created_at'].split('T')[0] if 'T' in item['created_at'] else item['created_at']
        text += f"#{item['id']} | User: <code>{item['user_id']}</code> | ⭐ {item['amount']} | Статус: {item['status']} | {created}\n"

    kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=get_str("btn_back", lang), callback_data="admin_main")]])
    await safe_edit_text(callback.message, text, reply_markup=kb, parse_mode=ParseMode.HTML)


# --- РАССЫЛКА ---
@router.callback_query(F.data == "adm_broadcast")
async def process_adm_broadcast(callback: CallbackQuery, state: FSMContext):
    admin_id = callback.from_user.id
    if not await has_perm(admin_id, "broadcast"):
        await callback.answer(get_str("no_permission", "ru"), show_alert=True)
        return

    await callback.answer()
    await state.set_state(AdminFSM.waiting_broadcast_msg)
    await safe_edit_text(callback.message, "📢 Отправьте сообщение для рассылки:")


@router.message(AdminFSM.waiting_broadcast_msg)
async def process_broadcast_msg_input(message: Message, state: FSMContext):
    await state.update_data(broadcast_msg_id=message.message_id, broadcast_chat_id=message.chat.id)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Отправить", callback_data="adm_broadcast_confirm")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_main")]
    ])
    await message.answer(
        "📢 <b>Предпросмотр рассылки.</b> Вы уверены, что хотите отправить это сообщение всем пользователям?",
        reply_markup=kb, parse_mode=ParseMode.HTML)


@router.callback_query(F.data == "adm_broadcast_confirm")
async def process_adm_broadcast_confirm(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    msg_id = data["broadcast_msg_id"]
    from_chat_id = data["broadcast_chat_id"]
    await state.clear()

    await safe_edit_text(callback.message, "⏳ Рассылка запущена...")

    users = await db_query("SELECT telegram_id FROM users WHERE is_banned = 0", fetchall=True) or []

    success = 0
    errors = 0

    for u in users:
        try:
            await bot.copy_message(chat_id=u["telegram_id"], from_chat_id=from_chat_id, message_id=msg_id)
            success += 1
            await asyncio.sleep(0.05)
        except Exception:
            errors += 1

    text = f"📢 <b>Рассылка завершена.</b>\n\n✅ Успешно отправлено: {success}\n❌ Ошибок доставки: {errors}"
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 В админку", callback_data="admin_main")]])
    await safe_edit_text(callback.message, text, reply_markup=kb, parse_mode=ParseMode.HTML)


# --- БАН И РАЗБАН ---
@router.callback_query(F.data == "adm_ban_menu")
async def process_adm_ban_menu(callback: CallbackQuery, state: FSMContext):
    admin_id = callback.from_user.id
    if not await has_perm(admin_id, "ban_users"):
        await callback.answer(get_str("no_permission", "ru"), show_alert=True)
        return

    await callback.answer()
    await state.set_state(AdminFSM.waiting_ban_user_id)
    await safe_edit_text(callback.message, "🚫 Введите Telegram ID пользователя для блокировки:")


@router.callback_query(F.data.startswith("adm_user_ban_act:"))
async def process_adm_user_ban_act(callback: CallbackQuery, state: FSMContext):
    admin_id = callback.from_user.id
    if not await has_perm(admin_id, "ban_users"):
        await callback.answer(get_str("no_permission", "ru"), show_alert=True)
        return

    await callback.answer()
    target_id = int(callback.data.split(":")[1])
    await state.update_data(ban_target_id=target_id)
    await state.set_state(AdminFSM.waiting_ban_time)
    await safe_edit_text(
        callback.message,
        f"⏳ Укажите срок бана для <code>{target_id}</code> в минутах (или 0 для бессрочного бана):",
        parse_mode=ParseMode.HTML)


@router.message(AdminFSM.waiting_ban_user_id)
async def process_ban_user_id_input(message: Message, state: FSMContext):
    try:
        target_id = int(message.text)
    except ValueError:
        await message.answer("❌ ID должен быть числом. Попробуйте еще раз:")
        return

    await state.update_data(ban_target_id=target_id)
    await state.set_state(AdminFSM.waiting_ban_time)
    await message.answer("⏳ Укажите срок бана в минутах (или 0 для пожизненного бана):")


@router.message(AdminFSM.waiting_ban_time)
async def process_ban_time_input(message: Message, state: FSMContext):
    try:
        minutes = int(message.text)
    except ValueError:
        await message.answer("❌ Время должно быть числом. Попробуйте еще раз:")
        return

    await state.update_data(ban_minutes=minutes)
    await state.set_state(AdminFSM.waiting_ban_reason)
    await message.answer("📝 Введите причину блокировки:")


@router.message(AdminFSM.waiting_ban_reason)
async def process_ban_reason_input(message: Message, state: FSMContext):
    data = await state.get_data()
    target_id = data["ban_target_id"]
    minutes = data["ban_minutes"]
    raw_reason = message.text or "Не указана"
    reason = html.escape(raw_reason.strip())
    admin_id = message.from_user.id

    ban_until_str = None
    if minutes > 0:
        ban_until_str = (datetime.now() + timedelta(minutes=minutes)).isoformat()

    await db_query("UPDATE users SET is_banned = 1, ban_until = ? WHERE telegram_id = ?", (ban_until_str, target_id))
    await log_admin_action(admin_id, target_id, "ban", "0", f"banned until {ban_until_str} ({reason})")

    try:
        await bot.send_message(target_id, get_str("banned_text", "ru", reason=reason), parse_mode=ParseMode.HTML)
    except Exception:
        pass

    await state.clear()
    await message.answer(f"🚫 Пользователь <code>{target_id}</code> успешно заблокирован.", parse_mode=ParseMode.HTML,
                         reply_markup=await build_admin_main_kb(admin_id, "ru"))


@router.callback_query(F.data.startswith("adm_user_unban_act:"))
async def process_adm_user_unban_act(callback: CallbackQuery):
    admin_id = callback.from_user.id
    if not await has_perm(admin_id, "unban_users"):
        await callback.answer(get_str("no_permission", "ru"), show_alert=True)
        return

    target_id = int(callback.data.split(":")[1])
    await db_query("UPDATE users SET is_banned = 0, ban_until = NULL WHERE telegram_id = ?", (target_id,))

    await log_admin_action(admin_id, target_id, "unban", "1", "0")

    try:
        await bot.send_message(target_id, "✅ Ваш доступ к GiftEz Stars восстановлен.")
    except Exception:
        pass

    await callback.answer("✅ Пользователь разбанен!")
    await safe_edit_text(callback.message, f"✅ Пользователь <code>{target_id}</code> успешно разблокирован.",
                         parse_mode=ParseMode.HTML)


# --- ИЗМЕНЕНИЕ БАЛАНСА ---
@router.callback_query(F.data == "adm_balance_menu")
async def process_adm_balance_menu(callback: CallbackQuery, state: FSMContext):
    admin_id = callback.from_user.id
    if not await has_perm(admin_id, "edit_balance"):
        await callback.answer(get_str("no_permission", "ru"), show_alert=True)
        return

    await callback.answer()
    await state.set_state(AdminFSM.waiting_balance_user_id)
    await safe_edit_text(callback.message, "⭐ Введите Telegram ID пользователя для изменения баланса:")


@router.callback_query(F.data.startswith("adm_user_bal_edit:"))
async def process_adm_user_bal_edit(callback: CallbackQuery, state: FSMContext):
    admin_id = callback.from_user.id
    if not await has_perm(admin_id, "edit_balance"):
        await callback.answer(get_str("no_permission", "ru"), show_alert=True)
        return

    await callback.answer()
    target_id = int(callback.data.split(":")[1])
    await state.update_data(bal_target_id=target_id)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="➕ Выдать", callback_data="bal_action:add"),
            InlineKeyboardButton(text="➖ Списать", callback_data="bal_action:sub")
        ],
        [InlineKeyboardButton(text="🔙 Отмена", callback_data="admin_main")]
    ])
    await safe_edit_text(
        callback.message,
        f"⚙️ Выберите действие с балансом пользователя <code>{target_id}</code>:",
        reply_markup=kb,
        parse_mode=ParseMode.HTML
    )


@router.callback_query(F.data.startswith("bal_action:"))
async def process_bal_action_select(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    action_type = callback.data.split(":")[1]
    await state.update_data(bal_action=action_type)
    await state.set_state(AdminFSM.waiting_balance_amount)

    action_text = "начисления (выдачи)" if action_type == "add" else "списания"
    await safe_edit_text(
        callback.message,
        f"⭐ Введите сумму Звезд для {action_text}:",
        parse_mode=ParseMode.HTML
    )


@router.message(AdminFSM.waiting_balance_user_id)
async def process_bal_user_id_input(message: Message, state: FSMContext):
    try:
        target_id = int(message.text)
    except ValueError:
        await message.answer("❌ ID должен быть числом. Попробуйте еще раз:")
        return

    u = await get_user(target_id)
    if not u:
        await message.answer("❌ Пользователь с таким ID не найден в базе!")
        return

    await state.update_data(bal_target_id=target_id)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="➕ Выдать", callback_data="bal_action:add"),
            InlineKeyboardButton(text="➖ Списать", callback_data="bal_action:sub")
        ],
        [InlineKeyboardButton(text="🔙 Отмена", callback_data="admin_main")]
    ])
    await message.answer(
        f"⚙️ Выберите действие с балансом пользователя <code>{target_id}</code>:",
        reply_markup=kb,
        parse_mode=ParseMode.HTML
    )


@router.message(AdminFSM.waiting_balance_amount)
async def process_bal_amount_input(message: Message, state: FSMContext):
    try:
        amount = abs(float(message.text))
        if amount <= 0:
            raise ValueError()
    except ValueError:
        await message.answer("❌ Введите корректное положительное число (например: 10 или 5.5):")
        return

    data = await state.get_data()
    target_id = data.get("bal_target_id")
    action_type = data.get("bal_action", "add")
    admin_id = message.from_user.id

    u = await get_user(target_id)
    if not u:
        await message.answer("❌ Пользователь не найден.")
        await state.clear()
        return

    old_bal = u["balance"]
    delta = amount if action_type == "add" else -amount
    new_bal = await update_user_balance(target_id, delta)

    await log_admin_action(admin_id, target_id, "edit_balance", str(old_bal), str(new_bal))

    # Отправка уведомления пользователю
    try:
        if action_type == "add":
            notif = f"🎁 <b>Вам начислено +{amount:.3f} Stars!</b>\n⭐ Текущий баланс: {new_bal:.3f} Stars"
        else:
            notif = f"⚠️ <b>С вашего баланса списано -{amount:.3f} Stars.</b>\n⭐ Текущий баланс: {new_bal:.3f} Stars"
        await bot.send_message(target_id, notif, parse_mode=ParseMode.HTML)
    except Exception:
        pass

    action_label = "выдано" if action_type == "add" else "списано"
    await state.clear()
    await message.answer(
        f"✅ Успешно! Пользователю <code>{target_id}</code> {action_label} <b>{amount:.3f} Stars</b>.\n"
        f"⭐ Старый баланс: {old_bal:.3f} | Новый баланс: {new_bal:.3f}",
        parse_mode=ParseMode.HTML,
        reply_markup=await build_admin_main_kb(admin_id, "ru")
    )


# --- УПРАВЛЕНИЕ ШАНСАМИ СООБЩЕНИЙ ---
@router.callback_query(F.data == "adm_chances_menu")
async def process_adm_chances_menu(callback: CallbackQuery):
    admin_id = callback.from_user.id
    if not await has_perm(admin_id, "manage_chances"):
        await callback.answer(get_str("no_permission", "ru"), show_alert=True)
        return

    await callback.answer()
    ch_keys = [
        ("msg_reward_chance", "Общий шанс выпадения награды за сообщение"),
        ("rng_0.001_0.01", "Шанс диапазона 0.001 - 0.01"),
        ("rng_0.01_0.10", "Шанс диапазона 0.01 - 0.10"),
        ("rng_0.10_0.50", "Шанс диапазона 0.10 - 0.50"),
        ("rng_0.50_1.00", "Шанс диапазона 0.50 - 1.00"),
        ("rng_1.00_2.00", "Шанс диапазона 1.00 - 2.00"),
        ("rng_2.00_3.00", "Шанс диапазона 2.00 - 3.00"),
        ("rng_3.00_4.00", "Шанс диапазона 3.00 - 4.00"),
        ("rng_4.00_5.00", "Шанс диапазона 4.00 - 5.00"),
    ]

    text = "🎲 <b>Настройка шансов выпадения Звезд в чатах:</b>\n\n"
    kb = []
    for key, label in ch_keys:
        val = await get_setting(key, "0")
        text += f"🔹 {label}: <b>{val}%</b>\n"
        kb.append([InlineKeyboardButton(text=f"✏️ {label} ({val}%)", callback_data=f"adm_set_val:{key}")])

    kb.append([InlineKeyboardButton(text="🔙 Назад", callback_data="admin_main")])
    await safe_edit_text(callback.message, text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb),
                         parse_mode=ParseMode.HTML)


# --- УПРАВЛЕНИЕ БОНУСОМ ---
@router.callback_query(F.data == "adm_bonus_menu")
async def process_adm_bonus_menu(callback: CallbackQuery):
    admin_id = callback.from_user.id
    if not await has_perm(admin_id, "manage_bonus"):
        await callback.answer(get_str("no_permission", "ru"), show_alert=True)
        return

    await callback.answer()
    b_min = await get_setting("bonus_min", "0.01")
    b_max = await get_setting("bonus_max", "2.00")

    text = (
        f"🎁 <b>Настройки ежедневного бонуса:</b>\n\n"
        f"🔹 Минимальный бонус: <b>{b_min} Stars</b>\n"
        f"🔹 Максимальный бонус: <b>{b_max} Stars</b>"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"✏️ Мин. бонус ({b_min})", callback_data="adm_set_val:bonus_min")],
        [InlineKeyboardButton(text=f"✏️ Макс. бонус ({b_max})", callback_data="adm_set_val:bonus_max")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_main")]
    ])
    await safe_edit_text(callback.message, text, reply_markup=kb, parse_mode=ParseMode.HTML)


# --- МОДУЛИ ---
@router.callback_query(F.data == "adm_modules_menu")
async def process_adm_modules_menu(callback: CallbackQuery):
    admin_id = callback.from_user.id
    if not await has_perm(admin_id, "manage_modules"):
        await callback.answer(get_str("no_permission", "ru"), show_alert=True)
        return

    await callback.answer()
    mods = [
        ("mod_rewards", "Награды в чатах"),
        ("mod_withdraws", "Вывод средств"),
        ("mod_bonus", "Ежедневный бонус"),
        ("mod_sub_check", "Проверка подписки на канал"),
    ]

    text = "⚙️ <b>Переключение системных модулей:</b>\n\n"
    kb = []
    for key, label in mods:
        val = await get_setting(key, "1")
        st = "🟢 Вкл" if val == "1" else "🔴 Выкл"
        text += f"{label}: <b>{st}</b>\n"
        kb.append([InlineKeyboardButton(text=f"{st} - {label}", callback_data=f"adm_toggle_mod:{key}")])

    kb.append([InlineKeyboardButton(text="🔙 Назад", callback_data="admin_main")])
    await safe_edit_text(callback.message, text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb),
                         parse_mode=ParseMode.HTML)


@router.callback_query(F.data.startswith("adm_toggle_mod:"))
async def process_adm_toggle_mod(callback: CallbackQuery):
    admin_id = callback.from_user.id
    if not await has_perm(admin_id, "manage_modules"):
        await callback.answer(get_str("no_permission", "ru"), show_alert=True)
        return

    key = callback.data.split(":")[1]
    curr = await get_setting(key, "1")
    new_val = "0" if curr == "1" else "1"
    await set_setting(key, new_val)
    await log_admin_action(admin_id, 0, f"toggle_module_{key}", curr, new_val)

    await callback.answer("Состояние модуля изменено!")
    await process_adm_modules_menu(callback)


# --- УПРАВЛЕНИЕ АДМИНИСТРАТОРАМИ ---
@router.callback_query(F.data == "adm_admins_menu")
async def process_adm_admins_menu(callback: CallbackQuery):
    admin_id = callback.from_user.id
    if not await has_perm(admin_id, "manage_admins"):
        await callback.answer(get_str("no_permission", "ru"), show_alert=True)
        return

    await callback.answer()
    admins = await db_query("SELECT * FROM admins", fetchall=True) or []

    text = "👮 <b>Список Администраторов:</b>\n\n"
    kb = []
    for a in admins:
        u = await get_user(a["telegram_id"])
        name = html.escape(u["first_name"]) if u and u.get("first_name") else "Н/Д"
        text += f"🔹 <b>{name}</b> (<code>{a['telegram_id']}</code>)\n"
        kb.append([InlineKeyboardButton(text=f"⚙️ {name} ({a['telegram_id']})",
                                        callback_data=f"adm_admin_info:{a['telegram_id']}")])

    kb.append([InlineKeyboardButton(text="➕ Добавить администратора", callback_data="adm_add_admin")])
    kb.append([InlineKeyboardButton(text="🔙 Назад", callback_data="admin_main")])
    await safe_edit_text(callback.message, text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb),
                         parse_mode=ParseMode.HTML)


@router.callback_query(F.data.startswith("adm_admin_info:"))
async def process_adm_admin_info(callback: CallbackQuery):
    admin_id = callback.from_user.id
    if not await has_perm(admin_id, "manage_admins"):
        await callback.answer(get_str("no_permission", "ru"), show_alert=True)
        return

    target_id = int(callback.data.split(":")[1])
    await callback.answer()

    text = f"👮 <b>Управление правами админа <code>{target_id}</code>:</b>\n\n"
    kb = []

    for perm in ALL_PERMISSIONS:
        has_p = await has_perm(target_id, perm)
        st = "🟢" if has_p else "🔴"
        kb.append([InlineKeyboardButton(text=f"{st} {perm}", callback_data=f"adm_toggle_perm:{target_id}:{perm}")])

    if target_id != OWNER_ID:
        kb.append([InlineKeyboardButton(text="❌ Удалить админа", callback_data=f"adm_del_admin:{target_id}")])

    kb.append([InlineKeyboardButton(text="🔙 Назад", callback_data="adm_admins_menu")])
    await safe_edit_text(callback.message, text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb),
                         parse_mode=ParseMode.HTML)


@router.callback_query(F.data.startswith("adm_toggle_perm:"))
async def process_adm_toggle_perm(callback: CallbackQuery):
    admin_id = callback.from_user.id
    if not await has_perm(admin_id, "manage_admins"):
        await callback.answer(get_str("no_permission", "ru"), show_alert=True)
        return

    parts = callback.data.split(":")
    target_id = int(parts[1])
    perm = parts[2]

    res = await db_query("SELECT enabled FROM permissions WHERE admin_id = ? AND permission_name = ?",
                         (target_id, perm), fetchone=True)
    curr = res["enabled"] if res else 0
    new_val = 0 if curr == 1 else 1

    await db_query("INSERT OR REPLACE INTO permissions (admin_id, permission_name, enabled) VALUES (?, ?, ?)",
                   (target_id, perm, new_val))
    await callback.answer("Право изменено!")
    await process_adm_admin_info(callback)


@router.callback_query(F.data == "adm_add_admin")
async def process_adm_add_admin(callback: CallbackQuery, state: FSMContext):
    admin_id = callback.from_user.id
    if not await has_perm(admin_id, "manage_admins"):
        await callback.answer(get_str("no_permission", "ru"), show_alert=True)
        return

    await callback.answer()
    await state.set_state(AdminFSM.waiting_add_admin_id)
    await safe_edit_text(callback.message, "➕ Введите Telegram ID пользователя для назначения администратором:")


@router.message(AdminFSM.waiting_add_admin_id)
async def process_add_admin_id_input(message: Message, state: FSMContext):
    try:
        target_id = int(message.text)
    except ValueError:
        await message.answer("❌ ID должен быть числом:")
        return

    now_str = datetime.now().isoformat()
    await db_query("INSERT OR IGNORE INTO admins (telegram_id, created_at, added_by) VALUES (?, ?, ?)",
                   (target_id, now_str, message.from_user.id))

    await state.clear()
    await message.answer(f"✅ Пользователь <code>{target_id}</code> назначен администратором.",
                         reply_markup=await build_admin_main_kb(message.from_user.id, "ru"), parse_mode=ParseMode.HTML)


@router.callback_query(F.data.startswith("adm_del_admin:"))
async def process_adm_del_admin(callback: CallbackQuery):
    admin_id = callback.from_user.id
    if not await has_perm(admin_id, "manage_admins"):
        await callback.answer(get_str("no_permission", "ru"), show_alert=True)
        return

    target_id = int(callback.data.split(":")[1])
    if target_id == OWNER_ID:
        await callback.answer("❌ Нельзя удалить главного владельца!", show_alert=True)
        return

    await db_query("DELETE FROM admins WHERE telegram_id = ?", (target_id,))
    await db_query("DELETE FROM permissions WHERE admin_id = ?", (target_id,))
    await callback.answer("Администратор удален!")
    await process_adm_admins_menu(callback)


# --- НАСТРОЙКИ ---
@router.callback_query(F.data == "adm_settings_menu")
async def process_adm_settings_menu(callback: CallbackQuery):
    admin_id = callback.from_user.id
    if not await has_perm(admin_id, "manage_settings"):
        await callback.answer(get_str("no_permission", "ru"), show_alert=True)
        return

    await callback.answer()
    s_keys = [
        ("min_msg_len", "Мин. длина сообщения для награды"),
        ("antiflood_cooldown", "Задержка зачисления между сообщениями (сек)"),
        ("withdraw_cooldown", "Задержка повторного вывода (сек)"),
    ]

    text = "⚙️ <b>Системные Настройки:</b>\n\n"
    kb = []
    for key, label in s_keys:
        val = await get_setting(key, "0")
        text += f"🔹 {label}: <b>{val}</b>\n"
        kb.append([InlineKeyboardButton(text=f"✏️ {label} ({val})", callback_data=f"adm_set_val:{key}")])

    kb.append([InlineKeyboardButton(text="🔙 Назад", callback_data="admin_main")])
    await safe_edit_text(callback.message, text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb),
                         parse_mode=ParseMode.HTML)


# УНИВЕРСАЛЬНЫЙ СЕТТЕР ДЛЯ НАСТРОЕК
@router.callback_query(F.data.startswith("adm_set_val:"))
async def process_adm_set_val(callback: CallbackQuery, state: FSMContext):
    key = callback.data.split(":")[1]
    await callback.answer()
    await state.update_data(setting_key=key)
    await state.set_state(AdminFSM.waiting_setting_value)
    await safe_edit_text(callback.message, f"✏️ Введите новое значение для параметра <code>{key}</code>:")


@router.message(AdminFSM.waiting_setting_value)
async def process_setting_value_input(message: Message, state: FSMContext):
    data = await state.get_data()
    key = data.get("setting_key")
    val = message.text.strip()

    if key:
        await set_setting(key, val)
        await message.answer(f"✅ Параметр <code>{key}</code> успешно обновлен на: <b>{html.escape(val)}</b>",
                             parse_mode=ParseMode.HTML,
                             reply_markup=await build_admin_main_kb(message.from_user.id, "ru"))
    await state.clear()


# ==============================================================================
# ТОЧКА ВХОДА И ЗАПУСК
# ==============================================================================

async def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(name)s - %(message)s")
    logging.info("Инициализация базы данных...")
    await init_db()
    logging.info("Запуск GiftEz Stars Telegram Bot...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())