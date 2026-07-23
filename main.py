import asyncio
import logging
import os
import random
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union

import aiosqlite
from aiogram import Bot, Dispatcher, F, Router
from aiogram.enums import ChatMemberStatus, ChatType, ParseMode
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

# Загрузка переменных окружения из .env
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
        "btn_channel": "📢 Наш канал",
        "btn_admin": "⚙️ Админ-панель",
        "btn_withdraw": "⭐ Вывести Звезды",
        "btn_bonus": "🎁 Ежедневный бонус",
        "btn_change_lang": "🌐 Сменить язык",
        "btn_open_chat": "💬 Открыть чат",
        "main_menu_text": "🌟 **Главное меню GiftEz Stars**\n\nВыберите нужный раздел в меню ниже:",
        "profile_text": (
            "👤 **Имя:** {name}\n"
            "🆔 **ID:** `{user_id}`\n"
            "⭐ **Баланс:** {balance:.2f} {currency}\n"
            "📅 **Регистрация:** {reg_date}\n"
            "🌐 **Язык:** {lang_name}"
        ),
        "earn_text": (
            "💰 **Заработок Звезд**\n\n"
            "Общайтесь в наших подключенных группах и получайте Звезды за активность!\n"
            "Накапливайте баланс и обменивайте его на настоящие Telegram Stars."
        ),
        "no_groups": "К сожалению, пока нет доступных подключенных групп.",
        "select_group": "💬 Выберите группу для общения и заработка:",
        "bonus_cooldown": "⏳ Следующий ежедневный бонус будет доступен через:\n\n**{hours} ч. {minutes} мин.**",
        "bonus_received": "🎁 **Ежедневный бонус получен!**\n\nВам начислено: **+{amount:.2f} {currency}**",
        "bonus_disabled": "🎁 Ежедневный бонус временно отключен администрацией.",
        "withdraw_disabled": "⚠️ Выводы временно недоступны.",
        "withdraw_menu": "⭐ **Вывод Звезд**\n\nВыберите сумму для создания заявки на вывод:",
        "withdraw_insufficient": "❌ **Недостаточно Звезд**\n\nВаш баланс: {balance:.2f} {currency}\nНеобходимо: {required} {currency}",
        "withdraw_cooldown": "⏳ Новую заявку можно создать через:\n\n**{minutes} мин. {seconds} сек.**",
        "withdraw_created": "📤 **Заявка на вывод создана!**\n\nСумма: **{amount} {currency}**\nСтатус: 🟡 **Новая**\n\nАдминистрация проверит её в ближайшее время.",
        "withdraw_user_notif_ok": "✅ Ваша заявка на вывод #{withdraw_id} на сумму {amount} {currency} успешно выполнена!",
        "withdraw_user_notif_reject": "❌ Ваша заявка на вывод #{withdraw_id} на сумму {amount} {currency} была отклонена.\n\n**Причина:** {reason}",
        "withdraw_user_notif_hold": "🟠 Ваша заявка на вывод #{withdraw_id} на сумму {amount} {currency} временно отложена.",
        "sub_check_failed": "❌ Вы всё еще не подписаны на канал {channel}. Подпишитесь и попробуйте снова!",
        "banned_text": "🚫 **Вы заблокированы в боте.**\n\nПричина: {reason}",
        "group_not_subbed": "⚠️ {name}, для получения Звезд необходимо подписаться на канал {channel}!",
        "group_reward_msg": "🎉 {name}, вам начислено **+{amount:.2f}** {currency} за активность в чате!",
        "admin_only_add": "❌ Добавлять бота в группы могут только администраторы группы.",
        "group_connected": "✅ **GiftEz Stars успешно подключен!**\n\nТеперь пользователи могут получать Звезды за активность в этом чате.",
        "group_already_connected": "ℹ️ Эта группа уже подключена к системе.",
        # Админка
        "admin_menu_title": "⚙️ **Админ-панель Управления**",
        "admin_btn_users": "👥 Пользователи",
        "admin_btn_withdraws": "📤 Активные заявки",
        "admin_btn_history": "📚 История выводов",
        "admin_btn_broadcast": "📢 Рассылка",
        "admin_btn_ban": "🚫 Бан / Разбан",
        "admin_btn_balance": "⭐ Управление балансом",
        "admin_btn_chances": "🎲 Управление шансами",
        "admin_btn_bonus_cfg": "🎁 Ежедневный бонус",
        "admin_btn_modules": "⚙️ Модули",
        "admin_btn_admins": "👮 Администраторы",
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
        "btn_channel": "📢 Our Channel",
        "btn_admin": "⚙️ Admin Panel",
        "btn_withdraw": "⭐ Withdraw Stars",
        "btn_bonus": "🎁 Daily Bonus",
        "btn_change_lang": "🌐 Change Language",
        "btn_open_chat": "💬 Open Chat",
        "main_menu_text": "🌟 **GiftEz Stars Main Menu**\n\nSelect a section from the menu below:",
        "profile_text": (
            "👤 **Name:** {name}\n"
            "🆔 **ID:** `{user_id}`\n"
            "⭐ **Balance:** {balance:.2f} {currency}\n"
            "📅 **Registered:** {reg_date}\n"
            "🌐 **Language:** {lang_name}"
        ),
        "earn_text": (
            "💰 **Earn Stars**\n\n"
            "Chat in our connected groups and receive Stars for your activity!\n"
            "Accumulate balance and exchange it for real Telegram Stars."
        ),
        "no_groups": "Unfortunately, there are no connected groups available yet.",
        "select_group": "💬 Select a group to chat and earn:",
        "bonus_cooldown": "⏳ Next daily bonus will be available in:\n\n**{hours} h. {minutes} min.**",
        "bonus_received": "🎁 **Daily Bonus Claimed!**\n\nYou received: **+{amount:.2f} {currency}**",
        "bonus_disabled": "🎁 Daily bonus is temporarily disabled by administration.",
        "withdraw_disabled": "⚠️ Withdrawals are temporarily unavailable.",
        "withdraw_menu": "⭐ **Withdraw Stars**\n\nSelect amount to create a withdrawal request:",
        "withdraw_insufficient": "❌ **Not enough Stars**\n\nYour balance: {balance:.2f} {currency}\nRequired: {required} {currency}",
        "withdraw_cooldown": "⏳ You can create a new request in:\n\n**{minutes} min. {seconds} sec.**",
        "withdraw_created": "📤 **Withdrawal Request Created!**\n\nAmount: **{amount} {currency}**\nStatus: 🟡 **New**\n\nAdmins will review it shortly.",
        "withdraw_user_notif_ok": "✅ Your withdrawal request #{withdraw_id} for {amount} {currency} has been approved!",
        "withdraw_user_notif_reject": "❌ Your withdrawal request #{withdraw_id} for {amount} {currency} was rejected.\n\n**Reason:** {reason}",
        "withdraw_user_notif_hold": "🟠 Your withdrawal request #{withdraw_id} for {amount} {currency} is put on hold.",
        "sub_check_failed": "❌ You are still not subscribed to {channel}. Please subscribe and try again!",
        "banned_text": "🚫 **You are banned in the bot.**\n\nReason: {reason}",
        "group_not_subbed": "⚠️ {name}, you must subscribe to {channel} to earn Stars!",
        "group_reward_msg": "🎉 {name}, you received **+{amount:.2f}** {currency} for chat activity!",
        "admin_only_add": "❌ Only group administrators can add this bot.",
        "group_connected": "✅ **GiftEz Stars successfully connected!**\n\nUsers can now earn Stars for activity in this chat.",
        "group_already_connected": "ℹ️ This group is already connected.",
        # Admin
        "admin_menu_title": "⚙️ **Admin Control Panel**",
        "admin_btn_users": "👥 Users",
        "admin_btn_withdraws": "📤 Active Requests",
        "admin_btn_history": "📚 Withdrawal History",
        "admin_btn_broadcast": "📢 Broadcast",
        "admin_btn_ban": "🚫 Ban / Unban",
        "admin_btn_balance": "⭐ Manage Balance",
        "admin_btn_chances": "🎲 Chance Management",
        "admin_btn_bonus_cfg": "🎁 Daily Bonus Config",
        "admin_btn_modules": "⚙️ Modules",
        "admin_btn_admins": "👮 Administrators",
        "admin_btn_settings": "⚙️ Settings",
        "admin_btn_stats": "📊 Statistics",
        "no_permission": "❌ You do not have permission to perform this action.",
    },
}

ALL_PERMISSIONS = [
    "view_users", "edit_balance", "ban_users", "unban_users",
    "broadcast", "manage_chances", "manage_bonus", "manage_withdraws",
    "view_history", "view_active_withdraws", "manage_modules",
    "manage_settings", "view_stats", "manage_admins", "full_access"
]

def get_str(key: str, lang: str = "ru", **kwargs) -> str:
    lang_code = lang if lang in STRINGS else "ru"
    template = STRINGS[lang_code].get(key, STRINGS["ru"].get(key, key))
    return template.format(**kwargs)

# ==============================================================================
# БАЗА ДАННЫХ И МИГРАЦИИ
# ==============================================================================

async def init_db():
    async with aiosqlite.connect(DATABASE_PATH) as db:
        # Пользователи
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER UNIQUE,
                username TEXT,
                first_name TEXT,
                balance REAL DEFAULT 0.0,
                language TEXT DEFAULT 'ru',
                register_date TEXT,
                last_activity TEXT,
                last_bonus TEXT,
                is_banned INTEGER DEFAULT 0,
                ban_until TEXT
            )
        """)
        # Группы
        await db.execute("""
            CREATE TABLE IF NOT EXISTS groups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER UNIQUE,
                title TEXT,
                added_by INTEGER,
                created_at TEXT,
                status INTEGER DEFAULT 1
            )
        """)
        # Выводы
        await db.execute("""
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
        """)
        # Администраторы
        await db.execute("""
            CREATE TABLE IF NOT EXISTS admins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER UNIQUE,
                created_at TEXT,
                added_by INTEGER
            )
        """)
        # Права администраторов
        await db.execute("""
            CREATE TABLE IF NOT EXISTS permissions (
                admin_id INTEGER,
                permission_name TEXT,
                enabled INTEGER DEFAULT 1,
                PRIMARY KEY (admin_id, permission_name)
            )
        """)
        # Настройки и Модули
        await db.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        # История админ действий
        await db.execute("""
            CREATE TABLE IF NOT EXISTS history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                admin_id INTEGER,
                user_id INTEGER,
                action TEXT,
                old_value TEXT,
                new_value TEXT,
                created_at TEXT
            )
        """)
        # История бонусов
        await db.execute("""
            CREATE TABLE IF NOT EXISTS bonus_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                amount REAL,
                created_at TEXT
            )
        """)
        # История сообщений
        await db.execute("""
            CREATE TABLE IF NOT EXISTS messages_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                group_id INTEGER,
                created_at TEXT
            )
        """)

        # Значения по умолчанию для настроек и модулей
        default_settings = {
            # Модули (1 - вкл, 0 - выкл)
            "mod_rewards": "1",
            "mod_withdraws": "1",
            "mod_bonus": "1",
            "mod_sub_check": "1",
            "mod_groups": "1",
            "mod_broadcast": "1",
            # Настройки антифлуда и выводов
            "min_msg_len": "5",
            "antiflood_cooldown": "30",
            "withdraw_cooldown": "300", # в секундах (5 минут)
            "msg_reward_chance": "15", # процент 15%
            # Шансы для диапазонов сообщений (проценты)
            "rng_0.01_0.10": "70",
            "rng_0.10_0.50": "20",
            "rng_0.50_1.00": "7",
            "rng_1.00_2.00": "2",
            "rng_2.00_3.00": "0.8",
            "rng_3.00_4.00": "0.15",
            "rng_4.00_5.00": "0.05",
            # Ежедневный бонус
            "bonus_min": "0.01",
            "bonus_max": "2.00"
        }

        for k, v in default_settings.items():
            await db.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v))

        # Добавляем владельца в список админов
        now_str = datetime.now().isoformat()
        await db.execute("INSERT OR IGNORE INTO admins (telegram_id, created_at, added_by) VALUES (?, ?, ?)",
                         (OWNER_ID, now_str, OWNER_ID))
        for perm in ALL_PERMISSIONS:
            await db.execute("INSERT OR IGNORE INTO permissions (admin_id, permission_name, enabled) VALUES (?, ?, 1)",
                             (OWNER_ID, perm))

        await db.commit()

# Вспомогательные функции взаимодействия с БД

async def get_setting(key: str, default: str = "") -> str:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute("SELECT value FROM settings WHERE key = ?", (key,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else default

async def set_setting(key: str, value: str):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))
        await db.commit()

async def get_user(telegram_id: int) -> Optional[Dict[str, Any]]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

async def create_user(telegram_id: int, username: str, first_name: str) -> Dict[str, Any]:
    now = datetime.now().isoformat()
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("""
            INSERT INTO users (telegram_id, username, first_name, register_date, last_activity)
            VALUES (?, ?, ?, ?, ?)
        """, (telegram_id, username or "", first_name or "", now, now))
        await db.commit()
    return await get_user(telegram_id)

async def update_user_activity(telegram_id: int):
    now = datetime.now().isoformat()
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("UPDATE users SET last_activity = ? WHERE telegram_id = ?", (now, telegram_id))
        await db.commit()

async def update_user_balance(telegram_id: int, delta: float) -> float:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("UPDATE users SET balance = balance + ? WHERE telegram_id = ?", (delta, telegram_id))
        await db.commit()
        async with db.execute("SELECT balance FROM users WHERE telegram_id = ?", (telegram_id,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0.0

async def set_user_language(telegram_id: int, lang: str):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("UPDATE users SET language = ? WHERE telegram_id = ?", (lang, telegram_id))
        await db.commit()

async def is_admin(telegram_id: int) -> bool:
    if telegram_id == OWNER_ID:
        return True
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute("SELECT id FROM admins WHERE telegram_id = ?", (telegram_id,)) as cursor:
            row = await cursor.fetchone()
            return row is not None

async def has_perm(telegram_id: int, perm_name: str) -> bool:
    if telegram_id == OWNER_ID:
        return True
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute("""
            SELECT enabled FROM permissions 
            WHERE admin_id = ? AND permission_name = ?
        """, (telegram_id, perm_name)) as cursor:
            row = await cursor.fetchone()
            if row and row[0] == 1:
                return True
        # Проверка на полный доступ
        async with db.execute("""
            SELECT enabled FROM permissions 
            WHERE admin_id = ? AND permission_name = 'full_access'
        """, (telegram_id,)) as cursor:
            row = await cursor.fetchone()
            return row is not None and row[0] == 1

async def log_admin_action(admin_id: int, user_id: int, action: str, old_val: str, new_val: str):
    now = datetime.now().isoformat()
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("""
            INSERT INTO history (admin_id, user_id, action, old_value, new_value, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (admin_id, user_id, action, str(old_val), str(new_val), now))
        await db.commit()

# ==============================================================================
# ПРОВЕРКА ПОДПИСКИ И БАНА (MIDDLEWARE & HELPERS)
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
        logging.error(f" Ошибка проверки подписки пользователя {user_id}: {e}")
        return True

async def check_user_ban_status(user: Dict[str, Any]) -> bool:
    if not user.get("is_banned"):
        return False
    ban_until_str = user.get("ban_until")
    if ban_until_str:
        ban_until = datetime.fromisoformat(ban_until_str)
        if datetime.now() > ban_until:
            async with aiosqlite.connect(DATABASE_PATH) as db:
                await db.execute("UPDATE users SET is_banned = 0, ban_until = NULL WHERE telegram_id = ?", (user["telegram_id"],))
                await db.commit()
            return False
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
        [InlineKeyboardButton(text=get_str("btn_channel", lang), url=f"https://t.me/{CHANNEL_USERNAME.replace('@', '')}")]
    ]
    if await is_admin(telegram_id):
        kb.append([InlineKeyboardButton(text=get_str("btn_admin", lang), callback_data="admin_main")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

async def get_profile_keyboard(telegram_id: int, lang: str) -> InlineKeyboardMarkup:
    kb = [
        [InlineKeyboardButton(text=get_str("btn_withdraw", lang), callback_data="user_withdraw")],
        [InlineKeyboardButton(text=get_str("btn_bonus", lang), callback_data="user_bonus")],
        [InlineKeyboardButton(text=get_str("btn_change_lang", lang), callback_data="user_change_lang")],
        [InlineKeyboardButton(text=get_str("btn_back", lang), callback_data="menu_main")]
    ]
    if await is_admin(telegram_id):
        kb.insert(3, [InlineKeyboardButton(text=get_str("btn_admin", lang), callback_data="admin_main")])
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
# ОБРАБОТЧИКИ ПОЛЬЗОВАТЕЛЬСКОЙ ЧАСТИ
# ==============================================================================

@router.message(CommandStart(), F.chat.type == ChatType.PRIVATE)
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    user = await get_user(user_id)

    if not user:
        user = await create_user(user_id, message.from_user.username, message.from_user.first_name)
        await message.answer(
            get_str("select_lang", "ru"),
            reply_markup=get_lang_keyboard(),
            parse_mode=ParseMode.MARKDOWN
        )
        return

    await update_user_activity(user_id)

    if await check_user_ban_status(user):
        await message.answer(get_str("banned_text", user["language"], reason=user.get("ban_until") or "Нарушение правил"))
        return

    is_subbed = await check_channel_subscription(user_id)
    if not is_subbed:
        await message.answer(
            get_str("sub_required", user["language"], channel=CHANNEL_USERNAME),
            reply_markup=get_sub_keyboard(user["language"]),
            parse_mode=ParseMode.MARKDOWN
        )
        return

    await message.answer(
        get_str("main_menu_text", user["language"]),
        reply_markup=await get_main_menu_keyboard(user_id, user["language"]),
        parse_mode=ParseMode.MARKDOWN
    )

@router.callback_query(F.data.startswith("set_lang:"))
async def process_set_language(callback: CallbackQuery):
    await callback.answer()
    lang = callback.data.split(":")[1]
    user_id = callback.from_user.id
    await set_user_language(user_id, lang)

    is_subbed = await check_channel_subscription(user_id)
    if not is_subbed:
        await callback.message.edit_text(
            get_str("sub_required", lang, channel=CHANNEL_USERNAME),
            reply_markup=get_sub_keyboard(lang),
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        await callback.message.edit_text(
            get_str("main_menu_text", lang),
            reply_markup=await get_main_menu_keyboard(user_id, lang),
            parse_mode=ParseMode.MARKDOWN
        )

@router.callback_query(F.data == "check_subscription")
async def process_check_subscription(callback: CallbackQuery):
    user_id = callback.from_user.id
    user = await get_user(user_id)
    lang = user["language"] if user else "ru"

    is_subbed = await check_channel_subscription(user_id)
    if is_subbed:
        await callback.answer("✅ Подписка подтверждена!")
        await callback.message.edit_text(
            get_str("main_menu_text", lang),
            reply_markup=await get_main_menu_keyboard(user_id, lang),
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        await callback.answer(get_str("sub_check_failed", lang, channel=CHANNEL_USERNAME), show_alert=True)

@router.callback_query(F.data == "menu_main")
async def process_menu_main(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.answer()
    user_id = callback.from_user.id
    user = await get_user(user_id)
    lang = user["language"]

    await callback.message.edit_text(
        get_str("main_menu_text", lang),
        reply_markup=await get_main_menu_keyboard(user_id, lang),
        parse_mode=ParseMode.MARKDOWN
    )

@router.callback_query(F.data == "menu_profile")
async def process_menu_profile(callback: CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    user = await get_user(user_id)
    lang = user["language"]

    reg_date = user["register_date"].split("T")[0] if "T" in user["register_date"] else user["register_date"]
    lang_name = "Русский 🇷🇺" if lang == "ru" else "English 🇬🇧"
    currency = get_str("currency", lang)

    text = get_str(
        "profile_text",
        lang,
        name=user["first_name"],
        user_id=user["telegram_id"],
        balance=user["balance"],
        currency=currency,
        reg_date=reg_date,
        lang_name=lang_name
    )

    await callback.message.edit_text(
        text,
        reply_markup=await get_profile_keyboard(user_id, lang),
        parse_mode=ParseMode.MARKDOWN
    )

@router.callback_query(F.data == "user_change_lang")
async def process_user_change_lang(callback: CallbackQuery):
    await callback.answer()
    await callback.message.edit_text(
        get_str("select_lang", "ru"),
        reply_markup=get_lang_keyboard(),
        parse_mode=ParseMode.MARKDOWN
    )

@router.callback_query(F.data == "menu_earn")
async def process_menu_earn(callback: CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    user = await get_user(user_id)
    lang = user["language"]

    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM groups WHERE status = 1") as cursor:
            groups = await cursor.fetchall()

    kb = []
    if groups:
        for g in groups:
            kb.append([InlineKeyboardButton(text=f"💬 {g['title']}", url=f"https://t.me/{CHANNEL_USERNAME.replace('@', '')}")])
    kb.append([InlineKeyboardButton(text=get_str("btn_channel", lang), url=f"https://t.me/{CHANNEL_USERNAME.replace('@', '')}")])
    kb.append([InlineKeyboardButton(text=get_str("btn_back", lang), callback_data="menu_main")])

    text = get_str("earn_text", lang)
    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb),
        parse_mode=ParseMode.MARKDOWN
    )

# ==============================================================================
# ЕЖЕДНЕВНЫЙ БОНУС
# ==============================================================================

@router.callback_query(F.data == "user_bonus")
async def process_user_bonus(callback: CallbackQuery):
    user_id = callback.from_user.id
    user = await get_user(user_id)
    lang = user["language"]
    currency = get_str("currency", lang)

    mod_bonus = await get_setting("mod_bonus", "1")
    if mod_bonus == "0":
        await callback.answer(get_str("bonus_disabled", lang), show_alert=True)
        return

    last_bonus_str = user.get("last_bonus")
    now = datetime.now()

    if last_bonus_str:
        last_bonus_time = datetime.fromisoformat(last_bonus_str)
        next_bonus_time = last_bonus_time + timedelta(hours=24)
        if now < next_bonus_time:
            await callback.answer()
            diff = next_bonus_time - now
            hours, remainder = divmod(int(diff.total_seconds()), 3600)
            minutes, _ = divmod(remainder, 60)
            text = get_str("bonus_cooldown", lang, hours=hours, minutes=minutes)
            kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=get_str("btn_back", lang), callback_data="menu_profile")]])
            await callback.message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)
            return

    await callback.answer()
    b_min = float(await get_setting("bonus_min", "0.01"))
    b_max = float(await get_setting("bonus_max", "2.00"))
    reward = round(random.uniform(b_min, b_max), 2)

    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("UPDATE users SET balance = balance + ?, last_bonus = ? WHERE telegram_id = ?",
                         (reward, now.isoformat(), user_id))
        await db.execute("INSERT INTO bonus_history (user_id, amount, created_at) VALUES (?, ?, ?)",
                         (user_id, reward, now.isoformat()))
        await db.commit()

    text = get_str("bonus_received", lang, amount=reward, currency=currency)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=get_str("btn_back", lang), callback_data="menu_profile")]])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)

# ==============================================================================
# ВЫВОД ЗВЕЗД
# ==============================================================================

@router.callback_query(F.data == "user_withdraw")
async def process_user_withdraw_menu(callback: CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    user = await get_user(user_id)
    lang = user["language"]

    await callback.message.edit_text(
        get_str("withdraw_menu", lang),
        reply_markup=get_withdraw_amounts_keyboard(lang),
        parse_mode=ParseMode.MARKDOWN
    )

@router.callback_query(F.data.startswith("withdraw_req:"))
async def process_create_withdraw(callback: CallbackQuery):
    amount = float(callback.data.split(":")[1])
    user_id = callback.from_user.id
    user = await get_user(user_id)
    lang = user["language"]
    currency = get_str("currency", lang)

    if await get_setting("mod_withdraws", "1") == "0":
        await callback.answer(get_str("withdraw_disabled", lang), show_alert=True)
        return

    if user["balance"] < amount:
        await callback.answer()
        text = get_str("withdraw_insufficient", lang, balance=user["balance"], currency=currency, required=amount)
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=get_str("btn_back", lang), callback_data="user_withdraw")]])
        await callback.message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)
        return

    cooldown_sec = int(await get_setting("withdraw_cooldown", "300"))
    now = datetime.now()

    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute(
            "SELECT created_at FROM withdraws WHERE user_id = ? ORDER BY id DESC LIMIT 1", (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                last_req_time = datetime.fromisoformat(row[0])
                if now - last_req_time < timedelta(seconds=cooldown_sec):
                    await callback.answer()
                    remaining = timedelta(seconds=cooldown_sec) - (now - last_req_time)
                    mins, secs = divmod(int(remaining.total_seconds()), 60)
                    text = get_str("withdraw_cooldown", lang, minutes=mins, seconds=secs)
                    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=get_str("btn_back", lang), callback_data="user_withdraw")]])
                    await callback.message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)
                    return

        await db.execute("UPDATE users SET balance = balance - ? WHERE telegram_id = ?", (amount, user_id))
        now_str = now.isoformat()
        cursor = await db.execute("""
            INSERT INTO withdraws (user_id, amount, status, created_at, updated_at)
            VALUES (?, ?, 'new', ?, ?)
        """, (user_id, amount, now_str, now_str))
        withdraw_id = cursor.lastrowid
        await db.commit()

    await callback.answer()
    text = get_str("withdraw_created", lang, amount=amount, currency=currency)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=get_str("btn_back", lang), callback_data="menu_profile")]])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)

    admin_text = (
        f"📤 **Новая заявка на вывод #{withdraw_id}**\n\n"
        f"👤 **Пользователь:** {user['first_name']}\n"
        f"📛 **Username:** @{user['username']}\n"
        f"🆔 **ID:** `{user['telegram_id']}`\n"
        f"⭐ **Сумма:** {amount} {currency}\n"
        f"📅 **Дата:** {now_str.split('T')[0]}"
    )
    admin_kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Выполнить", callback_data=f"adm_wd_approve:{withdraw_id}"),
            InlineKeyboardButton(text="🟠 Отложить", callback_data=f"adm_wd_hold:{withdraw_id}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"adm_wd_reject:{withdraw_id}")
        ]
    ])

    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute("SELECT telegram_id FROM admins") as cursor:
            admins = await cursor.fetchall()
            for adm in admins:
                if await has_perm(adm[0], "manage_withdraws"):
                    try:
                        await bot.send_message(adm[0], admin_text, reply_markup=admin_kb, parse_mode=ParseMode.MARKDOWN)
                    except Exception:
                        pass

# ==============================================================================
# НАГРАДЫ ЗА СООБЩЕНИЯ В ГРУППАХ (ИСПРАВЛЕНО!)
# ==============================================================================

@router.message(F.chat.type.in_([ChatType.GROUP, ChatType.SUPERGROUP]))
async def handle_group_message(message: Message):
    if not message.from_user or message.from_user.is_bot:
        return

    chat_id = message.chat.id
    user_id = message.from_user.id
    now = datetime.now()

    # Проверка подключения группы в базе
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute("SELECT status FROM groups WHERE chat_id = ?", (chat_id,)) as cursor:
            group = await cursor.fetchone()
            if not group or group[0] == 0:
                return

    # Проверка активен ли модуль наград
    if await get_setting("mod_rewards", "1") == "0":
        return

    # Проверка минимальной длины сообщения
    min_len = int(await get_setting("min_msg_len", "5"))
    if not message.text or len(message.text) < min_len:
        return

    user = await get_user(user_id)
    if not user:
        user = await create_user(user_id, message.from_user.username, message.from_user.first_name)

    if await check_user_ban_status(user):
        return

    # Антифлуд задержка
    cooldown_sec = int(await get_setting("antiflood_cooldown", "30"))
    if user_id in user_last_reward_time:
        if now - user_last_reward_time[user_id] < timedelta(seconds=cooldown_sec):
            return

    # Проверка подписки на канал
    is_subbed = await check_channel_subscription(user_id)
    if not is_subbed:
        if user_id not in user_last_msg_time or (now - user_last_msg_time[user_id] > timedelta(minutes=5)):
            user_last_msg_time[user_id] = now
            name_link = f"[{message.from_user.first_name}](tg://user?id={user_id})"
            text = get_str("group_not_subbed", user["language"], name=name_link, channel=CHANNEL_USERNAME)
            await message.reply(text, parse_mode=ParseMode.MARKDOWN)
        return

    # Проверка вероятности (шанса)
    chance = float(await get_setting("msg_reward_chance", "15"))
    if chance <= 0.0:
        return
    if chance < 100.0:
        roll = random.uniform(0.0, 100.0)
        if roll > chance:
            return

    # Выбор диапазона наград по их точному процентному весу
    ranges = [
        (0.01, 0.10, float(await get_setting("rng_0.01_0.10", "70"))),
        (0.10, 0.50, float(await get_setting("rng_0.10_0.50", "20"))),
        (0.50, 1.00, float(await get_setting("rng_0.50_1.00", "7"))),
        (1.00, 2.00, float(await get_setting("rng_1.00_2.00", "2"))),
        (2.00, 3.00, float(await get_setting("rng_2.00_3.00", "0.8"))),
        (3.00, 4.00, float(await get_setting("rng_3.00_4.00", "0.15"))),
        (4.00, 5.00, float(await get_setting("rng_4.00_5.00", "0.05"))),
    ]

    total_weight = sum(r[2] for r in ranges)
    if total_weight <= 0:
        selected_range = ranges[0]
    else:
        rng_roll = random.uniform(0.0, total_weight)
        cumulative = 0.0
        selected_range = ranges[0]
        for r in ranges:
            cumulative += r[2]
            if rng_roll <= cumulative:
                selected_range = r
                break

    reward = round(random.uniform(selected_range[0], selected_range[1]), 2)

    await update_user_balance(user_id, reward)
    user_last_reward_time[user_id] = now

    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("INSERT INTO messages_history (user_id, group_id, created_at) VALUES (?, ?, ?)",
                         (user_id, chat_id, now.isoformat()))
        await db.commit()

    currency = get_str("currency", user["language"])
    name_link = f"[{message.from_user.first_name}](tg://user?id={user_id})"
    text = get_str("group_reward_msg", user["language"], name=name_link, amount=reward, currency=currency)
    await message.reply(text, parse_mode=ParseMode.MARKDOWN)

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
        async with aiosqlite.connect(DATABASE_PATH) as db:
            async with db.execute("SELECT id FROM groups WHERE chat_id = ?", (chat_id,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    await bot.send_message(chat_id, get_str("group_already_connected", "ru"))
                    return

            await db.execute("""
                INSERT INTO groups (chat_id, title, added_by, created_at, status)
                VALUES (?, ?, ?, ?, 1)
            """, (chat_id, title, added_by_user.id, now_str))
            await db.commit()

        await bot.send_message(chat_id, get_str("group_connected", "ru"), parse_mode=ParseMode.MARKDOWN)

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
    if await has_perm(admin_id, "manage_bonus"):
        r4.append(InlineKeyboardButton(text=get_str("admin_btn_bonus_cfg", lang), callback_data="adm_bonus_menu"))
    if r4: kb.append(r4)

    r5 = []
    if await has_perm(admin_id, "manage_modules"):
        r5.append(InlineKeyboardButton(text=get_str("admin_btn_modules", lang), callback_data="adm_modules_menu"))
    if await has_perm(admin_id, "manage_admins"):
        r5.append(InlineKeyboardButton(text=get_str("admin_btn_admins", lang), callback_data="adm_admins_menu"))
    if r5: kb.append(r5)

    r6 = []
    if await has_perm(admin_id, "manage_settings"):
        r6.append(InlineKeyboardButton(text=get_str("admin_btn_settings", lang), callback_data="adm_settings_menu"))
    if await has_perm(admin_id, "view_stats"):
        r6.append(InlineKeyboardButton(text=get_str("admin_btn_stats", lang), callback_data="adm_stats"))
    if r6: kb.append(r6)

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
    lang = user["language"]

    await callback.message.edit_text(
        get_str("admin_menu_title", lang),
        reply_markup=await build_admin_main_kb(user_id, lang),
        parse_mode=ParseMode.MARKDOWN
    )

# --- СТАТИСТИКА ---
@router.callback_query(F.data == "adm_stats")
async def process_adm_stats(callback: CallbackQuery):
    user_id = callback.from_user.id
    if not await has_perm(user_id, "view_stats"):
        await callback.answer(get_str("no_permission", "ru"), show_alert=True)
        return

    await callback.answer()
    user = await get_user(user_id)
    lang = user["language"]

    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM users") as c: total_users = (await c.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM messages_history") as c: total_msgs = (await c.fetchone())[0]
        async with db.execute("SELECT SUM(balance) FROM users") as c: total_stars = (await c.fetchone())[0] or 0.0
        async with db.execute("SELECT COUNT(*) FROM bonus_history") as c: total_bonuses = (await c.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM withdraws") as c: total_wd = (await c.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM withdraws WHERE status = 'approved'") as c: ok_wd = (await c.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM withdraws WHERE status = 'rejected'") as c: err_wd = (await c.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM withdraws WHERE status = 'hold'") as c: hold_wd = (await c.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM users WHERE is_banned = 1") as c: banned_users = (await c.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM admins") as c: total_admins = (await c.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM groups WHERE status = 1") as c: total_groups = (await c.fetchone())[0]

    text = (
        f"📊 **Системная Статистика**\n\n"
        f"👥 **Всего пользователей:** {total_users}\n"
        f"💬 **Обработано сообщений:** {total_msgs}\n"
        f"⭐ **Всего Звезд на балансах:** {total_stars:.2f}\n"
        f"🎁 **Выдано ежедневных бонусов:** {total_bonuses}\n"
        f"📤 **Всего заявок на вывод:** {total_wd}\n"
        f"  └ 🟢 Выполнено: {ok_wd}\n"
        f"  └ 🔴 Отклонено: {err_wd}\n"
        f"  └ 🟠 Отложено: {hold_wd}\n"
        f"🚫 **Заблокировано пользователей:** {banned_users}\n"
        f"👮 **Администраторов:** {total_admins}\n"
        f"🏠 **Подключенных групп:** {total_groups}"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=get_str("btn_back", lang), callback_data="admin_main")]])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)

# --- СПИСОК ПОЛЬЗОВАТЕЛЕЙ (С ПАГИНАЦИЕЙ) ---
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
    lang = user["language"]

    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT COUNT(*) FROM users") as c:
            total_count = (await c.fetchone())[0]

        async with db.execute("SELECT * FROM users ORDER BY id DESC LIMIT ? OFFSET ?", (limit, offset)) as cursor:
            users_list = await cursor.fetchall()

    text = f"👥 **Список пользователей (Страница {page})**\n\n"
    kb = []
    for u in users_list:
        text += f"👤 **{u['first_name']}** | @{u['username']} | `{u['telegram_id']}` | ⭐ {u['balance']:.2f}\n"
        kb.append([InlineKeyboardButton(text=f"👤 {u['first_name']} ({u['telegram_id']})", callback_data=f"adm_user_info:{u['telegram_id']}")])

    nav = []
    if page > 1:
        nav.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"adm_users_page:{page-1}"))
    if offset + limit < total_count:
        nav.append(InlineKeyboardButton(text="➡️ Вперед", callback_data=f"adm_users_page:{page+1}"))
    if nav:
        kb.append(nav)

    kb.append([InlineKeyboardButton(text=get_str("btn_back", lang), callback_data="admin_main")])
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb), parse_mode=ParseMode.MARKDOWN)

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
    lang = admin["language"]

    status = "🚫 Заблокирован" if u["is_banned"] else "✅ Активен"
    text = (
        f"👤 **Информация о пользователе**\n\n"
        f"👤 **Имя:** {u['first_name']}\n"
        f"📛 **Username:** @{u['username']}\n"
        f"🆔 **ID:** `{u['telegram_id']}`\n"
        f"⭐ **Баланс:** {u['balance']:.2f}\n"
        f"📅 **Регистрация:** {u['register_date']}\n"
        f"🌐 **Язык:** {u['language']}\n"
        f"📌 **Статус:** {status}\n"
        f"⏱ **Активность:** {u['last_activity']}"
    )

    kb = []
    if await has_perm(admin_id, "edit_balance"):
        kb.append([
            InlineKeyboardButton(text="⭐ Выдать/Списать", callback_data=f"adm_user_bal_edit:{u['telegram_id']}")
        ])
    if await has_perm(admin_id, "ban_users") and not u["is_banned"]:
        kb.append([InlineKeyboardButton(text="🚫 Забанить", callback_data=f"adm_user_ban_act:{u['telegram_id']}")])
    if await has_perm(admin_id, "unban_users") and u["is_banned"]:
        kb.append([InlineKeyboardButton(text="✅ Разбанить", callback_data=f"adm_user_unban_act:{u['telegram_id']}")])

    kb.append([InlineKeyboardButton(text=get_str("btn_back", lang), callback_data="adm_users_page:1")])
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb), parse_mode=ParseMode.MARKDOWN)

# --- ВЫВОДЫ ЗАЯВКИ ---
@router.callback_query(F.data.startswith("adm_withdraws_act:"))
async def process_adm_withdraws_active(callback: CallbackQuery):
    admin_id = callback.from_user.id
    if not await has_perm(admin_id, "view_active_withdraws"):
        await callback.answer(get_str("no_permission", "ru"), show_alert=True)
        return

    await callback.answer()
    admin = await get_user(admin_id)
    lang = admin["language"]

    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM withdraws WHERE status IN ('new', 'hold') ORDER BY id DESC") as cursor:
            items = await cursor.fetchall()

    if not items:
        text = "📤 **Активных заявок на вывод нет.**"
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=get_str("btn_back", lang), callback_data="admin_main")]])
        await callback.message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)
        return

    text = "📤 **Список активных заявок:**\n\n"
    kb = []
    for item in items:
        u = await get_user(item["user_id"])
        uname = f"@{u['username']}" if u else "Н/Д"
        st = "🟡 Новая" if item["status"] == "new" else "🟠 Отложена"
        text += f"Заявка #{item['id']} | {uname} | ⭐ {item['amount']} | {st}\n"
        kb.append([InlineKeyboardButton(text=f"Управление #{item['id']} ({item['amount']} ⭐)", callback_data=f"adm_wd_manage:{item['id']}")])

    kb.append([InlineKeyboardButton(text=get_str("btn_back", lang), callback_data="admin_main")])
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb), parse_mode=ParseMode.MARKDOWN)

@router.callback_query(F.data.startswith("adm_wd_manage:"))
async def process_adm_wd_manage(callback: CallbackQuery):
    await callback.answer()
    wd_id = int(callback.data.split(":")[1])
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM withdraws WHERE id = ?", (wd_id,)) as cursor:
            wd = await cursor.fetchone()

    u = await get_user(wd["user_id"])
    text = (
        f"📤 **Управление заявкой #{wd['id']}**\n\n"
        f"👤 **Имя:** {u['first_name'] if u else 'Н/Д'}\n"
        f"📛 **Username:** @{u['username'] if u else 'Н/Д'}\n"
        f"🆔 **ID:** `{wd['user_id']}`\n"
        f"⭐ **Сумма:** {wd['amount']}\n"
        f"📅 **Дата:** {wd['created_at']}\n"
        f"📌 **Статус:** {wd['status']}"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Выполнить", callback_data=f"adm_wd_approve:{wd['id']}"),
            InlineKeyboardButton(text="🟠 Отложить", callback_data=f"adm_wd_hold:{wd['id']}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"adm_wd_reject:{wd['id']}")
        ],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="adm_withdraws_act:1")]
    ])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)

@router.callback_query(F.data.startswith("adm_wd_approve:"))
async def process_adm_wd_approve(callback: CallbackQuery):
    admin_id = callback.from_user.id
    if not await has_perm(admin_id, "manage_withdraws"):
        await callback.answer(get_str("no_permission", "ru"), show_alert=True)
        return

    wd_id = int(callback.data.split(":")[1])
    now_str = datetime.now().isoformat()

    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM withdraws WHERE id = ?", (wd_id,)) as cursor:
            wd = await cursor.fetchone()
        await db.execute("""
            UPDATE withdraws SET status = 'approved', updated_at = ?, admin_id = ? WHERE id = ?
        """, (now_str, admin_id, wd_id))
        await db.commit()

    await log_admin_action(admin_id, wd["user_id"], "approve_withdraw", wd["status"], "approved")

    u = await get_user(wd["user_id"])
    if u:
        try:
            msg = get_str("withdraw_user_notif_ok", u["language"], withdraw_id=wd_id, amount=wd["amount"], currency=get_str("currency", u["language"]))
            await bot.send_message(u["telegram_id"], msg, parse_mode=ParseMode.MARKDOWN)
        except Exception:
            pass

    await callback.answer("✅ Заявка помечена как выполненная!")
    await callback.message.edit_text(f"✅ Заявка #{wd_id} успешно выполнена.")

@router.callback_query(F.data.startswith("adm_wd_hold:"))
async def process_adm_wd_hold(callback: CallbackQuery):
    admin_id = callback.from_user.id
    if not await has_perm(admin_id, "manage_withdraws"):
        await callback.answer(get_str("no_permission", "ru"), show_alert=True)
        return

    wd_id = int(callback.data.split(":")[1])
    now_str = datetime.now().isoformat()

    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM withdraws WHERE id = ?", (wd_id,)) as cursor:
            wd = await cursor.fetchone()
        await db.execute("""
            UPDATE withdraws SET status = 'hold', updated_at = ?, admin_id = ? WHERE id = ?
        """, (now_str, admin_id, wd_id))
        await db.commit()

    await log_admin_action(admin_id, wd["user_id"], "hold_withdraw", wd["status"], "hold")

    u = await get_user(wd["user_id"])
    if u:
        try:
            msg = get_str("withdraw_user_notif_hold", u["language"], withdraw_id=wd_id, amount=wd["amount"], currency=get_str("currency", u["language"]))
            await bot.send_message(u["telegram_id"], msg, parse_mode=ParseMode.MARKDOWN)
        except Exception:
            pass

    await callback.answer("🟠 Заявка временно отложена.")
    await callback.message.edit_text(f"🟠 Заявка #{wd_id} отложена.")

@router.callback_query(F.data.startswith("adm_wd_reject:"))
async def process_adm_wd_reject(callback: CallbackQuery, state: FSMContext):
    admin_id = callback.from_user.id
    if not await has_perm(admin_id, "manage_withdraws"):
        await callback.answer(get_str("no_permission", "ru"), show_alert=True)
        return

    await callback.answer()
    wd_id = int(callback.data.split(":")[1])
    await state.update_data(reject_wd_id=wd_id)
    await state.set_state(AdminFSM.waiting_reject_reason)

    await callback.message.edit_text("❌ Введите причину отказа для пользователя:")

@router.message(AdminFSM.waiting_reject_reason)
async def process_reject_reason_input(message: Message, state: FSMContext):
    admin_id = message.from_user.id
    data = await state.get_data()
    wd_id = data["reject_wd_id"]
    reason = message.text
    now_str = datetime.now().isoformat()

    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM withdraws WHERE id = ?", (wd_id,)) as cursor:
            wd = await cursor.fetchone()

        await db.execute("UPDATE users SET balance = balance + ? WHERE telegram_id = ?", (wd["amount"], wd["user_id"]))
        await db.execute("""
            UPDATE withdraws SET status = 'rejected', reject_reason = ?, updated_at = ?, admin_id = ? WHERE id = ?
        """, (reason, now_str, admin_id, wd_id))
        await db.commit()

    await log_admin_action(admin_id, wd["user_id"], "reject_withdraw", wd["status"], f"rejected ({reason})")

    u = await get_user(wd["user_id"])
    if u:
        try:
            msg = get_str("withdraw_user_notif_reject", u["language"], withdraw_id=wd_id, amount=wd["amount"], currency=get_str("currency", u["language"]), reason=reason)
            await bot.send_message(u["telegram_id"], msg, parse_mode=ParseMode.MARKDOWN)
        except Exception:
            pass

    await state.clear()
    await message.answer(f"❌ Заявка #{wd_id} отклонена. Средства вернулись на баланс пользователя.", reply_markup=await build_admin_main_kb(admin_id, "ru"))

# --- ИСТОРИЯ ВЫВОДОВ ---
@router.callback_query(F.data.startswith("adm_withdraws_hist:"))
async def process_adm_withdraws_history(callback: CallbackQuery):
    admin_id = callback.from_user.id
    if not await has_perm(admin_id, "view_history"):
        await callback.answer(get_str("no_permission", "ru"), show_alert=True)
        return

    await callback.answer()
    admin = await get_user(admin_id)
    lang = admin["language"]

    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM withdraws ORDER BY id DESC LIMIT 20") as cursor:
            items = await cursor.fetchall()

    text = "📚 **История выводов (Последние 20):**\n\n"
    for item in items:
        text += f"#{item['id']} | User: `{item['user_id']}` | ⭐ {item['amount']} | Статус: {item['status']} | {item['created_at'].split('T')[0]}\n"

    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=get_str("btn_back", lang), callback_data="admin_main")]])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)

# --- РАССЫЛКА ---
@router.callback_query(F.data == "adm_broadcast")
async def process_adm_broadcast(callback: CallbackQuery, state: FSMContext):
    admin_id = callback.from_user.id
    if not await has_perm(admin_id, "broadcast"):
        await callback.answer(get_str("no_permission", "ru"), show_alert=True)
        return

    await callback.answer()
    await state.set_state(AdminFSM.waiting_broadcast_msg)
    await callback.message.edit_text("📢 Отправьте сообщение для рассылки (поддерживается HTML/Markdown разметка):")

@router.message(AdminFSM.waiting_broadcast_msg)
async def process_broadcast_msg_input(message: Message, state: FSMContext):
    await state.update_data(broadcast_msg_id=message.message_id, broadcast_chat_id=message.chat.id)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Отправить", callback_data="adm_broadcast_confirm")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_main")]
    ])
    await message.answer("📢 **Предпросмотр рассылки.** Вы уверены, что хотите отправить это сообщение всем пользователям?", reply_markup=kb)

@router.callback_query(F.data == "adm_broadcast_confirm")
async def process_adm_broadcast_confirm(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    msg_id = data["broadcast_msg_id"]
    from_chat_id = data["broadcast_chat_id"]
    await state.clear()

    await callback.message.edit_text("⏳ Рассылка запущена...")

    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute("SELECT telegram_id FROM users WHERE is_banned = 0") as cursor:
            users = await cursor.fetchall()

    success = 0
    errors = 0

    for u in users:
        try:
            await bot.copy_message(chat_id=u[0], from_chat_id=from_chat_id, message_id=msg_id)
            success += 1
            await asyncio.sleep(0.05)
        except Exception:
            errors += 1

    text = f"📢 **Рассылка завершена.**\n\n✅ Успешно отправлено: {success}\n❌ Ошибок доставки: {errors}"
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 В админку", callback_data="admin_main")]])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)

# --- БАН И РАЗБАН ---
@router.callback_query(F.data == "adm_ban_menu")
async def process_adm_ban_menu(callback: CallbackQuery, state: FSMContext):
    admin_id = callback.from_user.id
    if not await has_perm(admin_id, "ban_users"):
        await callback.answer(get_str("no_permission", "ru"), show_alert=True)
        return

    await callback.answer()
    await state.set_state(AdminFSM.waiting_ban_user_id)
    await callback.message.edit_text("🚫 Введите Telegram ID пользователя для блокировки:")

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
    reason = message.text
    admin_id = message.from_user.id

    ban_until_str = None
    if minutes > 0:
        ban_until_str = (datetime.now() + timedelta(minutes=minutes)).isoformat()

    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("UPDATE users SET is_banned = 1, ban_until = ? WHERE telegram_id = ?", (ban_until_str, target_id))
        await db.commit()

    await log_admin_action(admin_id, target_id, "ban", "0", f"banned until {ban_until_str} ({reason})")

    try:
        await bot.send_message(target_id, get_str("banned_text", "ru", reason=reason))
    except Exception:
        pass

    await state.clear()
    await message.answer(f"🚫 Пользователь `{target_id}` успешно заблокирован.", parse_mode=ParseMode.MARKDOWN, reply_markup=await build_admin_main_kb(admin_id, "ru"))

@router.callback_query(F.data.startswith("adm_user_unban_act:"))
async def process_adm_user_unban_act(callback: CallbackQuery):
    admin_id = callback.from_user.id
    if not await has_perm(admin_id, "unban_users"):
        await callback.answer(get_str("no_permission", "ru"), show_alert=True)
        return

    target_id = int(callback.data.split(":")[1])
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("UPDATE users SET is_banned = 0, ban_until = NULL WHERE telegram_id = ?", (target_id,))
        await db.commit()

    await log_admin_action(admin_id, target_id, "unban", "1", "0")

    try:
        await bot.send_message(target_id, "✅ Ваш доступ к GiftEz Stars восстановлен.")
    except Exception:
        pass

    await callback.answer("✅ Пользователь разбанен!")
    await callback.message.edit_text(f"✅ Пользователь `{target_id}` успешно разблокирован.")

# --- ИЗМЕНЕНИЕ БАЛАНСА (ВЫДАЧА / СПИСАНИЕ) ---
@router.callback_query(F.data == "adm_balance_menu")
async def process_adm_balance_menu(callback: CallbackQuery, state: FSMContext):
    admin_id = callback.from_user.id
    if not await has_perm(admin_id, "edit_balance"):
        await callback.answer(get_str("no_permission", "ru"), show_alert=True)
        return

    await callback.answer()
    await state.set_state(AdminFSM.waiting_balance_user_id)
    await callback.message.edit_text("⭐ Введите Telegram ID пользователя для изменения баланса:")

@router.callback_query(F.data.startswith("adm_user_bal_edit:"))
async def process_adm_user_bal_edit(callback: CallbackQuery, state: FSMContext):
    admin_id = callback.from_user.id
    if not await has_perm(admin_id, "edit_balance"):
        await callback.answer(get_str("no_permission", "ru"), show_alert=True)
        return

    await callback.answer()
    target_id = int(callback.data.split(":")[1])
    await state.update_data(bal_target_id=target_id)
    await state.set_state(AdminFSM.waiting_balance_amount)
    await callback.message.edit_text(f"⭐ Введите сумму изменения баланса для `{target_id}` (например +5.5 или -2.0):", parse_mode=ParseMode.MARKDOWN)

@router.message(AdminFSM.waiting_balance_user_id)
async def process_bal_user_id_input(message: Message, state: FSMContext):
    try:
        target_id = int(message.text)
    except ValueError:
        await message.answer("❌ ID должен быть числом. Попробуйте еще раз:")
        return

    await state.update_data(bal_target_id=target_id)
    await state.set_state(AdminFSM.waiting_balance_amount)
    await message.answer("⭐ Введите сумму изменения (например +5.5 или -2.0):")

@router.message(AdminFSM.waiting_balance_amount)
async def process_bal_amount_input(message: Message, state: FSMContext):
    try:
        delta = float(message.text)
    except ValueError:
        await message.answer("❌ Введите числовое значение (например: +10 или -5):")
        return

    data = await state.get_data()
    target_id = data["bal_target_id"]
    admin_id = message.from_user.id

    u = await get_user(target_id)
    if not u:
        await message.answer("❌ Пользователь не найден в базе данных.")
        await state.clear()
        return

    old_bal = u["balance"]
    new_bal = await update_user_balance(target_id, delta)

    await log_admin_action(admin_id, target_id, "edit_balance", str(old_bal), str(new_bal))

    try:
        await bot.send_message(target_id, "⭐ Ваш баланс был изменен администратором.")
    except Exception:
        pass

    await state.clear()
    await message.answer(
        f"✅ Баланс пользователя `{target_id}` обновлен!\nБыло: {old_bal:.2f} | Стало: {new_bal:.2f}",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=await build_admin_main_kb(admin_id, "ru")
    )

# --- МОДУЛИ ---
@router.callback_query(F.data == "adm_modules_menu")
async def process_adm_modules_menu(callback: CallbackQuery):
    admin_id = callback.from_user.id
    if not await has_perm(admin_id, "manage_modules"):
        await callback.answer(get_str("no_permission", "ru"), show_alert=True)
        return

    await callback.answer()
    mods = {
        "mod_rewards": "Награды за сообщения",
        "mod_withdraws": "Вывод Звезд",
        "mod_bonus": "Ежедневный бонус",
        "mod_sub_check": "Проверка подписки",
        "mod_groups": "Работа групп",
        "mod_broadcast": "Рассылки"
    }

    kb = []
    text = "⚙️ **Управление модулями системы:**\n\n"
    for k, name in mods.items():
        val = await get_setting(k, "1")
        st_icon = "✅" if val == "1" else "❌"
        text += f"{st_icon} **{name}**\n"
        kb.append([InlineKeyboardButton(text=f"{st_icon} {name}", callback_data=f"adm_mod_toggle:{k}")])

    kb.append([InlineKeyboardButton(text="🔙 Назад", callback_data="admin_main")])
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb), parse_mode=ParseMode.MARKDOWN)

@router.callback_query(F.data.startswith("adm_mod_toggle:"))
async def process_adm_mod_toggle(callback: CallbackQuery):
    admin_id = callback.from_user.id
    if not await has_perm(admin_id, "manage_modules"):
        await callback.answer(get_str("no_permission", "ru"), show_alert=True)
        return

    mod_key = callback.data.split(":")[1]
    curr = await get_setting(mod_key, "1")
    new_val = "0" if curr == "1" else "1"
    await set_setting(mod_key, new_val)

    await log_admin_action(admin_id, 0, "toggle_module", curr, new_val)
    await process_adm_modules_menu(callback)

# --- УПРАВЛЕНИЕ АДМИНИСТРАТОРАМИ ---
@router.callback_query(F.data == "adm_admins_menu")
async def process_adm_admins_menu(callback: CallbackQuery):
    admin_id = callback.from_user.id
    if not await has_perm(admin_id, "manage_admins"):
        await callback.answer(get_str("no_permission", "ru"), show_alert=True)
        return

    await callback.answer()
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM admins") as cursor:
            admins_list = await cursor.fetchall()

    text = "👮 **Список администраторов:**\n\n"
    kb = []
    for adm in admins_list:
        text += f"• `{adm['telegram_id']}` (Добавил: `{adm['added_by']}`)\n"
        if adm['telegram_id'] != OWNER_ID:
            kb.append([InlineKeyboardButton(text=f"⚙️ Права `{adm['telegram_id']}`", callback_data=f"adm_perm_edit:{adm['telegram_id']}")])

    kb.append([InlineKeyboardButton(text="➕ Добавить администратора", callback_data="adm_add_admin")])
    kb.append([InlineKeyboardButton(text="🔙 Назад", callback_data="admin_main")])
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb), parse_mode=ParseMode.MARKDOWN)

@router.callback_query(F.data == "adm_add_admin")
async def process_adm_add_admin(callback: CallbackQuery, state: FSMContext):
    admin_id = callback.from_user.id
    if not await has_perm(admin_id, "manage_admins"):
        await callback.answer(get_str("no_permission", "ru"), show_alert=True)
        return

    await callback.answer()
    await state.set_state(AdminFSM.waiting_add_admin_id)
    await callback.message.edit_text("🆔 Введите Telegram ID нового администратора:")

@router.message(AdminFSM.waiting_add_admin_id)
async def process_add_admin_id_input(message: Message, state: FSMContext):
    try:
        new_admin_id = int(message.text)
    except ValueError:
        await message.answer("❌ ID должен быть числом. Попробуйте еще раз:")
        return

    now_str = datetime.now().isoformat()
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("INSERT OR IGNORE INTO admins (telegram_id, created_at, added_by) VALUES (?, ?, ?)",
                         (new_admin_id, now_str, message.from_user.id))
        for p in ALL_PERMISSIONS:
            await db.execute("INSERT OR IGNORE INTO permissions (admin_id, permission_name, enabled) VALUES (?, ?, 1)",
                             (new_admin_id, p))
        await db.commit()

    await state.clear()
    await message.answer(f"✅ Пользователь `{new_admin_id}` назначен администратором со всеми правами.", reply_markup=await build_admin_main_kb(message.from_user.id, "ru"))

@router.callback_query(F.data.startswith("adm_perm_edit:"))
async def process_adm_perm_edit(callback: CallbackQuery):
    admin_id = callback.from_user.id
    if not await has_perm(admin_id, "manage_admins"):
        await callback.answer(get_str("no_permission", "ru"), show_alert=True)
        return

    await callback.answer()
    target_adm_id = int(callback.data.split(":")[1])

    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT permission_name, enabled FROM permissions WHERE admin_id = ?", (target_adm_id,)) as cursor:
            perms = await cursor.fetchall()

    perm_dict = {p["permission_name"]: p["enabled"] for p in perms}

    kb = []
    text = f"⚙️ **Управление правами админа `{target_adm_id}`:**\n\n"
    for p in ALL_PERMISSIONS:
        st = "✅" if perm_dict.get(p, 0) == 1 else "❌"
        kb.append([InlineKeyboardButton(text=f"{st} {p}", callback_data=f"adm_perm_toggle:{target_adm_id}:{p}")])

    kb.append([InlineKeyboardButton(text="🗑 Удалить администратора", callback_data=f"adm_remove_admin:{target_adm_id}")])
    kb.append([InlineKeyboardButton(text="🔙 Назад", callback_data="adm_admins_menu")])
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb), parse_mode=ParseMode.MARKDOWN)

@router.callback_query(F.data.startswith("adm_perm_toggle:"))
async def process_adm_perm_toggle(callback: CallbackQuery):
    admin_id = callback.from_user.id
    if not await has_perm(admin_id, "manage_admins"):
        await callback.answer(get_str("no_permission", "ru"), show_alert=True)
        return

    parts = callback.data.split(":")
    target_adm_id = int(parts[1])
    perm_name = parts[2]

    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute("SELECT enabled FROM permissions WHERE admin_id = ? AND permission_name = ?",
                               (target_adm_id, perm_name)) as cursor:
            row = await cursor.fetchone()
            curr = row[0] if row else 0
        new_val = 0 if curr == 1 else 1
        await db.execute("INSERT OR REPLACE INTO permissions (admin_id, permission_name, enabled) VALUES (?, ?, ?)",
                         (target_adm_id, perm_name, new_val))
        await db.commit()

    await process_adm_perm_edit(callback)

@router.callback_query(F.data.startswith("adm_remove_admin:"))
async def process_adm_remove_admin(callback: CallbackQuery):
    admin_id = callback.from_user.id
    if not await has_perm(admin_id, "manage_admins"):
        await callback.answer(get_str("no_permission", "ru"), show_alert=True)
        return

    target_adm_id = int(callback.data.split(":")[1])
    if target_adm_id == OWNER_ID:
        await callback.answer("❌ Нельзя удалить владельца бота!", show_alert=True)
        return

    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("DELETE FROM admins WHERE telegram_id = ?", (target_adm_id,))
        await db.execute("DELETE FROM permissions WHERE admin_id = ?", (target_adm_id,))
        await db.commit()

    await callback.answer("✅ Администратор удален!")
    await process_adm_admins_menu(callback)

# --- НАСТРОЙКИ, ШАНСЫ И БОНУСЫ ---
@router.callback_query(F.data == "adm_settings_menu")
async def process_adm_settings_menu(callback: CallbackQuery):
    admin_id = callback.from_user.id
    if not await has_perm(admin_id, "manage_settings"):
        await callback.answer(get_str("no_permission", "ru"), show_alert=True)
        return

    await callback.answer()
    min_len = await get_setting("min_msg_len", "5")
    af_cd = await get_setting("antiflood_cooldown", "30")
    wd_cd = await get_setting("withdraw_cooldown", "300")

    text = (
        f"⚙️ **Системные Настройки:**\n\n"
        f"1️⃣ Мин. длина сообщения: `{min_len}` символов\n"
        f"2️⃣ Антифлуд кулдаун: `{af_cd}` сек.\n"
        f"3️⃣ Задержка между заявками вывода: `{wd_cd}` сек."
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Изменить Мин. длину сообщения", callback_data="adm_set_edit:min_msg_len")],
        [InlineKeyboardButton(text="Изменить Антифлуд кулдаун", callback_data="adm_set_edit:antiflood_cooldown")],
        [InlineKeyboardButton(text="Изменить Задержку выводов", callback_data="adm_set_edit:withdraw_cooldown")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_main")]
    ])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)

@router.callback_query(F.data == "adm_chances_menu")
async def process_adm_chances_menu(callback: CallbackQuery):
    admin_id = callback.from_user.id
    if not await has_perm(admin_id, "manage_chances"):
        await callback.answer(get_str("no_permission", "ru"), show_alert=True)
        return

    await callback.answer()
    main_chance = await get_setting("msg_reward_chance", "15")

    text = (
        f"🎲 **Управление Шансами и Диапазонами:**\n\n"
        f"🎯 Общий шанс начисления за сообщение: `{main_chance}%`\n\n"
        f"**Веса выпадения диапазонов (в %):**\n"
        f"• 0.01-0.10: `{await get_setting('rng_0.01_0.10', '70')}%`\n"
        f"• 0.10-0.50: `{await get_setting('rng_0.10_0.50', '20')}%`\n"
        f"• 0.50-1.00: `{await get_setting('rng_0.50_1.00', '7')}%`\n"
        f"• 1.00-2.00: `{await get_setting('rng_1.00_2.00', '2')}%`\n"
        f"• 2.00-3.00: `{await get_setting('rng_2.00_3.00', '0.8')}%`\n"
        f"• 3.00-4.00: `{await get_setting('rng_3.00_4.00', '0.15')}%`\n"
        f"• 4.00-5.00: `{await get_setting('rng_4.00_5.00', '0.05')}%`"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎯 Общий шанс сообщения", callback_data="adm_set_edit:msg_reward_chance")],
        [InlineKeyboardButton(text="Изменить диапазон 0.01-0.10", callback_data="adm_set_edit:rng_0.01_0.10")],
        [InlineKeyboardButton(text="Изменить диапазон 0.10-0.50", callback_data="adm_set_edit:rng_0.10_0.50")],
        [InlineKeyboardButton(text="Изменить диапазон 0.50-1.00", callback_data="adm_set_edit:rng_0.50_1.00")],
        [InlineKeyboardButton(text="Изменить диапазон 1.00-2.00", callback_data="adm_set_edit:rng_1.00_2.00")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_main")]
    ])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)

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
        f"🎁 **Настройки Ежедневного Бонуса:**\n\n"
        f"🔹 Мин. награда: `{b_min}` Звезд\n"
        f"🔸 Макс. награда: `{b_max}` Звезд"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Изменить Мин. бонус", callback_data="adm_set_edit:bonus_min")],
        [InlineKeyboardButton(text="Изменить Макс. бонус", callback_data="adm_set_edit:bonus_max")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_main")]
    ])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)

@router.callback_query(F.data.startswith("adm_set_edit:"))
async def process_adm_set_edit(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    key = callback.data.split(":")[1]
    await state.update_data(setting_key=key)
    await state.set_state(AdminFSM.waiting_setting_value)
    await callback.message.edit_text(f"⚙️ Введите новое значение для `{key}`:", parse_mode=ParseMode.MARKDOWN)

@router.message(AdminFSM.waiting_setting_value)
async def process_setting_value_input(message: Message, state: FSMContext):
    data = await state.get_data()
    key = data["setting_key"]
    val = message.text.strip()

    await set_setting(key, val)
    await log_admin_action(message.from_user.id, 0, f"set_setting_{key}", "", val)

    await state.clear()
    await message.answer(f"✅ Настройка `{key}` успешно изменена на `{val}`.", parse_mode=ParseMode.MARKDOWN, reply_markup=await build_admin_main_kb(message.from_user.id, "ru"))

# ==============================================================================
# ЗАПУСК БОТА И MAIN
# ==============================================================================

async def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(name)s - %(message)s")
    logging.info("Инициализация базы данных...")
    await init_db()

    logging.info("Запуск GiftEz Stars Telegram Bot...")
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())