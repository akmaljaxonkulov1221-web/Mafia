import asyncio
import json
import os
import random
import datetime
from collections import defaultdict
from typing import Dict, Any, Optional, List

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.types import BotCommand, BotCommandScopeAllPrivateChats, BotCommandScopeAllGroupChats
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

# ================= CONFIG =================
TOKEN = "7969313997:AAGPTAZsJJ7oabfA4GiyjVYMMF_nRCYPGVc"

if not TOKEN:
    raise SystemExit("BOT_TOKEN topilmadi. PowerShell: $env:BOT_TOKEN=\"xxxx\" qilib qayta ishga tushiring.")

bot = Bot(token=TOKEN)
dp = Dispatcher()

# ================= SHOP / ECONOMY (Mafia Baku Black-style) =================
SHOP_ITEMS: Dict[str, Dict[str, Any]] = {
    # money items
    "protect": {"title": "🛡 Himoya", "currency": "money", "price": 120, "field": "protect", "qty": 1},
    "vote_protect": {"title": "⚖️ Vote protect", "currency": "money", "price": 150, "field": "vote_protect", "qty": 1},
    "mask": {"title": "🎭 Maska", "currency": "money", "price": 90, "field": "mask", "qty": 1},
    "fake_docs": {"title": "📁 Soxta hujjat", "currency": "money", "price": 110, "field": "fake_docs", "qty": 1},
    # diamond items
    "anti_killer": {"title": "⛑️ Qotildan himoya", "currency": "diamonds", "price": 3, "field": "anti_killer", "qty": 1},
    "gun": {"title": "🔫 Miltiq", "currency": "diamonds", "price": 5, "field": "gun", "qty": 1},
}

# ================= DB =================
USERS_DB = "users.json"
GROUP_DB = "groups.json"


def _load_json(path: str) -> Dict[str, Any]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_json(path: str, data: Dict[str, Any]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


DEFAULT_USER = {
    "name": "User",
    "language": "uz",
    "money": 250,
    "diamonds": 0,
    "wins": 0,
    "games": 0,

    # items / protects
    "protect": 0,        # 🛡
    "anti_killer": 0,    # ⛑️
    "vote_protect": 0,   # ⚖️
    "gun": 0,            # 🔫
    "mask": 0,           # 🎭
    "fake_docs": 0,      # 📁
    "next_role": "-",    # 🃏
}


def load_users() -> Dict[str, Any]:
    return _load_json(USERS_DB)


def save_users(data: Dict[str, Any]) -> None:
    _save_json(USERS_DB, data)


def get_user(uid: int, name: str) -> Dict[str, Any]:
    users = load_users()
    suid = str(uid)
    if suid not in users:
        u = DEFAULT_USER.copy()
        u["name"] = name or "User"
        users[suid] = u
        save_users(users)
        return u

    u = users[suid]
    changed = False
    for k, v in DEFAULT_USER.items():
        if k not in u:
            u[k] = v
            changed = True
    if name and u.get("name") != name:
        u["name"] = name
        changed = True
    if changed:
        users[suid] = u
        save_users(users)
    return u


def update_user(uid: int, user: Dict[str, Any]) -> None:
    users = load_users()
    users[str(uid)] = user
    save_users(users)


def load_groups() -> Dict[str, Any]:
    return _load_json(GROUP_DB)


def save_groups(data: Dict[str, Any]) -> None:
    _save_json(GROUP_DB, data)


DEFAULT_GROUP = {
    "lang": "uz",

    "silent_mode": False,      # 🔇
    "reveal_roles": True,      # 🎭
    "allow_teamgame": True,   # 🔵🔴
    "allow_giveaway": False,  # 🎁
    "weapons_enabled": False, # 🔫

    "night_seconds": 25,
    "discussion_seconds": 15,
    "day_seconds": 25,
    "registration_seconds": 60,
}


def get_group(chat_id: int) -> Dict[str, Any]:
    groups = load_groups()
    sid = str(chat_id)
    if sid not in groups:
        groups[sid] = DEFAULT_GROUP.copy()
        save_groups(groups)
    g = groups[sid]
    changed = False
    for k, v in DEFAULT_GROUP.items():
        if k not in g:
            g[k] = v
            changed = True
    if changed:
        groups[sid] = g
        save_groups(groups)
    return g


def update_group(chat_id: int, group: Dict[str, Any]) -> None:
    groups = load_groups()
    groups[str(chat_id)] = group
    save_groups(groups)


# ================= ADMIN CHECK =================
async def is_admin(chat_id: int, user_id: int) -> bool:
    try:
        m = await bot.get_chat_member(chat_id, user_id)
        return m.status in ("administrator", "creator")
    except Exception:
        return False


# ================= I18N =================
LANGS = {
    "uz": "O'zbek", "ru": "Русский", "en": "English", "tr": "Türkçe", "kz": "Қазақша",
    "tg": "Тоҷикӣ", "az": "Azərbaycan", "kk": "Qaraqalpaq", "ky": "Кыргызча", "ar": "العربية"
}

TXT = {
    "private_start": {
        "uz": "👋 Mafia botga xush kelibsiz!\nPastdagi /commands menu'dan foydalaning.",
        "ru": "👋 Добро пожаловать!\nИспользуйте меню команд внизу слева.",
        "en": "👋 Welcome!\nUse commands menu on the bottom-left.",
    }
}


def tr(uid: int, key: str) -> str:
    u = get_user(uid, "User")
    lang = u.get("language", "uz")
    return TXT.get(key, {}).get(lang) or TXT.get(key, {}).get("uz") or key


def fmt_money(n: int) -> str:
    try:
        return f"{int(n):,}".replace(",", " ")
    except Exception:
        return str(n)


# ================= MENU COMMANDS (bottom-left) =================
async def setup_commands_menu():
    # Private - All commands like Mafia Baku Black 2
    await bot.set_my_commands(
        commands=[
            BotCommand(command="start", description="🎮 Boshlash"),
            BotCommand(command="profile", description="👤 Profil"),
            BotCommand(command="roles", description="🎭 Rollar"),
            BotCommand(command="top", description="🏆 Top"),
            BotCommand(command="lang", description="🌐 Til"),
            BotCommand(command="shop", description="🛒 Do'kon"),
            BotCommand(command="buy", description="💰 Sotib olish"),
            BotCommand(command="help", description="📚 Yordam"),
            BotCommand(command="game", description="🎮 O'yin"),
            BotCommand(command="back", description="🔙 Guruhga qaytish"),
            BotCommand(command="stats", description="📊 Statistika"),
            BotCommand(command="balance", description="💰 Balans"),
            BotCommand(command="inventory", description="🎒 Inventar"),
            BotCommand(command="daily", description="🎁 Kunlik bonus"),
            BotCommand(command="transfer", description="💸 Pul o'tkazish"),
            BotCommand(command="gift", description="🎁 Sovg'a qilish"),
            BotCommand(command="premium", description="👑 Premium"),
        ],
        scope=BotCommandScopeAllPrivateChats()
    )

    # Group - All commands like Mafia Baku Black 2
    await bot.set_my_commands(
        commands=[
            BotCommand(command="game", description="🎮 Ro'yxat boshlash"),
            BotCommand(command="start", description="🚀 O'yinni boshlash"),
            BotCommand(command="stop", description="🛑 O'yinni to'xtatish"),
            BotCommand(command="extend", description="⏰ Vaqtni uzaytirish"),
            BotCommand(command="leave", description="🚪 O'yindan chiqish"),
            BotCommand(command="kick", description="👊 Kik qilish"),
            BotCommand(command="give", description="💎 Olmos berish"),
            BotCommand(command="teamgame", description="👥 Jamoa o'yini"),
            BotCommand(command="top", description="🏆 Guruh top"),
            BotCommand(command="roles", description="🎭 Rollar"),
            BotCommand(command="profile", description="👤 Profil"),
            BotCommand(command="settings", description="⚙️ Sozlamalar"),
            BotCommand(command="shop", description="🛒 Do'kon"),
            BotCommand(command="buy", description="💰 Sotib olish"),
            BotCommand(command="help", description="📚 Yordam"),
            BotCommand(command="menu", description="🎮 Admin menyu"),
            BotCommand(command="stats", description="📊 Guruh statistikasi"),
            BotCommand(command="balance", description="💰 Guruh balansi"),
            BotCommand(command="reset", description="🔄 Guruhni tiklash"),
            BotCommand(command="ban", description="🚫 Ban berish"),
            BotCommand(command="unban", description="✅ Ban olib tashlash"),
            BotCommand(command="mute", description="🔇 Mute qilish"),
            BotCommand(command="unmute", description="🔊 Mute olib tashlash"),
        ],
        scope=BotCommandScopeAllGroupChats()
    )


# ================= ROLES =================
ROLE_EMOJI = {
    "Tinch": "👨🏼",
    "Kezuvchi": "💃",
    "Serjant": "👮🏻‍♂",
    "Komissar": "🕵🏻‍♂",
    "Doktor": "👨🏻‍⚕",
    "Daydi": "🧙‍♂",
    "Afsungar": "🧞‍♂️",
    "Don": "🤵🏻",
    "Mafiya": "🤵🏼",
    "Advokat": "👨‍💼",
    "Qotil": "🔪",
    "Bo'ri": "🐺",
    "G'azabkor": "🧟",
    "Omadli": "🤞🏼",
    "Suisid": "🤦🏼",
}

ROLES_LIST = [
    "Tinch", "Kezuvchi", "Serjant", "Komissar", "Doktor", "Daydi", "Afsungar",
    "Don", "Mafiya", "Advokat", "Qotil", "Bo'ri", "G'azabkor", "Omadli", "Suisid"
]

ROLE_DESC_UZ = {
    "Komissar": "🔴 🕵🏻‍♂ Komissar Kattanining maqsadi.\nMafiyani topish va ovozda osish.\n1-tundan tekshirmasdan otish taqiqlanadi (soddalashtirilgan).",
    "Tinch": "🔴 👨🏼 Tinch aholining maqsadi: mafiyani topish va osish.",
    "Kezuvchi": "🔴 💃 Kezuvchi: tun payti 1 o'yinchini uxlatadi (block). Komissarni uxlatmang.",
    "Serjant": "🔴 👮🏻‍♂ Serjant: Komissarga yordam.\nAgar Komissar o'lsa, Serjant tekshiruvchi bo'lib qoladi.",
    "Doktor": "🔴 👨🏻‍⚕ Doktor: tun payti 1 o'yinchini davolaydi.\nFaqat 1 marta davolashi mumkin (soddalashtirilgan).",
    "Daydi": "🔴 🧙‍♂️ Daydi: tunda borib kuzatadi.\nAgar kuzatgan odam o'lsa, xabar oladi.",
    "Don": "🔴 🤵🏻 Don: Mafiya boshlig'i. Tun payti qotillikni tanlaydi.",
    "Mafiya": "🔴 🤵🏼 Mafiya: tun payti qotillik tanlaydi (jamoa).",
    "Advokat": "🔴 👨‍💼 Advokat: tun payti himoya tanlaydi.\nMafiyani himoyalasa, Komissarga 'Tinch' bo'lib ko'rinadi.",
    "Qotil": "🔴 🔪 Qotil: faqat o'zi tirik qolsa g'olib (solo).",
    "Afsungar": "🔴 🧞‍♂️ Afsungar: o'ldirilsa, o'ldirganni ham olib ketadi.\nKun ovozida o'ldirilsa, 1 kishini o'zi tanlaydi (soddalashtirilgan).",
    "Bo'ri": "🔴 🐺 Bo'ri: reenkarnatsiya (soddalashtirilgan).\nKomissar otsa serjantga, Don otsa mafiaga, qotil otsa bo'ri o'lishi mumkin.",
    "G'azabkor": "🔴 🧟 G'azabkor: o'ldirilganda 1 tasini o'ldiradi.",
    "Omadli": "🔴 🤞🏼 Omadli: har kechasi 1 kishini saqlaydi.",
    "Suisid": "🔴 🤦🏼 Suisid: o'ldirilganda 1 tasini o'zi tanlab o'ldiradi.",
}

def roles_kb() -> InlineKeyboardMarkup:
    rows = []
    for r in ROLES_LIST:
        rows.append([InlineKeyboardButton(text=f"{ROLE_EMOJI.get(r,'🎭')} {r}", callback_data=f"roleinfo:{r}")])
    rows.append([InlineKeyboardButton(text="❌ Yopish", callback_data="roles_close")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ================= GAME =================
GAMES: Dict[int, Dict[str, Any]] = {}

PHASE_IDLE = "idle"
PHASE_REG = "registration"
PHASE_NIGHT = "night"
PHASE_DISCUSSION = "discussion"
PHASE_DAY = "day"
PHASE_AFSUN = "afsun"

DAY_LENGTH_FALLBACK = 25
NIGHT_LENGTH_FALLBACK = 25


def get_game(chat_id: int) -> Dict[str, Any]:
    if chat_id not in GAMES:
        GAMES[chat_id] = {
            "started": False,
            "phase": PHASE_IDLE,
            "loop_task": None,

            # registration
            "reg_deadline": 0.0,
            "teams": None,

            # players
            "players": {},     # uid(str) -> name
            "roles": {},       # uid(str) -> role
            "alive": [],       # [uid(str)]

            # phase controllers
            "night_turn": 0,
            "night_picks": {},
            "mafia_votes": {},   # mafia_actor_uid -> target_uid

            "doc_self_used": set(),
            "afsun_revenge": None,  # afsungar victim chosen in day
            "afsun_target": None,    # chosen target in afsun

            "night": {
                "heal": None,
                "heal_by": None,
                "block": None,               # blocked uid
                "lawyer_protect": None,     # advokat target
                "watch": {},                 # daydi_uid -> watched_uid
                "killer_kill": None,
                "killer_by": None,
            },

            "votes": {},  # voter_uid -> target_uid
        }
    return GAMES[chat_id]


def assign_roles(n: int) -> List[str]:
    base = ["Komissar", "Doktor", "Mafiya", "Tinch", "Tinch", "Tinch"]
    extra = []
    if n >= 6:
        extra += ["Kezuvchi"]
    if n >= 7:
        extra += ["Daydi"]
    if n >= 8:
        extra += ["Don"]
    if n >= 9:
        extra += ["Advokat"]
    if n >= 10:
        extra += ["Afsungar"]
    if n >= 11:
        extra += ["Qotil"]
    if n >= 12:
        extra += ["Bo'ri"]
    if n >= 13:
        extra += ["G'azabkor"]
    if n >= 14:
        extra += ["Omadli"]
    if n >= 15:
        extra += ["Suisid"]

    roles = base + extra
    while len(roles) < n:
        roles.append("Tinch")
    random.shuffle(roles)
    return roles[:n]


def check_win(game: Dict[str, Any]) -> Optional[str]:
    # Qotil solo yutadi
    if len(game["alive"]) == 1 and game["roles"].get(game["alive"][0]) == "Qotil":
        return "Qotil"

    mafia_alive = sum(1 for u in game["alive"] if game["roles"].get(u) in {"Mafiya", "Don", "Advokat"})
    others_alive = len(game["alive"]) - mafia_alive
    if mafia_alive == 0:
        return "Tinchlar"
    if mafia_alive >= others_alive:
        return "Mafiya"
    return None


async def safe_dm(uid: str, text: str, reply_markup=None):
    try:
        await bot.send_message(int(uid), text, reply_markup=reply_markup)
    except (TelegramForbiddenError, TelegramBadRequest):
        pass
    except Exception:
        pass


def make_target_kb(game: Dict[str, Any], prefix: str, chat_id: int, actor_uid: str, forbid: Optional[set] = None):
    forbid = forbid or set()
    rows = []
    for u in game["alive"]:
        if u == actor_uid:
            continue
        if u in forbid:
            continue
        rows.append([InlineKeyboardButton(text=game["players"][u], callback_data=f"{prefix}:{chat_id}:{u}")])
    if not rows:
        rows = [[InlineKeyboardButton(text="—", callback_data="noop")]]
    return InlineKeyboardMarkup(inline_keyboard=rows)


@dp.callback_query(F.data == "noop")
async def cb_noop(cb: CallbackQuery):
    await cb.answer()


def mafia_target_from_votes(game: Dict[str, Any]) -> Optional[str]:
    if not game["mafia_votes"]:
        return None
    cnt = defaultdict(int)
    for _, t in game["mafia_votes"].items():
        cnt[t] += 1
    maxv = max(cnt.values())
    top = [uid for uid, v in cnt.items() if v == maxv]
    return top[0] if len(top) == 1 else None


async def send_night_prompts(chat_id: int):
    game = get_game(chat_id)
    g = get_group(chat_id)

    commissar_like = {u for u in game["alive"] if game["roles"].get(u) in {"Komissar", "Serjant"}}

    for uid in list(game["alive"]):
        role = game["roles"].get(uid)

        if role in {"Mafiya", "Don"}:
            await safe_dm(uid, "🔪 Mafia/Don: kimni o'ldiramiz? (1 marta)",
                          reply_markup=make_target_kb(game, "mk", chat_id, uid))
        elif role == "Qotil":
            await safe_dm(uid, "🔪 Qotil: kimni o'ldirasiz? (1 marta)",
                          reply_markup=make_target_kb(game, "kk", chat_id, uid))
        elif role == "Doktor":
            await safe_dm(uid, "💉 Doktor: kimni davolaysiz? (o'zingizni 1 marta davolash mumkin)",
                          reply_markup=make_target_kb(game, "heal", chat_id, uid))
        elif role == "Kezuvchi":
            await safe_dm(uid, "💃 Kezuvchi: kimni uxlatib qo'yasiz? (Komissar/Serjantni block qilmang)",
                          reply_markup=make_target_kb(game, "block", chat_id, uid, forbid=commissar_like))
        elif role in {"Komissar", "Serjant"}:
            await safe_dm(uid, "🕵️ Tekshiruv: kimni tekshirasiz? (1 marta)",
                          reply_markup=make_target_kb(game, "check", chat_id, uid))
        elif role == "Advokat":
            await safe_dm(uid, "👨‍💼 Advokat: kimni himoya qilasiz?",
                          reply_markup=make_target_kb(game, "law", chat_id, uid))
        elif role == "Daydi":
            await safe_dm(uid, "🧙‍♂️ Daydi: kimni kuzatasiz?",
                          reply_markup=make_target_kb(game, "watch", chat_id, uid))


async def resolve_night(chat_id: int) -> List[str]:
    game = get_game(chat_id)
    events: List[str] = []

    blocked_uid = game["night"]["block"]

    def is_blocked(actor_uid: Optional[str]) -> bool:
        return actor_uid is not None and blocked_uid == actor_uid

    # apply block to heal/killer
    heal_target = game["night"]["heal"]
    heal_by = game["night"]["heal_by"]
    if is_blocked(heal_by):
        heal_target = None

    mafia_target = mafia_target_from_votes(game)
    killer_target = game["night"]["killer_kill"]
    killer_by = game["night"]["killer_by"]
    if is_blocked(killer_by):
        killer_target = None

    # watch after deaths
    watched = dict(game["night"]["watch"])
    deaths: Dict[str, str] = {}  # victim_uid -> killer_type

    def consume_item_if(uid_str: str, field: str) -> bool:
        """Consumes one item if user has it; returns True if consumed."""
        try:
            u = get_user(int(uid_str), game["players"].get(uid_str, "User"))
            cur = int(u.get(field, 0))
            if cur > 0:
                u[field] = cur - 1
                update_user(int(uid_str), u)
                return True
        except Exception:
            pass
        return False

    def has_item(uid_str: str, field: str) -> bool:
        try:
            u = get_user(int(uid_str), game["players"].get(uid_str, "User"))
            return int(u.get(field, 0)) > 0
        except Exception:
            return False

    # lawyer protect doesn't block kill in this simplified mode (it affects check). Keeping for "Baku-style" deception.

    if mafia_target and mafia_target in game["alive"]:
        # doctor heal
        if mafia_target == heal_target:
            events.append(f"💉 {game['players'][mafia_target]} saqlandi!")
        else:
            # 🛡 protect: blocks ONE night kill
            if consume_item_if(mafia_target, "protect"):
                events.append(f"🛡 {game['players'][mafia_target]} himoya ishlatdi!")
            else:
                deaths[mafia_target] = "mafia"

    if killer_target and killer_target in game["alive"]:
        if killer_target == heal_target:
            events.append(f"💉 {game['players'][killer_target]} saqlandi!")
        else:
            # ⛑ anti_killer protects ONLY from killer
            if consume_item_if(killer_target, "anti_killer"):
                events.append(f"⛑️ {game['players'][killer_target]} qotildan himoyalandi!")
            else:
                # 🛡 also blocks any night kill
                if consume_item_if(killer_target, "protect"):
                    events.append(f"🛡 {game['players'][killer_target]} himoya ishlatdi!")
                else:
                    deaths[killer_target] = "killer"

    # unique victims
    dead_set = set()
    for victim_uid in list(deaths.keys()):
        if victim_uid not in game["alive"]:
            continue
        victim_role = game["roles"].get(victim_uid)
        game["alive"].remove(victim_uid)
        dead_set.add(victim_uid)
        events.append(f"☠️ {game['players'][victim_uid]} o'ldirildi!")

        # Afsungar ketayotib olib ketish (soddalashtirilgan)
        if victim_role == "Afsungar":
            # agar o'ldiruvchi bo'lsa — killer_by hali saqlanmagan, soddalashtirilgan: qo'shimcha o'lim yo'q
            pass

        # Serjant/Komissar reveal continuing (soddalashtirilgan)
        if victim_role == "Komissar":
            # Agar serjant tirik bo'lsa, check imkoniyati saqlanadi (callback allaqachon ruxsat beradi)
            pass

    # Daydi notifications
    for daydi_uid, watched_uid in watched.items():
        if daydi_uid in game["alive"] and watched_uid in dead_set:
            await safe_dm(daydi_uid, f"🧙‍♂️ Daydi: kuzatgan odam o'ldi: {game['players'][watched_uid]}")

    # clear night actions
    game["night_picks"].clear()
    game["mafia_votes"].clear()
    game["night"] = {
        "heal": None,
        "heal_by": None,
        "block": None,
        "lawyer_protect": None,
        "watch": {},
        "killer_kill": None,
        "killer_by": None,
    }
    return events


def resolve_vote(game: Dict[str, Any]) -> Optional[str]:
    cnt = defaultdict(int)
    for target in game["votes"].values():
        cnt[target] += 1
    game["votes"].clear()
    if not cnt:
        return None
    maxv = max(cnt.values())
    top = [uid for uid, v in cnt.items() if v == maxv]
    return top[0] if len(top) == 1 else None


def consume_vote_protect_if(game: Dict[str, Any], uid_str: str) -> bool:
    """Consumes vote_protect item if present; returns True if consumed."""
    try:
        u = get_user(int(uid_str), game["players"].get(uid_str, "User"))
        cur = int(u.get("vote_protect", 0))
        if cur > 0:
            u["vote_protect"] = cur - 1
            update_user(int(uid_str), u)
            return True
    except Exception:
        pass
    return False


async def end_game(chat_id: int, winner: str):
    game = get_game(chat_id)
    g = get_group(chat_id)

    if not g.get("silent_mode", False):
        await bot.send_message(chat_id, f"🏆 O'yin tugadi! G'olib: {winner}")

    # stats
    for uid_str, name in game["players"].items():
        u = get_user(int(uid_str), name)
        u["games"] = u.get("games", 0) + 1
        role = game["roles"].get(uid_str)

        if winner == "Tinchlar":
            if role not in {"Mafiya", "Don", "Advokat"}:
                u["wins"] = u.get("wins", 0) + 1
        elif winner == "Mafiya":
            if role in {"Mafiya", "Don", "Advokat"}:
                u["wins"] = u.get("wins", 0) + 1
        elif winner == "Qotil":
            if role == "Qotil":
                u["wins"] = u.get("wins", 0) + 1

        update_user(int(uid_str), u)

    t = game.get("loop_task")
    if t and not t.done():
        t.cancel()

    GAMES.pop(chat_id, None)


async def game_loop(chat_id: int):
    game = get_game(chat_id)

    while True:
        winner = check_win(game)
        if winner:
            await end_game(chat_id, winner)
            return

        g = get_group(chat_id)

        # NIGHT
        game["phase"] = PHASE_NIGHT
        game["night_turn"] += 1
        game["night_picks"] = {}
        await bot.send_message(chat_id, f"🌙 Tun boshlandi... ({g['night_seconds']}s)") if not g["silent_mode"] else None
        await send_night_prompts(chat_id)
        await asyncio.sleep(g["night_seconds"])

        events = await resolve_night(chat_id)
        await bot.send_message(
            chat_id,
            "🌙 Tun yakuni:\n" + ("\n".join(events) if events else "😴 Hech narsa bo'lmadi.")
        ) if not g["silent_mode"] else None

        winner = check_win(game)
        if winner:
            await end_game(chat_id, winner)
            return

        # DISCUSSION
        game["phase"] = PHASE_DISCUSSION
        await bot.send_message(chat_id, f"🗣 Muhokama vaqti: {g['discussion_seconds']}s") if not g["silent_mode"] else None
        await asyncio.sleep(g["discussion_seconds"])

        # DAY VOTE
        game["phase"] = PHASE_DAY
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=game["players"][u], callback_data=f"vote:{chat_id}:{u}")]
                for u in game["alive"]
            ]
        )
        await bot.send_message(chat_id, f"☀️ Kun: kimni chiqaramiz? ({g['day_seconds']}s)", reply_markup=kb) if not g["silent_mode"] else None
        await asyncio.sleep(g["day_seconds"])

        victim = resolve_vote(game)
        if victim and victim in game["alive"]:
            # ⚖️ vote protect consumes and blocks ONE day elimination
            if consume_vote_protect_if(game, victim):
                if not g["silent_mode"]:
                    await bot.send_message(chat_id, f"⚖️ {game['players'][victim]} vote protect ishlatdi! (Saqlanib qoldi)")
                continue

            game["alive"].remove(victim)
            role = game["roles"].get(victim, "—")

            if not g["silent_mode"]:
                if g["reveal_roles"]:
                    await bot.send_message(chat_id, f"⚖️ {game['players'][victim]} chiqarildi! (Rol: {role})")
                else:
                    await bot.send_message(chat_id, f"⚖️ {game['players'][victim]} chiqarildi!")

            # Afsungar day revenge stage
            if role == "Afsungar":
                game["afsun_revenge"] = victim
                game["afsun_target"] = None
                await safe_dm(victim, f"🧞‍♂️ Afsungar ketmoqda... kimni o'zi bilan olib ketasiz?",
                              reply_markup=make_target_kb(game, "afsun", chat_id, actor_uid=victim))
                game["phase"] = PHASE_AFSUN
                await asyncio.sleep(15)

                if game["afsun_target"] and game["afsun_target"] in game["alive"]:
                    killed = game["afsun_target"]
                    game["alive"].remove(killed)
                    if not g["silent_mode"]:
                        await bot.send_message(chat_id, f"🧞‍♂️ Afsungar qo'shimcha o'lim: {game['players'][killed]}")

                game["afsun_revenge"] = None
                game["afsun_target"] = None

        else:
            await bot.send_message(chat_id, "☀️ Hech kim chiqarilmadi (teng ovoz yoki ovoz yo'q).") if not g["silent_mode"] else None


# ================= TOGGLE CALLBACK HANDLERS =================
@dp.callback_query(F.data.startswith("toggle:"))
async def cb_toggle(cb: CallbackQuery):
    item = cb.data.split(":", 1)[1]
    u = get_user(cb.from_user.id, cb.from_user.full_name)
    
    await cb.answer()
    
    if item == "protect":
        if u.get('protect', 0) > 0:
            u['protect'] = 0
            await cb.answer("🛡 Himoya o'chirildi", show_alert=True)
        else:
            await cb.answer("🛡 Himoya uchun do'konga boring", show_alert=True)
    elif item == "anti_killer":
        if u.get('anti_killer', 0) > 0:
            u['anti_killer'] = 0
            await cb.answer("⛑️ Qotildan himoyasi o'chirildi", show_alert=True)
        else:
            await cb.answer("⛑️ Qotildan himoyasi uchun do'konga boring", show_alert=True)
    elif item == "vote_protect":
        if u.get('vote_protect', 0) > 0:
            u['vote_protect'] = 0
            await cb.answer("⚖️ Ovoz himoyasi o'chirildi", show_alert=True)
        else:
            await cb.answer("⚖️ Ovoz himoyasi uchun do'konga boring", show_alert=True)
    elif item == "gun":
        if u.get('gun', 0) > 0:
            u['gun'] = 0
            await cb.answer("🔫 Miltiq o'chirildi", show_alert=True)
        else:
            await cb.answer("🔫 Miltiq uchun do'konga boring", show_alert=True)
    
    update_user(cb.from_user.id, u)
    
    # Refresh profile
    await cb_menu(cb)


# ================= ADDITIONAL CALLBACK HANDLERS =================
@dp.callback_query(F.data.startswith("buy:money"))
async def cb_buy_money(cb: CallbackQuery):
    await cb.answer("💵 Dollar xaridi uchun do'konga boring", show_alert=True)
    await cb.message.edit_text("🛒 Do'kon. Sotib olish uchun bosing:", reply_markup=shop_kb())

@dp.callback_query(F.data.startswith("buy:diamond"))
async def cb_buy_diamond(cb: CallbackQuery):
    await cb.answer("💎 Olmos xaridi uchun do'konga boring", show_alert=True)
    await cb.message.edit_text("🛒 Do'kon. Sotib olish uchun bosing:", reply_markup=shop_kb())

@dp.callback_query(F.data.startswith("premium:"))
async def cb_premium(cb: CallbackQuery):
    await cb.answer("👑 Premium guruhlar tez orada!", show_alert=True)

@dp.callback_query(F.data == "news")
async def cb_news(cb: CallbackQuery):
    news_text = (
        "📰 Mafia Bot Yangiliklar\n\n"
        "🆕 Yangi imkoniyatlar:\n"
        "• 🎮 Yaxshilangan o'yin interfeysi\n"
        "• 🛒 Kengaytirilgan do'kon\n"
        "• 👥 Jamoa o'yinlari\n"
        "• 🔙 Guruhga qaytish funksiyasi\n\n"
        "🔮 Tez kunda:\n"
        "• 🏆 Turnirlar\n"
        "• 🎁 Sovg'alar\n"
        "• 🌟 VIP imkoniyatlar\n\n"
        "📞 Bog'lanish: @admin"
    )
    back_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="menu:start")]
    ])
    await cb.answer()
    await cb.message.edit_text(news_text, reply_markup=back_kb)


# ================= MENU CALLBACK HANDLERS =================
@dp.callback_query(F.data.startswith("menu:"))
async def cb_menu(cb: CallbackQuery):
    action = cb.data.split(":", 1)[1]
    await cb.answer()
    
    if action == "profile":
        u = get_user(cb.from_user.id, cb.from_user.full_name)
        
        # Create toggle buttons for items - 1xl size
        toggle_rows = []
        
        # Himoya toggle
        protect_status = "🟢 ON" if u.get('protect', 0) > 0 else "🔴 OFF"
        toggle_rows.append([InlineKeyboardButton(text=f"🛡 Himoya {protect_status}", callback_data="toggle:protect")])
        
        # Qotildan himoya toggle
        anti_killer_status = "🟢 ON" if u.get('anti_killer', 0) > 0 else "🔴 OFF"
        toggle_rows.append([InlineKeyboardButton(text=f"⛑️ Qotildan himoya {anti_killer_status}", callback_data="toggle:anti_killer")])
        
        # Ovoz berishni himoya qilish toggle
        vote_protect_status = "🟢 ON" if u.get('vote_protect', 0) > 0 else "🔴 OFF"
        toggle_rows.append([InlineKeyboardButton(text=f"⚖️ Ovoz berishni himoya qilish {vote_protect_status}", callback_data="toggle:vote_protect")])
        
        # Miltiq toggle
        gun_status = "🟢 ON" if u.get('gun', 0) > 0 else "🔴 OFF"
        toggle_rows.append([InlineKeyboardButton(text=f"🔫 Miltiq {gun_status}", callback_data="toggle:gun")])
        
        # Action buttons - matching screenshot layout
        action_rows = [
            [InlineKeyboardButton(text="🛒 Do'kon", callback_data="menu:shop")],
            [InlineKeyboardButton(text="💵 Xarid qilish", callback_data="buy:money")],
            [InlineKeyboardButton(text="💎 Xarid qilish", callback_data="buy:diamond")],
            [InlineKeyboardButton(text="👑 Premium guruhlar", callback_data="premium:groups")],
            [InlineKeyboardButton(text="📰 Yangiliklar", callback_data="news")],
        ]
        
        profile_kb = InlineKeyboardMarkup(inline_keyboard=toggle_rows + action_rows)
        
        # Profile text matching screenshot format
        text = (
            f"⭐️ ID: {cb.from_user.id}\n"
            f"👤 Username: {cb.from_user.full_name}\n\n"
            f"💵 Dollar: {fmt_money(u.get('money', 0))}\n"
            f"💎 Olmos: {u.get('diamonds', 0)}\n\n"
            f"🛡 Himoya: {u.get('protect', 0)}\n"
            f"⛑️ Qotildan himoya: {u.get('anti_killer', 0)}\n"
            f"⚖️ Ovoz berishni himoya qilish: {u.get('vote_protect', 0)}\n"
            f"🔫 Miltiq: {u.get('gun', 0)}\n\n"
            f"🎭 Maska: {u.get('mask', 0)}\n"
            f"📁 Soxta hujjat: {u.get('fake_docs', 0)}\n"
            f"🃏 Keyingi o'yindagi rolingiz: {u.get('next_role', '-')}\n\n"
            f"🎯 G'alaba: {u.get('wins', 0)}\n"
            f"🎲 Jami o'yinlar: {u.get('games', 0)}"
        )
        
        await cb.message.edit_text(text, reply_markup=profile_kb)
        
    elif action == "game":
        u = get_user(cb.from_user.id, cb.from_user.full_name)
        
        # Find active games where user is participating
        active_games = []
        for chat_id, game in GAMES.items():
            if str(cb.from_user.id) in game.get("players", {}):
                g = get_group(chat_id)
                active_games.append((chat_id, g, game))
        
        if not active_games:
            text = "🎮 Siz hech qanday o'yinda qatnashmaysiz.\n\nGuruhda admin bilan o'yin boshlang!"
            back_kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Orqaga", callback_data="menu:start")]
            ])
            await cb.message.edit_text(text, reply_markup=back_kb)
            return
        
        text = "🎮 Faol o'yinlar:\n\n"
        rows = []
        
        for chat_id, g, game in active_games:
            players_count = len(game["players"])
            phase = game["phase"]
            
            phase_text = {
                "idle": "🔴 Faol emas",
                "registration": "📝 Ro'yxat",
                "night": "🌙 Tun",
                "discussion": "🗣 Muhokama", 
                "day": "☀️ Kun",
                "afsun": "🧞‍♂️ Afsun"
            }.get(phase, phase)
            
            text += f"🏘 Guruh: {chat_id}\n"
            text += f"👥 O'yinchilar: {players_count}\n"
            text += f"📊 Holat: {phase_text}\n\n"
            
            rows.append([InlineKeyboardButton(
                text=f"🏘 Guruh {chat_id} ({players_count} o'yinchi)",
                callback_data=f"game_info:{chat_id}"
            )])
        
        rows.append([InlineKeyboardButton(text="🔄 Yangilash", callback_data="menu:game")])
        rows.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="menu:start")])
        
        await cb.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
        
    elif action == "roles":
        await cb.message.edit_text("🎭 O'yin rollari. Rolni bosing:", reply_markup=roles_kb())
        
    elif action == "top":
        users = load_users()
        arr = []
        for _, u in users.items():
            arr.append((u.get("wins", 0), u.get("games", 0), u.get("name", "User")))
        arr.sort(key=lambda x: (x[0], x[1]), reverse=True)
        top = arr[:10]
        if not top:
            text = "🏆 Top bo'sh."
        else:
            lines = ["🏆 TOP 10:"]
            for i, (w, g, name) in enumerate(top, 1):
                lines.append(f"{i}) {name} — 🎯 {w} | 🎲 {g}")
            text = "\n".join(lines)
        
        back_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Orqaga", callback_data="menu:start")]
        ])
        await cb.message.edit_text(text, reply_markup=back_kb)
        
    elif action == "shop":
        await cb.message.edit_text("🛒 Do'kon. Sotib olish uchun bosing:", reply_markup=shop_kb())
        
    elif action == "lang":
        u = get_user(cb.from_user.id, cb.from_user.full_name)
        cur = u.get("language", "uz")
        rows = []
        for code, name in LANGS.items():
            mark = "✅ " if code == cur else ""
            rows.append([InlineKeyboardButton(text=f"{mark}{name}", callback_data=f"setlang:{code}")])
        rows.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="menu:start")])
        await cb.message.edit_text("🌐 Tilni tanlang:", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
        
    elif action == "back":
        u = get_user(cb.from_user.id, cb.from_user.full_name)
        
        # Find games where user is participating
        user_games = []
        for chat_id, game in GAMES.items():
            if str(cb.from_user.id) in game.get("players", {}):
                user_games.append(chat_id)
        
        if not user_games:
            text = "❌ Siz hech qanday o'yinda qatnashmaysiz."
            back_kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Orqaga", callback_data="menu:start")]
            ])
            await cb.message.edit_text(text, reply_markup=back_kb)
            return
        
        if len(user_games) == 1:
            chat_id = user_games[0]
            text = f"🔙 Guruhga qaytish uchun tugmani bosing:"
            kb = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="🔙 Guruhga qaytish", url=f"https://t.me/c/{str(chat_id)[4:] if str(chat_id).startswith('-100') else chat_id}")],
                    [InlineKeyboardButton(text="🔙 Orqaga", callback_data="menu:start")]
                ]
            )
        else:
            rows = []
            for chat_id in user_games:
                rows.append([InlineKeyboardButton(
                    text=f"🏘 Guruh {chat_id}",
                    url=f"https://t.me/c/{str(chat_id)[4:] if str(chat_id).startswith('-100') else chat_id}"
                )])
            rows.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="menu:start")])
            text = "🔙 Qaysi guruhga qaytmoqchisiz?"
            kb = InlineKeyboardMarkup(inline_keyboard=rows)
        
        await cb.message.edit_text(text, reply_markup=kb)
        
    elif action == "help":
        help_text = (
            "📚 Mafia Bot Yordam\n\n"
            "🎮 O'yinni boshlash:\n"
            "1. Guruhda admin /game buyrug'ini yuboradi\n"
            "2. O'yinchilar 💡 Qo'shilish tugmasini bosadi\n"
            "3. Admin /start bilan o'yinni boshlaydi\n\n"
            "🎭 Rollar:\n"
            "• 🕵️ Komissar - Mafiyani topadi\n"
            "• 👨‍⚕️ Doktor - Davolaydi\n"
            "• 💃 Kezuvchi - Uxlatadi\n"
            "• 🤵 Mafiya - O'ldiradi\n"
            "• Va boshqa rollar...\n\n"
            "🛒 Do'kon:\n"
            "• Himoya, qurollar va boshqa narsalar\n\n"
            "🔙 Guruhga qaytish:\n"
            "O'yindagi holatingizni ko'rish va guruhga qaytish"
        )
        back_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Orqaga", callback_data="menu:start")]
        ])
        await cb.message.edit_text(help_text, reply_markup=back_kb)
        
    elif action == "start":
        # Return to main menu
        main_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="👤 Profil", callback_data="menu:profile")],
            [InlineKeyboardButton(text="🎮 O'yin", callback_data="menu:game")],
            [InlineKeyboardButton(text="🎭 Rollar", callback_data="menu:roles")],
            [InlineKeyboardButton(text="🏆 Top", callback_data="menu:top")],
            [InlineKeyboardButton(text="🛒 Do'kon", callback_data="menu:shop")],
            [InlineKeyboardButton(text="🌐 Til", callback_data="menu:lang")],
            [InlineKeyboardButton(text="🔙 Guruhga qaytish", callback_data="menu:back")],
            [InlineKeyboardButton(text="📚 Yordam", callback_data="menu:help")],
        ])
        await cb.message.edit_text(
            "👋 Mafia botga xush kelibsiz!\n\n"
            "Quyidagi tugmalardan foydalaning:",
            reply_markup=main_kb
        )


# ================= COMMANDS: PRIVATE =================
@dp.message(Command("start"))
async def private_start(msg: Message):
    get_user(msg.from_user.id, msg.from_user.full_name)
    
    # Main menu with inline buttons
    main_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤 Profil", callback_data="menu:profile")],
        [InlineKeyboardButton(text="🎮 O'yin", callback_data="menu:game")],
        [InlineKeyboardButton(text="🎭 Rollar", callback_data="menu:roles")],
        [InlineKeyboardButton(text="🏆 Top", callback_data="menu:top")],
        [InlineKeyboardButton(text="🛒 Do'kon", callback_data="menu:shop")],
        [InlineKeyboardButton(text="🌐 Til", callback_data="menu:lang")],
        [InlineKeyboardButton(text="🔙 Guruhga qaytish", callback_data="menu:back")],
        [InlineKeyboardButton(text="📚 Yordam", callback_data="menu:help")],
    ])
    
    await msg.answer(
        "👋 Mafia botga xush kelibsiz!\n\n"
        "Quyidagi tugmalardan foydalaning:",
        reply_markup=main_kb
    )


@dp.message(Command("profile"))
async def private_profile(msg: Message):
    u = get_user(msg.from_user.id, msg.from_user.full_name)
    
    # Create toggle buttons for items - 1xl size
    toggle_rows = []
    
    # Himoya toggle
    protect_status = "🟢 ON" if u.get('protect', 0) > 0 else "🔴 OFF"
    toggle_rows.append([InlineKeyboardButton(text=f"🛡 Himoya {protect_status}", callback_data="toggle:protect")])
    
    # Qotildan himoya toggle
    anti_killer_status = "🟢 ON" if u.get('anti_killer', 0) > 0 else "🔴 OFF"
    toggle_rows.append([InlineKeyboardButton(text=f"⛑️ Qotildan himoya {anti_killer_status}", callback_data="toggle:anti_killer")])
    
    # Ovoz berishni himoya qilish toggle
    vote_protect_status = "🟢 ON" if u.get('vote_protect', 0) > 0 else "🔴 OFF"
    toggle_rows.append([InlineKeyboardButton(text=f"⚖️ Ovoz berishni himoya qilish {vote_protect_status}", callback_data="toggle:vote_protect")])
    
    # Miltiq toggle
    gun_status = "🟢 ON" if u.get('gun', 0) > 0 else "🔴 OFF"
    toggle_rows.append([InlineKeyboardButton(text=f"🔫 Miltiq {gun_status}", callback_data="toggle:gun")])
    
    # Action buttons - matching screenshot layout
    action_rows = [
        [InlineKeyboardButton(text="🛒 Do'kon", callback_data="menu:shop")],
        [InlineKeyboardButton(text="💵 Xarid qilish", callback_data="buy:money")],
        [InlineKeyboardButton(text="💎 Xarid qilish", callback_data="buy:diamond")],
        [InlineKeyboardButton(text="👑 Premium guruhlar", callback_data="premium:groups")],
        [InlineKeyboardButton(text="📰 Yangiliklar", callback_data="news")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="menu:start")]
    ]
    
    profile_kb = InlineKeyboardMarkup(inline_keyboard=toggle_rows + action_rows)
    
    # Profile text matching screenshot format
    text = (
        f"⭐️ ID: {msg.from_user.id}\n"
        f"👤 Username: {msg.from_user.full_name}\n\n"
        f"💵 Dollar: {fmt_money(u.get('money', 0))}\n"
        f"💎 Olmos: {u.get('diamonds', 0)}\n\n"
        f"🛡 Himoya: {u.get('protect', 0)}\n"
        f"⛑️ Qotildan himoya: {u.get('anti_killer', 0)}\n"
        f"⚖️ Ovoz berishni himoya qilish: {u.get('vote_protect', 0)}\n"
        f"🔫 Miltiq: {u.get('gun', 0)}\n\n"
        f"🎭 Maska: {u.get('mask', 0)}\n"
        f"📁 Soxta hujjat: {u.get('fake_docs', 0)}\n"
        f"🃏 Keyingi o'yindagi rolingiz: {u.get('next_role', '-')}\n\n"
        f"🎯 G'alaba: {u.get('wins', 0)}\n"
        f"🎲 Jami o'yinlar: {u.get('games', 0)}"
    )
    
    await msg.answer(text, reply_markup=profile_kb)


def shop_kb() -> InlineKeyboardMarkup:
    rows: List[List[InlineKeyboardButton]] = []
    for key, it in SHOP_ITEMS.items():
        price = it["price"]
        cur = "💵" if it["currency"] == "money" else "💎"
        rows.append([InlineKeyboardButton(text=f"{it['title']} — {price}{cur}", callback_data=f"buy:{key}")])
    rows.append([InlineKeyboardButton(text="❌ Yopish", callback_data="shop_close")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


@dp.message(Command("shop"))
async def private_shop(msg: Message):
    get_user(msg.from_user.id, msg.from_user.full_name)
    await msg.answer("🛒 Do'kon. Sotib olish uchun bosing:", reply_markup=shop_kb())


@dp.message(Command("buy"))
async def private_buy(msg: Message):
    parts = msg.text.split()
    if len(parts) < 2:
        return await msg.answer("❌ Notog'ri format. Misol: /buy himoya 1")
    
    item_name = parts[1].lower()
    qty = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 1
    
    # Find item by name
    item_key = None
    for key, it in SHOP_ITEMS.items():
        if item_name in it['title'].lower() or item_name == key:
            item_key = key
            break
    
    if not item_key:
        return await msg.answer("❌ Bunday item yo'q")
    
    it = SHOP_ITEMS[item_key]
    u = get_user(msg.from_user.id, msg.from_user.full_name)
    field = it["field"]
    price = int(it["price"]) * qty
    cur = it["currency"]

    if cur == "money":
        have = int(u.get("money", 0))
        if have < price:
            return await msg.answer("❌ Dollar yetarli emas")
        u["money"] = have - price
    else:
        have = int(u.get("diamonds", 0))
        if have < price:
            return await msg.answer("❌ Olmos yetarli emas")
        u["diamonds"] = have - price

    u[field] = int(u.get(field, 0)) + (int(it.get("qty", 1)) * qty)
    update_user(msg.from_user.id, u)
    await msg.answer(f"✅ {qty} ta {it['title']} sotib olindi!")


@dp.callback_query(F.data == "shop_close")
async def cb_shop_close(cb: CallbackQuery):
    await cb.answer()
    try:
        await cb.message.edit_text("🛒 Do'kon. Sotib olish uchun bosing:", reply_markup=shop_kb())
    except Exception:
        pass


@dp.callback_query(F.data.startswith("buy:"))
async def cb_buy(cb: CallbackQuery):
    key = cb.data.split(":", 1)[1]
    it = SHOP_ITEMS.get(key)
    if not it:
        return await cb.answer("❌", show_alert=True)

    u = get_user(cb.from_user.id, cb.from_user.full_name)
    field = it["field"]
    qty = int(it.get("qty", 1))
    price = int(it["price"])
    cur = it["currency"]

    if cur == "money":
        have = int(u.get("money", 0))
        if have < price:
            return await cb.answer("❌ Dollar yetarli emas", show_alert=True)
        u["money"] = have - price
    else:
        have = int(u.get("diamonds", 0))
        if have < price:
            return await cb.answer("❌ Olmos yetarli emas", show_alert=True)
        u["diamonds"] = have - price

    u[field] = int(u.get(field, 0)) + qty
    update_user(cb.from_user.id, u)
    await cb.answer("✅ Sotib olindi", show_alert=True)
    try:
        await cb.message.edit_text("🛒 Do'kon. Sotib olish uchun bosing:", reply_markup=shop_kb())
    except Exception:
        pass


@dp.message(Command("top"))
async def private_top(msg: Message):
    users = load_users()
    arr = []
    for _, u in users.items():
        arr.append((u.get("wins", 0), u.get("games", 0), u.get("name", "User")))
    arr.sort(key=lambda x: (x[0], x[1]), reverse=True)
    top = arr[:10]
    if not top:
        return await msg.answer("🏆 Top bo'sh.")
    lines = ["🏆 TOP 10:"]
    for i, (w, g, name) in enumerate(top, 1):
        lines.append(f"{i}) {name} — 🎯 {w} | 🎲 {g}")
    await msg.answer("\n".join(lines))


@dp.message(Command("lang"), F.chat.type == "private")
async def private_lang(msg: Message):
    u = get_user(msg.from_user.id, msg.from_user.full_name)
    cur = u.get("language", "uz")
    rows = []
    for code, name in LANGS.items():
        mark = "✅ " if code == cur else ""
        rows.append([InlineKeyboardButton(text=f"{mark}{name}", callback_data=f"setlang:{code}")])
    await msg.answer("🌐 Tilni tanlang:", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))


@dp.callback_query(F.data.startswith("setlang:"))
async def cb_setlang(cb: CallbackQuery):
    code = cb.data.split(":", 1)[1]
    if code not in LANGS:
        return await cb.answer("❌", show_alert=True)
    if cb.message.chat.type == "private":
        u = get_user(cb.from_user.id, cb.from_user.full_name)
        u["language"] = code
        update_user(cb.from_user.id, u)
        await cb.answer("✅ Til saqlandi", show_alert=True)
        return await cb.message.edit_text("🌐 Til tanlandi. /start yozing.")
    # group lang set handled by settings panel /group handler
    return await cb.answer("❌", show_alert=True)


@dp.message(Command("roles"))
async def private_roles(msg: Message):
    await msg.answer("🎭 O'yin rollari. Rolni bosing:", reply_markup=roles_kb())


@dp.message(Command("game"))
async def private_game(msg: Message):
    u = get_user(msg.from_user.id, msg.from_user.full_name)
    
    # Find active games where user is participating
    active_games = []
    for chat_id, game in GAMES.items():
        if str(msg.from_user.id) in game.get("players", {}):
            g = get_group(chat_id)
            active_games.append((chat_id, g, game))
    
    if not active_games:
        await msg.answer("🎮 Siz hech qanday o'yinda qatnashmaysiz.\n\nGuruhda /game buyrug'ini bosing va ro'yxatdan o'ting!")
        return
    
    text = "🎮 Faol o'yinlar:\n\n"
    rows = []
    
    for chat_id, g, game in active_games:
        players_count = len(game["players"])
        phase = game["phase"]
        
        phase_text = {
            "idle": "🔴 Faol emas",
            "registration": "📝 Ro'yxat",
            "night": "🌙 Tun",
            "discussion": "🗣 Muhokama", 
            "day": "☀️ Kun",
            "afsun": "🧞‍♂️ Afsun"
        }.get(phase, phase)
        
        text += f"🏘 Guruh: {chat_id}\n"
        text += f"👥 O'yinchilar: {players_count}\n"
        text += f"📊 Holat: {phase_text}\n\n"
        
        rows.append([InlineKeyboardButton(
            text=f"🏘 Guruh {chat_id} ({players_count} o'yinchi)",
            callback_data=f"game_info:{chat_id}"
        )])
    
    rows.append([InlineKeyboardButton(text="🔄 Yangilash", callback_data="refresh_games")])
    await msg.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))


@dp.message(Command("back"))
async def private_back(msg: Message):
    u = get_user(msg.from_user.id, msg.from_user.full_name)
    
    # Find games where user is participating
    user_games = []
    for chat_id, game in GAMES.items():
        if str(msg.from_user.id) in game.get("players", {}):
            user_games.append(chat_id)
    
    if not user_games:
        await msg.answer("❌ Siz hech qanday o'yinda qatnashmaysiz.")
        return
    
    if len(user_games) == 1:
        chat_id = user_games[0]
        await msg.answer(f"🔙 Guruhga qaytish uchun tugmani bosing:", reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Guruhga qaytish", url=f"https://t.me/c/{str(chat_id)[4:] if str(chat_id).startswith('-100') else chat_id}")]
            ]
        ))
    else:
        rows = []
        for chat_id in user_games:
            rows.append([InlineKeyboardButton(
                text=f"🏘 Guruh {chat_id}",
                url=f"https://t.me/c/{str(chat_id)[4:] if str(chat_id).startswith('-100') else chat_id}"
            )])
        await msg.answer("🔙 Qaysi guruhga qaytmoqchisiz?", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))


@dp.callback_query(F.data == "refresh_games")
async def cb_refresh_games(cb: CallbackQuery):
    await cb.answer()
    # Trigger game command again to refresh
    await private_game(cb.message)


@dp.message(Command("stats"))
async def private_stats(msg: Message):
    u = get_user(msg.from_user.id, msg.from_user.full_name)
    
    text = (
        f"📊 {msg.from_user.full_name} statistikasi:\n\n"
        f"🎯 G'alabalar: {u.get('wins', 0)}\n"
        f"🎲 Jami o'yinlar: {u.get('games', 0)}\n"
        f"🏆 G'alaba foizi: {(u.get('wins', 0) / max(u.get('games', 1), 1)) * 100:.1f}%\n\n"
        f"💵 Jami daromad: {fmt_money(u.get('total_earned', 0))}\n"
        f"💸 Jami xarajat: {fmt_money(u.get('total_spent', 0))}\n"
        f"💰 Sof daromad: {fmt_money(u.get('total_earned', 0) - u.get('total_spent', 0))}\n\n"
        f"🎭 Eng ko'p o'ynagan rol: {u.get('most_played_role', 'Yo\'q')}\n"
        f"⏰ O'yin vaqti: {u.get('play_time', 0)} daqiqa"
    )
    
    await msg.answer(text)


@dp.message(Command("balance"))
async def private_balance(msg: Message):
    u = get_user(msg.from_user.id, msg.from_user.full_name)
    
    text = (
        f"💰 {msg.from_user.full_name} balansi:\n\n"
        f"💵 Dollar: {fmt_money(u.get('money', 0))}\n"
        f"💎 Olmos: {u.get('diamonds', 0)}\n\n"
        f"🎁 Kunlik bonus: {'✅ Olingan' if u.get('daily_claimed', 0) == datetime.datetime.now().date().toordinal() else '❌ Olinmagan'}\n"
        f"👑 Premium: {'✅ Faol' if u.get('premium', 0) > datetime.datetime.now().timestamp() else '❌ Faol emas'}"
    )
    
    await msg.answer(text)


@dp.message(Command("inventory"))
async def private_inventory(msg: Message):
    u = get_user(msg.from_user.id, msg.from_user.full_name)
    
    text = (
        f"🎒 {msg.from_user.full_name} inventari:\n\n"
        f"🛡 Himoya: {u.get('protect', 0)} ta\n"
        f"⛑️ Qotildan himoya: {u.get('anti_killer', 0)} ta\n"
        f"⚖️ Ovoz himoyasi: {u.get('vote_protect', 0)} ta\n"
        f"🔫 Miltiq: {u.get('gun', 0)} ta\n"
        f"🎭 Maska: {u.get('mask', 0)} ta\n"
        f"📁 Soxta hujjat: {u.get('fake_docs', 0)} ta\n\n"
        f"🃏 Keyingi rol: {u.get('next_role', '-')}"
    )
    
    await msg.answer(text)


@dp.message(Command("daily"))
async def private_daily(msg: Message):
    u = get_user(msg.from_user.id, msg.from_user.full_name)
    
    today = datetime.datetime.now().date().toordinal()
    if u.get('daily_claimed', 0) == today:
        await msg.answer("❌ Siz kunlik bonusni allaqachon oldingiz. Ertaga keling!")
        return
    
    # Give daily bonus
    daily_money = 1000
    daily_diamond = 5
    
    u['money'] = u.get('money', 0) + daily_money
    u['diamonds'] = u.get('diamonds', 0) + daily_diamond
    u['daily_claimed'] = today
    update_user(msg.from_user.id, u)
    
    text = (
        f"🎁 Kunlik bonus muvaffaqiyatli olindi!\n\n"
        f"💵 +{daily_money} dollar\n"
        f"💎 +{daily_diamond} olmos\n\n"
        f"Yangi balansingiz:\n"
        f"💵 {fmt_money(u.get('money', 0))}\n"
        f"💎 {u.get('diamonds', 0)}"
    )
    
    await msg.answer(text)


@dp.message(Command("transfer"))
async def private_transfer(msg: Message):
    parts = msg.text.split()
    if len(parts) < 3:
        return await msg.answer("❌ Notog'ri format. Misol: /transfer 123456789 1000")
    
    try:
        target_id = int(parts[1])
        amount = int(parts[2])
        
        if amount <= 0:
            return await msg.answer("❌ Miqdor musbat bo'lishi kerak.")
        
        u = get_user(msg.from_user.id, msg.from_user.full_name)
        if u.get('money', 0) < amount:
            return await msg.answer("❌ Sizda yetarli pul yo'q.")
        
        target = get_user(target_id, f"User_{target_id}")
        
        # Transfer money
        u['money'] = u.get('money', 0) - amount
        target['money'] = target.get('money', 0) + amount
        
        update_user(msg.from_user.id, u)
        update_user(target_id, target)
        
        await msg.answer(f"✅ {amount} dollar muvaffaqiyatli o'tkazildi!\n👤 Qabul qiluvchi: {target_id}")
        
        # Notify receiver
        try:
            await bot.send_message(
                target_id,
                f"💸 Siz {amount} dollar oldingiz!\n👤 Yuboruvchi: {msg.from_user.full_name}"
            )
        except Exception:
            pass
            
    except ValueError:
        await msg.answer("❌ Notog'ri ID yoki miqdor.")


@dp.message(Command("gift"))
async def private_gift(msg: Message):
    parts = msg.text.split()
    if len(parts) < 3:
        return await msg.answer("❌ Notog'ri format. Misol: /gift 123456789 himoya 2")
    
    try:
        target_id = int(parts[1])
        item_name = parts[2].lower()
        qty = int(parts[3]) if len(parts) > 3 else 1
        
        # Find item
        item_key = None
        for key, it in SHOP_ITEMS.items():
            if item_name in it['title'].lower() or item_name == key:
                item_key = key
                break
        
        if not item_key:
            return await msg.answer("❌ Bunday item yo'q.")
        
        u = get_user(msg.from_user.id, msg.from_user.full_name)
        it = SHOP_ITEMS[item_key]
        field = it["field"]
        
        if u.get(field, 0) < qty:
            return await msg.answer(f"❌ Sizda yetarli {it['title']} yo'q.")
        
        target = get_user(target_id, f"User_{target_id}")
        
        # Transfer item
        u[field] = u.get(field, 0) - qty
        target[field] = target.get(field, 0) + qty
        
        update_user(msg.from_user.id, u)
        update_user(target_id, target)
        
        await msg.answer(f"✅ {qty} ta {it['title']} sovg'a qilindi!\n👤 Qabul qiluvchi: {target_id}")
        
        # Notify receiver
        try:
            await bot.send_message(
                target_id,
                f"🎁 Siz {qty} ta {it['title']} oldingiz!\n👤 Yuboruvchi: {msg.from_user.full_name}"
            )
        except Exception:
            pass
            
    except (ValueError, IndexError):
        await msg.answer("❌ Notog'ri format. Misol: /gift 123456789 himoya 2")


@dp.message(Command("premium"))
async def private_premium(msg: Message):
    u = get_user(msg.from_user.id, msg.from_user.full_name)
    
    if u.get('premium', 0) > datetime.datetime.now().timestamp():
        premium_end = datetime.datetime.fromtimestamp(u.get('premium', 0))
        await msg.answer(f"👑 Sizda premium mavjud!\n📅 Tugash vaqti: {premium_end.strftime('%Y-%m-%d %H:%M')}")
        return
    
    text = (
        "👑 Premium paketlar:\n\n"
        "💎 1 oy - 100 olmos\n"
        "💎 3 oy - 250 olmos\n"
        "💎 6 oy - 450 olmos\n"
        "💎 1 yil - 800 olmos\n\n"
        "Premium afzalliklari:\n"
        "🎁 Kunlik bonus 2x ko'p\n"
        "💰 Do'kon chegirmalari\n"
        "🎭 Maxsus rollar\n"
        "⭐ Maxsim rivojlanish\n\n"
        "Sotib olish uchun: /premium_buy <oy_soni>"
    )
    
    await msg.answer(text)


@dp.message(Command("premium_buy"))
async def private_premium_buy(msg: Message):
    parts = msg.text.split()
    if len(parts) < 2:
        return await msg.answer("❌ Notog'ri format. Misol: /premium_buy 1")
    
    try:
        months = int(parts[1])
        if months <= 0 or months > 12:
            return await msg.answer("❌ Oy soni 1 dan 12 gacha bo'lishi kerak.")
        
        # Calculate price
        prices = {1: 100, 3: 250, 6: 450, 12: 800}
        price = prices.get(months, months * 100)
        
        u = get_user(msg.from_user.id, msg.from_user.full_name)
        
        if u.get('diamonds', 0) < price:
            return await msg.answer(f"❌ Sizda yetarli olmos yo'q. Kerak: {price} 💎")
        
        # Give premium
        current_time = datetime.datetime.now().timestamp()
        current_premium = u.get('premium', 0)
        new_premium = max(current_premium, current_time) + (months * 30 * 24 * 60 * 60)
        
        u['diamonds'] = u.get('diamonds', 0) - price
        u['premium'] = new_premium
        
        update_user(msg.from_user.id, u)
        
        premium_end = datetime.datetime.fromtimestamp(new_premium)
        await msg.answer(f"✅ Premium muvaffaqiyatli sotib olindi!\n📅 Tugash vaqti: {premium_end.strftime('%Y-%m-%d %H:%M')}")
        
    except ValueError:
        await msg.answer("❌ Notog'ri format. Misol: /premium_buy 1")


@dp.callback_query(F.data.startswith("game_info:"))
async def cb_game_info(cb: CallbackQuery):
    chat_id = int(cb.data.split(":", 1)[1])
    game = get_game(chat_id)
    
    if str(cb.from_user.id) not in game.get("players", {}):
        await cb.answer("❌ Siz bu o'yinda emassiz", show_alert=True)
        return
    
    g = get_group(chat_id)
    players_list = list(game["players"].values())
    
    text = f"🎮 O'yin ma'lumoti\n\n"
    text += f"🏘 Guruh: {chat_id}\n"
    text += f"👥 O'yinchilar: {len(players_list)}\n\n"
    
    text += "📋 Tirik o'yinchilar:\n"
    for i, name in enumerate(players_list, 1):
        uid = None
        for uid_str, player_name in game["players"].items():
            if player_name == name:
                uid = uid_str
                break
        
        if uid and uid in game.get("alive", []):
            role = game["roles"].get(uid, "Noma'lum")
            emoji = ROLE_EMOJI.get(role, "🎭")
            text += f"{i}. {emoji} {name}\n"
        else:
            text += f"{i}. ☠️ {name}\n"
    
    await cb.answer()
    await cb.message.edit_text(text, reply_markup=InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Guruhga qaytish", url=f"https://t.me/c/{str(chat_id)[4:] if str(chat_id).startswith('-100') else chat_id}")],
            [InlineKeyboardButton(text="🔄 Yangilash", callback_data=f"game_info:{chat_id}")]
        ]
    ))


# ================= CALLBACKS: GAME ACTIONS =================
def _in_group_game(chat_id: int, uid: int) -> Optional[Dict[str, Any]]:
    game = get_game(chat_id)
    if not game.get("started"):
        return None
    if str(uid) not in game.get("alive", []):
        return None
    return game


def _consume_item(uid: int, name: str, field: str, qty: int = 1) -> bool:
    u = get_user(uid, name)
    cur = int(u.get(field, 0))
    if cur < qty:
        return False
    u[field] = cur - qty
    update_user(uid, u)
    return True


@dp.callback_query(F.data.startswith("mk:"))
async def cb_mafia_kill(cb: CallbackQuery):
    # mk:{chat_id}:{target_uid}
    try:
        _, chat_id_s, target_uid = cb.data.split(":", 2)
        chat_id = int(chat_id_s)
    except Exception:
        return await cb.answer()

    game = _in_group_game(chat_id, cb.from_user.id)
    if not game:
        return await cb.answer("❌ O'yin topilmadi", show_alert=True)

    actor = str(cb.from_user.id)
    role = game["roles"].get(actor)
    if role not in {"Mafiya", "Don"}:
        return await cb.answer("❌ Siz mafia emassiz", show_alert=True)

    if game["phase"] != PHASE_NIGHT:
        return await cb.answer("❌ Hozir tun emas", show_alert=True)

    if target_uid not in game["alive"]:
        return await cb.answer("❌ Target tirik emas", show_alert=True)

    # one vote per mafia member
    game["mafia_votes"][actor] = target_uid
    await cb.answer("✅ Ovoz berildi", show_alert=True)


@dp.callback_query(F.data.startswith("kk:"))
async def cb_killer_kill(cb: CallbackQuery):
    # kk:{chat_id}:{target_uid}
    try:
        _, chat_id_s, target_uid = cb.data.split(":", 2)
        chat_id = int(chat_id_s)
    except Exception:
        return await cb.answer()

    game = _in_group_game(chat_id, cb.from_user.id)
    if not game:
        return await cb.answer("❌ O'yin topilmadi", show_alert=True)

    actor = str(cb.from_user.id)
    if game["roles"].get(actor) != "Qotil":
        return await cb.answer("❌ Siz qotil emassiz", show_alert=True)
    if game["phase"] != PHASE_NIGHT:
        return await cb.answer("❌ Hozir tun emas", show_alert=True)
    if target_uid not in game["alive"]:
        return await cb.answer("❌ Target tirik emas", show_alert=True)

    game["night"]["killer_kill"] = target_uid
    game["night"]["killer_by"] = actor
    await cb.answer("✅ Tanlandi", show_alert=True)


@dp.callback_query(F.data.startswith("heal:"))
async def cb_heal(cb: CallbackQuery):
    # heal:{chat_id}:{target_uid}
    try:
        _, chat_id_s, target_uid = cb.data.split(":", 2)
        chat_id = int(chat_id_s)
    except Exception:
        return await cb.answer()

    game = _in_group_game(chat_id, cb.from_user.id)
    if not game:
        return await cb.answer("❌ O'yin topilmadi", show_alert=True)

    actor = str(cb.from_user.id)
    if game["roles"].get(actor) != "Doktor":
        return await cb.answer("❌ Siz doktor emassiz", show_alert=True)
    if game["phase"] != PHASE_NIGHT:
        return await cb.answer("❌ Hozir tun emas", show_alert=True)
    if target_uid not in game["alive"]:
        return await cb.answer("❌ Target tirik emas", show_alert=True)

    # self-heal only once
    if target_uid == actor and actor in game.get("doc_self_used", set()):
        return await cb.answer("❌ O'zingizni 2-marta davolay olmaysiz", show_alert=True)

    game["night"]["heal"] = target_uid
    game["night"]["heal_by"] = actor
    if target_uid == actor:
        game["doc_self_used"].add(actor)
    await cb.answer("✅ Davolash tanlandi", show_alert=True)


@dp.callback_query(F.data.startswith("block:"))
async def cb_block(cb: CallbackQuery):
    # block:{chat_id}:{target_uid}
    try:
        _, chat_id_s, target_uid = cb.data.split(":", 2)
        chat_id = int(chat_id_s)
    except Exception:
        return await cb.answer()

    game = _in_group_game(chat_id, cb.from_user.id)
    if not game:
        return await cb.answer("❌ O'yin topilmadi", show_alert=True)

    actor = str(cb.from_user.id)
    if game["roles"].get(actor) != "Kezuvchi":
        return await cb.answer("❌ Siz kezuvchi emassiz", show_alert=True)
    if game["phase"] != PHASE_NIGHT:
        return await cb.answer("❌ Hozir tun emas", show_alert=True)
    if target_uid not in game["alive"]:
        return await cb.answer("❌ Target tirik emas", show_alert=True)

    # can't block commissar-like in this simplified mode
    if game["roles"].get(target_uid) in {"Komissar", "Serjant"}:
        return await cb.answer("❌ Komissarni uxlatmang", show_alert=True)

    game["night"]["block"] = target_uid
    await cb.answer("✅ Uxlatildi", show_alert=True)


@dp.callback_query(F.data.startswith("law:"))
async def cb_lawyer(cb: CallbackQuery):
    # law:{chat_id}:{target_uid}
    try:
        _, chat_id_s, target_uid = cb.data.split(":", 2)
        chat_id = int(chat_id_s)
    except Exception:
        return await cb.answer()

    game = _in_group_game(chat_id, cb.from_user.id)
    if not game:
        return await cb.answer("❌ O'yin topilmadi", show_alert=True)

    actor = str(cb.from_user.id)
    if game["roles"].get(actor) != "Advokat":
        return await cb.answer("❌ Siz advokat emassiz", show_alert=True)
    if game["phase"] != PHASE_NIGHT:
        return await cb.answer("❌ Hozir tun emas", show_alert=True)
    if target_uid not in game["alive"]:
        return await cb.answer("❌ Target tirik emas", show_alert=True)

    game["night"]["lawyer_protect"] = target_uid
    await cb.answer("✅ Himoya tanlandi", show_alert=True)


@dp.callback_query(F.data.startswith("watch:"))
async def cb_watch(cb: CallbackQuery):
    # watch:{chat_id}:{target_uid}
    try:
        _, chat_id_s, target_uid = cb.data.split(":", 2)
        chat_id = int(chat_id_s)
    except Exception:
        return await cb.answer()

    game = _in_group_game(chat_id, cb.from_user.id)
    if not game:
        return await cb.answer("❌ O'yin topilmadi", show_alert=True)

    actor = str(cb.from_user.id)
    if game["roles"].get(actor) != "Daydi":
        return await cb.answer("❌ Siz daydi emassiz", show_alert=True)
    if game["phase"] != PHASE_NIGHT:
        return await cb.answer("❌ Hozir tun emas", show_alert=True)
    if target_uid not in game["alive"]:
        return await cb.answer("❌ Target tirik emas", show_alert=True)

    game["night"]["watch"][actor] = target_uid
    await cb.answer("✅ Kuzatish tanlandi", show_alert=True)


@dp.callback_query(F.data.startswith("check:"))
async def cb_check(cb: CallbackQuery):
    # check:{chat_id}:{target_uid}
    try:
        _, chat_id_s, target_uid = cb.data.split(":", 2)
        chat_id = int(chat_id_s)
    except Exception:
        return await cb.answer()

    game = _in_group_game(chat_id, cb.from_user.id)
    if not game:
        return await cb.answer("❌ O'yin topilmadi", show_alert=True)

    actor = str(cb.from_user.id)
    if game["roles"].get(actor) not in {"Komissar", "Serjant"}:
        return await cb.answer("❌ Siz tekshiruvchi emassiz", show_alert=True)
    if game["phase"] != PHASE_NIGHT:
        return await cb.answer("❌ Hozir tun emas", show_alert=True)
    if target_uid not in game["alive"]:
        return await cb.answer("❌ Target tirik emas", show_alert=True)

    # block prevents actor's action
    if game["night"].get("block") == actor:
        return await cb.answer("😴 Siz uxlatilgansiz", show_alert=True)

    target_role = game["roles"].get(target_uid, "—")
    mafia_roles = {"Mafiya", "Don", "Advokat"}
    seen_as_mafia = target_role in mafia_roles

    # deception: lawyer protect OR mask/fake_docs makes mafia look "Tinch"
    lawyer_target = game["night"].get("lawyer_protect")
    if seen_as_mafia and lawyer_target == target_uid:
        seen_as_mafia = False

    # one-time mask / fake_docs consumption for any check (Baku-like "protect from check")
    if seen_as_mafia:
        used = False
        try:
            used = _consume_item(int(target_uid), game["players"].get(target_uid, "User"), "mask", 1)
        except Exception:
            used = False
        if not used:
            try:
                used = _consume_item(int(target_uid), game["players"].get(target_uid, "User"), "fake_docs", 1)
            except Exception:
                used = False
        if used:
            seen_as_mafia = False

    result = "Mafiya" if seen_as_mafia else "Tinch"
    await cb.answer("✅ Tekshirildi", show_alert=True)
    await safe_dm(actor, f"🕵️ Tekshiruv natijasi: {game['players'][target_uid]} — {result}")


@dp.callback_query(F.data.startswith("vote:"))
async def cb_vote(cb: CallbackQuery):
    # vote:{chat_id}:{target_uid}
    try:
        _, chat_id_s, target_uid = cb.data.split(":", 2)
        chat_id = int(chat_id_s)
    except Exception:
        return await cb.answer()

    game = _in_group_game(chat_id, cb.from_user.id)
    if not game:
        return await cb.answer("❌ O'yin topilmadi", show_alert=True)

    voter = str(cb.from_user.id)
    if game["phase"] != PHASE_DAY:
        return await cb.answer("❌ Hozir ovoz bosqichi emas", show_alert=True)
    if voter not in game["alive"]:
        return await cb.answer("❌ Siz tirik emasiz", show_alert=True)
    if target_uid not in game["alive"]:
        return await cb.answer("❌ Target tirik emas", show_alert=True)
    if target_uid == voter:
        return await cb.answer("❌ O'zingizga ovoz berolmaysiz", show_alert=True)

    game["votes"][voter] = target_uid
    await cb.answer("✅ Ovoz berildi", show_alert=True)


@dp.callback_query(F.data.startswith("afsun:"))
async def cb_afsun(cb: CallbackQuery):
    # afsun:{chat_id}:{target_uid}
    try:
        _, chat_id_s, target_uid = cb.data.split(":", 2)
        chat_id = int(chat_id_s)
    except Exception:
        return await cb.answer()

    game = get_game(chat_id)
    actor = str(cb.from_user.id)
    if game.get("phase") != PHASE_AFSUN or game.get("afsun_revenge") != actor:
        return await cb.answer("❌", show_alert=True)
    if target_uid not in game.get("alive", []):
        return await cb.answer("❌ Target tirik emas", show_alert=True)
    if target_uid == actor:
        return await cb.answer("❌", show_alert=True)

    game["afsun_target"] = target_uid
    await cb.answer("✅ Tanlandi", show_alert=True)


@dp.callback_query(F.data.startswith("roleinfo:"))
async def cb_roleinfo(cb: CallbackQuery):
    role = cb.data.split(":", 1)[1]
    emo = ROLE_EMOJI.get(role, "🎭")
    desc = ROLE_DESC_UZ.get(role, "—")
    await cb.answer()
    await cb.message.edit_text(f"{emo} {role}\n\n{desc}", reply_markup=roles_kb())


@dp.callback_query(F.data == "roles_close")
async def cb_roles_close(cb: CallbackQuery):
    await cb.answer()
    try:
        main_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="👤 Profil", callback_data="menu:profile")],
            [InlineKeyboardButton(text="🎮 O'yin", callback_data="menu:game")],
            [InlineKeyboardButton(text="🎭 Rollar", callback_data="menu:roles")],
            [InlineKeyboardButton(text="🏆 Top", callback_data="menu:top")],
            [InlineKeyboardButton(text="🛒 Do'kon", callback_data="menu:shop")],
            [InlineKeyboardButton(text="🌐 Til", callback_data="menu:lang")],
            [InlineKeyboardButton(text="🔙 Guruhga qaytish", callback_data="menu:back")],
            [InlineKeyboardButton(text="📚 Yordam", callback_data="menu:help")],
        ])
        await cb.message.edit_text(
            "👋 Mafia botga xush kelibsiz!\n\n"
            "Quyidagi tugmalardan foydalaning:",
            reply_markup=main_kb
        )
    except Exception:
        pass


# ================= GROUP INLINE MENU =================
@dp.message(Command("menu"), F.chat.type.in_({"group", "supergroup"}))
async def group_menu(msg: Message):
    if not await is_admin(msg.chat.id, msg.from_user.id):
        return  # Admin bo'lmasa javob bermaymiz
    
    admin_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎮 Ro'yxat boshlash", callback_data="group:game")],
        [InlineKeyboardButton(text="🚀 O'yinni boshlash", callback_data="group:start")],
        [InlineKeyboardButton(text="🛑 O'yinni to'xtatish", callback_data="group:stop")],
        [InlineKeyboardButton(text="⏰ Vaqtni uzaytirish", callback_data="group:extend")],
        [InlineKeyboardButton(text="👊 Kik qilish", callback_data="group:kick")],
        [InlineKeyboardButton(text="💎 Olmos berish", callback_data="group:give")],
        [InlineKeyboardButton(text="👥 Jamoa o'yini", callback_data="group:teamgame")],
        [InlineKeyboardButton(text="⚙️ Sozlamalar", callback_data="group:settings")],
    ])
    
    await msg.answer("🎮 Admin menyu:", reply_markup=admin_kb)

@dp.callback_query(F.data.startswith("group:"))
async def cb_group_menu(cb: CallbackQuery):
    action = cb.data.split(":", 1)[1]
    chat_id = cb.message.chat.id
    
    if not await is_admin(chat_id, cb.from_user.id):
        return await cb.answer("❌ Faqat admin.", show_alert=True)
    
    await cb.answer()
    
    if action == "game":
        # Trigger game registration
        await group_game_register(cb.message)
    elif action == "start":
        success, result = await start_game_func(chat_id)
        if success and result:
            await cb.message.answer(result)
        else:
            await cb.answer(result, show_alert=True)
    elif action == "stop":
        game = get_game(chat_id)
        t = game.get("loop_task")
        if t and not t.done():
            t.cancel()
        GAMES.pop(chat_id, None)
        await cb.message.answer("🛑 O'yin to'xtatildi va tozalandi.")
    elif action == "extend":
        game = get_game(chat_id)
        if game["phase"] != PHASE_REG or game["started"]:
            await cb.answer("❌ Hozir ro'yxat emas.", show_alert=True)
            return
        g = get_group(chat_id)
        # +30s extend: old deadline ustiga qo'shamiz (agar o'tib ketgan bo'lsa, hozirdan boshlab)
        now = float(asyncio.get_event_loop().time())
        old_deadline = float(game.get("reg_deadline", 0.0))
        base = max(old_deadline, now)
        game["reg_deadline"] = base + 30.0
        await cb.message.answer("✅ Ro'yxat 30 soniyaga uzaytirildi.")
    elif action == "kick":
        await cb.message.edit_text(
            "👊 Kik qilish uchun user ID yuboring:\n\n"
            "Misol: /kick 123456789",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Orqaga", callback_data="group:menu")]
            ])
        )
    elif action == "give":
        await cb.message.edit_text(
            "💎 Olmos berish uchun:\n\n"
            "Misol: /give 123456789 10",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Orqaga", callback_data="group:menu")]
            ])
        )
    elif action == "teamgame":
        g = get_group(chat_id)
        if not g.get("allow_teamgame", True):
            await cb.answer("❌ TeamGame o'chiq (settings'da).", show_alert=True)
            return
        game = get_game(chat_id)
        if game.get("started") or game["phase"] != PHASE_REG:
            await cb.answer("❌ Avval ro'yxat qiling.", show_alert=True)
            return
        players = list(game["players"].keys())
        if len(players) < 4:
            await cb.answer("❌ Kamida 4 o'yinchi kerak.", show_alert=True)
            return
        random.shuffle(players)
        mid = len(players) // 2
        blue = players[:mid]
        red = players[mid:]
        game["teams"] = {"blue": blue, "red": red}
        await cb.message.answer(
            "🔵 Ko'k jamoa:\n" + "\n".join(f"- {game['players'][u]}" for u in blue) +
            "\n\n🔴 Qizil jamoa:\n" + "\n".join(f"- {game['players'][u]}" for u in red)
        )
    elif action == "settings":
        await group_settings_panel(cb.message)
    elif action == "lang":
        # Language functionality removed
        await cb.answer("🌐 Til sozlamalari o'chirilgan", show_alert=True)
        return
    elif action == "menu":
        admin_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎮 Ro'yxat boshlash", callback_data="group:game")],
            [InlineKeyboardButton(text="🚀 O'yinni boshlash", callback_data="group:start")],
            [InlineKeyboardButton(text="🛑 O'yinni to'xtatish", callback_data="group:stop")],
            [InlineKeyboardButton(text="⏰ Vaqtni uzaytirish", callback_data="group:extend")],
            [InlineKeyboardButton(text="👊 Kik qilish", callback_data="group:kick")],
            [InlineKeyboardButton(text="💎 Olmos berish", callback_data="group:give")],
            [InlineKeyboardButton(text="👥 Jamoa o'yini", callback_data="group:teamgame")],
            [InlineKeyboardButton(text="⚙️ Sozlamalar", callback_data="group:settings")],
        ])
        await cb.message.edit_text("🎮 Admin menyu:", reply_markup=admin_kb)


# ================= COMMANDS: GROUP =================
@dp.message(Command("start"), F.chat.type.in_({"group", "supergroup"}))
async def group_start_admin(msg: Message):
    if not await is_admin(msg.chat.id, msg.from_user.id):
        return  # Admin bo'lmasa javob bermaymiz
    
    success, result = await start_game_func(msg.chat.id)
    
    try:
        await bot.send_message(msg.from_user.id, result if result else ("❌ Xatolik" if not success else "✅ Muvaffaqiyatli"))
    except Exception:
        pass


@dp.message(Command("game"), F.chat.type.in_({"group", "supergroup"}))
async def group_game_register(msg: Message):
    if not await is_admin(msg.chat.id, msg.from_user.id):
        return await msg.answer("❌ Faqat admin /game bilan ro'yxat ochadi.")
    game = get_game(msg.chat.id)
    if game["started"]:
        return await msg.answer("❌ O'yin boshlangan. /stop qiling.")

    g = get_group(msg.chat.id)
    game["started"] = False
    game["phase"] = PHASE_REG
    game["players"].clear()
    game["roles"].clear()
    game["alive"].clear()
    game["votes"].clear()
    game["teams"] = None

    game["reg_deadline"] = float(asyncio.get_event_loop().time()) + int(g["registration_seconds"])

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💡 Qo'shilish", callback_data=f"join:{msg.chat.id}")]
    ])
    
    # Initial game message with proper formatting
    game_msg = await msg.answer(
        f"� Ro'yxatdan o'tish davom etmoqda\n\n"
        f"📋 Ro'yxatdan o'tganlar:\n"
        f"Hali hech kim qo'shilmadi\n\n"
        f"Jami 0ta odam.",
        reply_markup=kb
    )
    
    # Store message ID for updates
    game["reg_message_id"] = game_msg.message_id


@dp.callback_query(F.data.startswith("join:"))
async def cb_join(cb: CallbackQuery):
    chat_id = int(cb.data.split(":", 1)[1])
    game = get_game(chat_id)
    if game["phase"] != PHASE_REG or game["started"]:
        return await cb.answer("❌ Ro'yxat yopiq.", show_alert=True)

    # deadline check (monotonic)
    now = asyncio.get_event_loop().time()
    if now > float(game.get("reg_deadline", 0)):
        return await cb.answer("⏳ Ro'yxat tugadi.", show_alert=True)

    uid = str(cb.from_user.id)
    if uid in game["players"]:
        return await cb.answer("✅ Siz allaqachon qo'shilgansiz.", show_alert=True)

    game["players"][uid] = cb.from_user.full_name
    if uid not in game["alive"]:
        game["alive"].append(uid)

    await cb.answer("✅ Qo'shildingiz. /start (admin boshlasa) kuting.", show_alert=True)
    
    # Send private message with return button
    try:
        await bot.send_message(
            int(uid),
            f"✅ Siz guruh {chat_id} o'yiniga qo'shildingiz!\n\n"
            f"🎮 O'yin boshlanganda sizga rol beriladi.\n"
            f"🔙 Tugmani bosib guruhga qaytishingiz mumkin:",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(
                        text="🔙 Guruhga qaytish",
                        url=f"https://t.me/c/{str(chat_id)[4:] if str(chat_id).startswith('-100') else chat_id}"
                    )]
                ]
            )
        )
    except Exception:
        pass
    
    # Update group message with players list
    try:
        players_list = list(game["players"].values())
        if players_list:
            players_text = "\n".join([f"{i+1}. {name}" for i, name in enumerate(players_list)])
            total_text = f"Jami {len(players_list)}ta odam."
        else:
            players_text = "Hali hech kim qo'shilmadi"
            total_text = "Jami 0ta odam."
        
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=game.get("reg_message_id"),
            text=f"� Ro'yxatdan o'tish davom etmoqda\n\n"
                 f"📋 Ro'yxatdan o'tganlar:\n"
                 f"{players_text}\n\n"
                 f"{total_text}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💡 Qo'shilish", callback_data=f"join:{chat_id}")]
            ])
        )
    except Exception:
        pass


# ================= COMMANDS: GROUP =================
@dp.message(Command("start"), F.chat.type.in_({"group", "supergroup"}))
async def group_start_admin(msg: Message):
    if not await is_admin(msg.chat.id, msg.from_user.id):
        return  # Admin bo'lmasa javob bermaymiz
    
    success, result = await start_game_func(msg.chat.id)
    
    try:
        await bot.send_message(msg.from_user.id, result if result else ("❌ Xatolik" if not success else "✅ Muvaffaqiyatli"))
    except Exception:
        pass


@dp.message(Command("game"), F.chat.type.in_({"group", "supergroup"}))
async def group_game_register(msg: Message):
    if not await is_admin(msg.chat.id, msg.from_user.id):
        return  # Admin bo'lmasa javob bermaymiz
    
    # Guruhga hech qanday xabar yubormaymiz, faqat o'yinni boshlaymiz
    game = get_game(msg.chat.id)
    if game["started"]:
        try:
            await bot.send_message(msg.from_user.id, "❌ O'yin boshlangan. /stop qiling.")
        except Exception:
            pass
        return

    g = get_group(msg.chat.id)
    game["started"] = False
    game["phase"] = PHASE_REG
    game["players"].clear()
    game["roles"].clear()
    game["alive"].clear()
    game["votes"].clear()
    game["teams"] = None

    game["reg_deadline"] = float(asyncio.get_event_loop().time()) + int(g["registration_seconds"])

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💡 Qo'shilish", callback_data=f"join:{msg.chat.id}")]
    ])
    
    # Faqat guruhda ro'yxat xabarini yuboramiz
    game_msg = await msg.answer(
        f"📝 Ro'yxatdan o'tish davom etmoqda\n\n"
        f"📋 Ro'yxatdan o'tganlar:\n"
        f"Hali hech kim qo'shilmadi\n\n"
        f"Jami 0ta odam.",
        reply_markup=kb
    )
    
    game["reg_message_id"] = game_msg.message_id
    
    # Adminga shaxsiy xabar
    try:
        await bot.send_message(msg.from_user.id, f"✅ Guruh {msg.chat.id} da ro'yxat boshlandi!")
    except Exception:
        pass


@dp.callback_query(F.data.startswith("join:"))
async def cb_join(cb: CallbackQuery):
    chat_id = int(cb.data.split(":", 1)[1])
    game = get_game(chat_id)
    if game["phase"] != PHASE_REG or game["started"]:
        return await cb.answer("❌ Ro'yxat yopiq.", show_alert=True)

    # deadline check (monotonic)
    now = asyncio.get_event_loop().time()
    if now > float(game.get("reg_deadline", 0)):
        return await cb.answer("⏳ Ro'yxat tugadi.", show_alert=True)

    uid = str(cb.from_user.id)
    if uid in game["players"]:
        return await cb.answer("✅ Siz allaqachon qo'shilgansiz.", show_alert=True)

    game["players"][uid] = cb.from_user.full_name
    if uid not in game["alive"]:
        game["alive"].append(uid)

    await cb.answer("✅ Qo'shildingiz. /start (admin boshlasa) kuting.", show_alert=True)
    
    # Send private message with return button
    try:
        await bot.send_message(
            int(uid),
            f"✅ Siz guruh {chat_id} o'yiniga qo'shildingiz!\n\n"
            f"🎮 O'yin boshlanganda sizga rol beriladi.\n"
            f"🔙 Tugmani bosib guruhga qaytishingiz mumkin:",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(
                        text="🔙 Guruhga qaytish",
                        url=f"https://t.me/c/{str(chat_id)[4:] if str(chat_id).startswith('-100') else chat_id}"
                    )]
                ]
            )
        )
    except Exception:
        pass
    
    # Update group message with players list
    try:
        players_list = list(game["players"].values())
        if players_list:
            players_text = "\n".join([f"{i+1}. {name}" for i, name in enumerate(players_list)])
            total_text = f"Jami {len(players_list)}ta odam."
        else:
            players_text = "Hali hech kim qo'shilmadi"
            total_text = "Jami 0ta odam."
        
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=game.get("reg_message_id"),
            text=f"📝 Ro'yxatdan o'tish davom etmoqda\n\n"
                 f"📋 Ro'yxatdan o'tganlar:\n"
                 f"{players_text}\n\n"
                 f"{total_text}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💡 Qo'shilish", callback_data=f"join:{chat_id}")]
            ])
        )
    except Exception:
        pass


@dp.message(Command("extend"), F.chat.type.in_({"group", "supergroup"}))
async def group_extend(msg: Message):
    if not await is_admin(msg.chat.id, msg.from_user.id):
        return  # Admin bo'lmasa javob bermaymiz
    
    game = get_game(msg.chat.id)
    if game["phase"] != PHASE_REG or game["started"]:
        try:
            await bot.send_message(msg.from_user.id, "❌ Hozir ro'yxat emas.")
        except Exception:
            pass
        return
    
    g = get_group(msg.chat.id)
    # +30s extend: old deadline ustiga qo'shamiz (agar o'tib ketgan bo'lsa, hozirdan boshlab)
    now = float(asyncio.get_event_loop().time())
    old_deadline = float(game.get("reg_deadline", 0.0))
    base = max(old_deadline, now)
    game["reg_deadline"] = base + 30.0
    
    try:
        await bot.send_message(msg.from_user.id, "✅ Ro'yxat 30 soniyaga uzaytirildi.")
    except Exception:
        pass


@dp.message(Command("leave"), F.chat.type.in_({"group", "supergroup"}))
async def group_leave(msg: Message):
    game = get_game(msg.chat.id)
    uid = str(msg.from_user.id)
    if game.get("started"):
        try:
            await bot.send_message(msg.from_user.id, "❌ O'yin boshlangan. Chiqib bo'lmaydi.")
        except Exception:
            pass
        return
    if uid not in game["players"]:
        try:
            await bot.send_message(msg.from_user.id, "❌ Siz ro'yxatda yo'qsiz.")
        except Exception:
            pass
        return
    
    game["players"].pop(uid, None)
    if uid in game["alive"]:
        game["alive"].remove(uid)
    
    try:
        await bot.send_message(msg.from_user.id, "✅ Siz ro'yxatdan chiqdingiz.")
    except Exception:
        pass


@dp.message(Command("kick"), F.chat.type.in_({"group", "supergroup"}))
async def group_kick(msg: Message):
    if not await is_admin(msg.chat.id, msg.from_user.id):
        return  # Admin bo'lmasa javob bermaymiz
    
    game = get_game(msg.chat.id)
    if game.get("started"):
        try:
            await bot.send_message(msg.from_user.id, "❌ O'yin boshlangan.")
        except Exception:
            pass
        return
    
    parts = msg.text.split()
    if len(parts) != 2 or not parts[1].isdigit():
        try:
            await bot.send_message(msg.from_user.id, "Misol: /kick 123456789")
        except Exception:
            pass
        return
    
    target = parts[1]
    if target not in game["players"]:
        try:
            await bot.send_message(msg.from_user.id, "❌ Bunday user ro'yxatda yo'q.")
        except Exception:
            pass
        return
    
    name = game["players"].get(target, target)
    game["players"].pop(target, None)
    if target in game["alive"]:
        game["alive"].remove(target)
    game["roles"].pop(target, None)
    
    try:
        await bot.send_message(msg.from_user.id, f"✅ Kick: {name}")
    except Exception:
        pass


@dp.message(Command("give"), F.chat.type.in_({"group", "supergroup"}))
async def group_give(msg: Message):
    if not await is_admin(msg.chat.id, msg.from_user.id):
        return  # Admin bo'lmasa javob bermaymiz
    
    parts = msg.text.split()
    if len(parts) != 3 or not parts[1].isdigit() or not parts[2].isdigit():
        try:
            await bot.send_message(msg.from_user.id, "Misol: /give 123456789 10  (diamonds)")
        except Exception:
            pass
        return
    
    uid = int(parts[1])
    amount = int(parts[2])
    if amount <= 0:
        try:
            await bot.send_message(msg.from_user.id, "❌ Noto'g'ri miqdor.")
        except Exception:
            pass
        return
    
    u = get_user(uid, str(uid))
    u["diamonds"] = u.get("diamonds", 0) + amount
    update_user(uid, u)
    
    try:
        await bot.send_message(msg.from_user.id, f"✅ {uid} ga {amount}💎 berildi.")
    except Exception:
        pass


@dp.message(Command("teamgame"), F.chat.type.in_({"group", "supergroup"}))
async def group_teamgame(msg: Message):
    if not await is_admin(msg.chat.id, msg.from_user.id):
        return  # Admin bo'lmasa javob bermaymiz
    
    g = get_group(msg.chat.id)
    if not g.get("allow_teamgame", True):
        try:
            await bot.send_message(msg.from_user.id, "❌ TeamGame o'chiq (settings'da).")
        except Exception:
            pass
        return
    
    game = get_game(msg.chat.id)
    if game.get("started") or game["phase"] != PHASE_REG:
        try:
            await bot.send_message(msg.from_user.id, "❌ Avval ro'yxat qiling.")
        except Exception:
            pass
        return
    
    players = list(game["players"].keys())
    if len(players) < 4:
        try:
            await bot.send_message(msg.from_user.id, "❌ Kamida 4 o'yinchi kerak.")
        except Exception:
            pass
        return
    
    random.shuffle(players)
    mid = len(players) // 2
    blue = players[:mid]
    red = players[mid:]
    game["teams"] = {"blue": blue, "red": red}
    
    text = (
        "🔵 Ko'k jamoa:\n" + "\n".join(f"- {game['players'][u]}" for u in blue) +
        "\n\n🔴 Qizil jamoa:\n" + "\n".join(f"- {game['players'][u]}" for u in red)
    )
    
    try:
        await bot.send_message(msg.from_user.id, text)
    except Exception:
        pass


@dp.message(Command("stop"), F.chat.type.in_({"group", "supergroup"}))
async def group_stop(msg: Message):
    if not await is_admin(msg.chat.id, msg.from_user.id):
        return  # Admin bo'lmasa javob bermaymiz
    
    game = get_game(msg.chat.id)
    t = game.get("loop_task")
    if t and not t.done():
        t.cancel()
    GAMES.pop(msg.chat.id, None)
    
    try:
        await bot.send_message(msg.from_user.id, "🛑 O'yin to'xtatildi va tozalandi.")
    except Exception:
        pass


# ================= REMOVED GROUP LANGUAGE HANDLER =================
# Group language functionality completely removed


@dp.message(Command("roles"), F.chat.type.in_({"group", "supergroup"}))
async def group_roles(msg: Message):
    if not await is_admin(msg.chat.id, msg.from_user.id):
        return  # Admin bo'lmasa javob bermaymiz
    
    try:
        await bot.send_message(
            msg.from_user.id,
            "🎭 O'yin rollari. Rolni bosing:",
            reply_markup=roles_kb()
        )
    except Exception:
        pass


@dp.message(Command("profile"), F.chat.type.in_({"group", "supergroup"}))
async def group_profile(msg: Message):
    if not await is_admin(msg.chat.id, msg.from_user.id):
        return  # Admin bo'lmasa javob bermaymiz
    
    u = get_user(msg.from_user.id, msg.from_user.full_name)
    
    # Create toggle buttons for items - 1xl size
    toggle_rows = []
    
    # Himoya toggle
    protect_status = "🟢 ON" if u.get('protect', 0) > 0 else "🔴 OFF"
    toggle_rows.append([InlineKeyboardButton(text=f"🛡 Himoya {protect_status}", callback_data="toggle:protect")])
    
    # Qotildan himoya toggle
    anti_killer_status = "🟢 ON" if u.get('anti_killer', 0) > 0 else "🔴 OFF"
    toggle_rows.append([InlineKeyboardButton(text=f"⛑️ Qotildan himoya {anti_killer_status}", callback_data="toggle:anti_killer")])
    
    # Ovoz berishni himoya qilish toggle
    vote_protect_status = "🟢 ON" if u.get('vote_protect', 0) > 0 else "🔴 OFF"
    toggle_rows.append([InlineKeyboardButton(text=f"⚖️ Ovoz berishni himoya qilish {vote_protect_status}", callback_data="toggle:vote_protect")])
    
    # Miltiq toggle
    gun_status = "🟢 ON" if u.get('gun', 0) > 0 else "🔴 OFF"
    toggle_rows.append([InlineKeyboardButton(text=f"🔫 Miltiq {gun_status}", callback_data="toggle:gun")])
    
    # Action buttons - matching screenshot layout without back button
    action_rows = [
        [InlineKeyboardButton(text="🛒 Do'kon", callback_data="menu:shop")],
        [InlineKeyboardButton(text="💵 Xarid qilish", callback_data="buy:money")],
        [InlineKeyboardButton(text="💎 Xarid qilish", callback_data="buy:diamond")],
        [InlineKeyboardButton(text="👑 Premium guruhlar", callback_data="premium:groups")],
        [InlineKeyboardButton(text="📰 Yangiliklar", callback_data="news")],
    ]
    
    profile_kb = InlineKeyboardMarkup(inline_keyboard=toggle_rows + action_rows)
    
    # Profile text matching screenshot format
    text = (
        f"⭐️ ID: {msg.from_user.id}\n"
        f"👤 Username: {msg.from_user.full_name}\n\n"
        f"💵 Dollar: {fmt_money(u.get('money', 0))}\n"
        f"💎 Olmos: {u.get('diamonds', 0)}\n\n"
        f"🛡 Himoya: {u.get('protect', 0)}\n"
        f"⛑️ Qotildan himoya: {u.get('anti_killer', 0)}\n"
        f"⚖️ Ovoz berishni himoya qilish: {u.get('vote_protect', 0)}\n"
        f"🔫 Miltiq: {u.get('gun', 0)}\n\n"
        f"🎭 Maska: {u.get('mask', 0)}\n"
        f"📁 Soxta hujjat: {u.get('fake_docs', 0)}\n"
        f"🃏 Keyingi o'yindagi rolingiz: {u.get('next_role', '-')}\n\n"
        f"🎯 G'alaba: {u.get('wins', 0)}\n"
        f"🎲 Jami o'yinlar: {u.get('games', 0)}"
    )
    
    try:
        await bot.send_message(msg.from_user.id, text, reply_markup=profile_kb)
    except Exception:
        pass


@dp.message(Command("shop"), F.chat.type.in_({"group", "supergroup"}))
async def group_shop(msg: Message):
    if not await is_admin(msg.chat.id, msg.from_user.id):
        return  # Admin bo'lmasa javob bermaymiz
    
    try:
        await bot.send_message(
            msg.from_user.id,
            "🛒 Do'kon. Sotib olish uchun bosing:",
            reply_markup=shop_kb()
        )
    except Exception:
        pass


@dp.message(Command("top"), F.chat.type.in_({"group", "supergroup"}))
async def group_top(msg: Message):
    if not await is_admin(msg.chat.id, msg.from_user.id):
        return  # Admin bo'lmasa javob bermaymiz
    
    users = load_users()
    arr = []
    for _, u in users.items():
        arr.append((u.get("wins", 0), u.get("games", 0), u.get("name", "User")))
    arr.sort(key=lambda x: (x[0], x[1]), reverse=True)
    top = arr[:10]
    if not top:
        text = "🏆 Top bo'sh."
    else:
        lines = ["🏆 TOP 10:"]
        for i, (w, g, name) in enumerate(top, 1):
            lines.append(f"{i}) {name} — 🎯 {w} | 🎲 {g}")
        text = "\n".join(lines)
    
    try:
        await bot.send_message(msg.from_user.id, text)
    except Exception:
        pass


@dp.message(Command("help"), F.chat.type.in_({"group", "supergroup"}))
async def group_help(msg: Message):
    if not await is_admin(msg.chat.id, msg.from_user.id):
        return  # Admin bo'lmasa javob bermaymiz
    
    help_text = (
        "📚 Mafia Bot Yordam\n\n"
        "🎮 O'yinni boshlash:\n"
        "1. Admin /game bilan ro'yxat ochadi\n"
        "2. O'yinchilar 💡 Qo'shilish tugmasini bosadi\n"
        "3. Admin /start bilan o'yinni boshlaydi\n\n"
        "🔧 Admin buyruqlari:\n"
        "• /game - Ro'yxat boshlash\n"
        "• /start - O'yinni boshlash\n"
        "• /stop - O'yinni to'xtatish\n"
        "• /extend - Vaqtni uzaytirish\n"
        "• /kick - O'yinchini kik qilish\n"
        "• /give - Olmos berish\n"
        "• /teamgame - Jamoa o'yini\n"
        "• /settings - Sozlamalar\n"
        "• /menu - Admin menyu\n\n"
        "👤 Foydalanuvchi buyruqlari:\n"
        "• /leave - O'yindan chiqish\n"
        "• /profile - Profil\n"
        "• /roles - Rollar\n"
        "• /top - Top o'yinchilar\n"
        "• /shop - Do'kon (botda)"
    )
    
    try:
        await bot.send_message(msg.from_user.id, help_text)
    except Exception:
        pass


@dp.message(Command("stats"), F.chat.type.in_({"group", "supergroup"}))
async def group_stats(msg: Message):
    if not await is_admin(msg.chat.id, msg.from_user.id):
        return  # Admin bo'lmasa javob bermaymiz
    
    g = get_group(msg.chat.id)
    users = load_users()
    
    # Count total games
    total_games = 0
    total_players = 0
    active_players = 0
    
    for uid, user in users.items():
        if user.get('games', 0) > 0:
            total_games += user.get('games', 0)
            total_players += 1
            if user.get('games', 0) >= 10:
                active_players += 1
    
    text = (
        f"📊 Guruh {msg.chat.id} statistikasi:\n\n"
        f"👤 Jami o'yinchilar: {total_players}\n"
        f"🎯 Faol o'yinchilar: {active_players}\n"
        f"🎲 Jami o'yinlar: {total_games}\n\n"
        f"⚙️ Ro'yxat vaqti: {g.get('registration_seconds', 60)} sek\n"
        f"🌃 Tun vaqti: {g.get('night_seconds', 60)} sek\n"
        f"☀️ Kun vaqti: {g.get('day_seconds', 60)} sek\n"
        f"🗣 Muhokama vaqti: {g.get('discussion_seconds', 60)} sek\n"
        f"🧞‍♂️ Afsun vaqti: {g.get('afsun_seconds', 30)} sek\n\n"
        f"👥 TeamGame: {'✅ Ruxsat etilgan' if g.get('allow_teamgame', True) else '❌ Ruxsat etilmagan'}"
    )
    
    try:
        await bot.send_message(msg.from_user.id, text)
    except Exception:
        pass


@dp.message(Command("balance"), F.chat.type.in_({"group", "supergroup"}))
async def group_balance(msg: Message):
    if not await is_admin(msg.chat.id, msg.from_user.id):
        return  # Admin bo'lmasa javob bermaymiz
    
    g = get_group(msg.chat.id)
    
    text = (
        f"💰 Guruh {msg.chat.id} balansi:\n\n"
        f"🏆 Guruh daromadi: {fmt_money(g.get('group_money', 0))}\n"
        f"💎 Guruh olmoslari: {g.get('group_diamonds', 0)}\n\n"
        f"📊 Oxigi o'yin: {g.get('last_game_date', 'O\'yin o\'ynalmagan')}\n"
        f"🏅 Oxigi g'olib: {g.get('last_winner', 'Yo\'q')}\n"
        f"👥 Oxigi o'yinchi soni: {g.get('last_players', 0)}"
    )
    
    try:
        await bot.send_message(msg.from_user.id, text)
    except Exception:
        pass


@dp.message(Command("reset"), F.chat.type.in_({"group", "supergroup"}))
async def group_reset(msg: Message):
    if not await is_admin(msg.chat.id, msg.from_user.id):
        return  # Admin bo'lmasa javob bermaymiz
    
    # Reset group data
    g = get_group(msg.chat.id)
    g.update({
        'registration_seconds': 60,
        'night_seconds': 60,
        'day_seconds': 60,
        'discussion_seconds': 60,
        'afsun_seconds': 30,
        'allow_teamgame': True,
        'language': 'uz',
        'group_money': 0,
        'group_diamonds': 0,
        'last_game_date': None,
        'last_winner': None,
        'last_players': 0
    })
    update_group(msg.chat.id, g)
    
    # Reset game data
    game = get_game(msg.chat.id)
    game.update({
        "started": False,
        "phase": PHASE_IDLE,
        "players": {},
        "roles": {},
        "alive": {},
        "votes": {},
        "teams": None,
        "reg_message_id": None,
        "reg_deadline": 0,
        "night_deadline": 0,
        "day_deadline": 0,
        "discussion_deadline": 0,
        "afsun_deadline": 0,
        "mafia_wins": 0,
        "civilian_wins": 0
    })
    
    try:
        await bot.send_message(msg.from_user.id, f"✅ Guruh {msg.chat.id} muvaffaqiyatli tiklandi!")
    except Exception:
        pass


@dp.message(Command("ban"), F.chat.type.in_({"group", "supergroup"}))
async def group_ban(msg: Message):
    if not await is_admin(msg.chat.id, msg.from_user.id):
        return  # Admin bo'lmasa javob bermaymiz
    
    parts = msg.text.split()
    if len(parts) < 2:
        try:
            await bot.send_message(msg.from_user.id, "❌ Notog'ri format. Misol: /ban 123456789")
        except Exception:
            pass
        return
    
    try:
        target_id = int(parts[1])
        target_user = await bot.get_chat(target_id)
        
        # Add to banned list
        g = get_group(msg.chat.id)
        if 'banned_users' not in g:
            g['banned_users'] = []
        
        if target_id not in g['banned_users']:
            g['banned_users'].append(target_id)
            update_group(msg.chat.id, g)
            
            try:
                await bot.send_message(msg.from_user.id, f"✅ {target_user.full_name} ({target_id}) banlandi!")
            except Exception:
                pass
            
            # Try to ban from group
            try:
                await bot.ban_chat_member(msg.chat.id, target_id)
            except Exception:
                pass
        else:
            try:
                await bot.send_message(msg.from_user.id, f"❌ {target_user.full_name} allaqachon banlangan!")
            except Exception:
                pass
                
    except (ValueError, Exception):
        try:
            await bot.send_message(msg.from_user.id, "❌ Foydalanuvchi topilmadi!")
        except Exception:
            pass


@dp.message(Command("unban"), F.chat.type.in_({"group", "supergroup"}))
async def group_unban(msg: Message):
    if not await is_admin(msg.chat.id, msg.from_user.id):
        return  # Admin bo'lmasa javob bermaymiz
    
    parts = msg.text.split()
    if len(parts) < 2:
        try:
            await bot.send_message(msg.from_user.id, "❌ Notog'ri format. Misol: /unban 123456789")
        except Exception:
            pass
        return
    
    try:
        target_id = int(parts[1])
        
        # Remove from banned list
        g = get_group(msg.chat.id)
        if 'banned_users' not in g:
            g['banned_users'] = []
        
        if target_id in g['banned_users']:
            g['banned_users'].remove(target_id)
            update_group(msg.chat.id, g)
            
            try:
                await bot.send_message(msg.from_user.id, f"✅ Foydalanuvchi {target_id} ban olib tashlandi!")
            except Exception:
                pass
            
            # Try to unban from group
            try:
                await bot.unban_chat_member(msg.chat.id, target_id)
            except Exception:
                pass
        else:
            try:
                await bot.send_message(msg.from_user.id, f"❌ Foydalanuvchi {target_id} banlangan emas!")
            except Exception:
                pass
                
    except ValueError:
        try:
            await bot.send_message(msg.from_user.id, "❌ Notog'ri ID!")
        except Exception:
            pass


@dp.message(Command("mute"), F.chat.type.in_({"group", "supergroup"}))
async def group_mute(msg: Message):
    if not await is_admin(msg.chat.id, msg.from_user.id):
        return  # Admin bo'lmasa javob bermaymiz
    
    parts = msg.text.split()
    if len(parts) < 2:
        try:
            await bot.send_message(msg.from_user.id, "❌ Notog'ri format. Misol: /mute 123456789")
        except Exception:
            pass
        return
    
    try:
        target_id = int(parts[1])
        target_user = await bot.get_chat(target_id)
        
        # Add to muted list
        g = get_group(msg.chat.id)
        if 'muted_users' not in g:
            g['muted_users'] = []
        
        if target_id not in g['muted_users']:
            g['muted_users'].append(target_id)
            update_group(msg.chat.id, g)
            
            try:
                await bot.send_message(msg.from_user.id, f"✅ {target_user.full_name} ({target_id}) mute qilindi!")
            except Exception:
                pass
            
            # Try to mute from group
            try:
                await bot.restrict_chat_member(msg.chat.id, target_id, can_send_messages=False)
            except Exception:
                pass
        else:
            try:
                await bot.send_message(msg.from_user.id, f"❌ {target_user.full_name} allaqachon mute qilingan!")
            except Exception:
                pass
                
    except (ValueError, Exception):
        try:
            await bot.send_message(msg.from_user.id, "❌ Foydalanuvchi topilmadi!")
        except Exception:
            pass


@dp.message(Command("unmute"), F.chat.type.in_({"group", "supergroup"}))
async def group_unmute(msg: Message):
    if not await is_admin(msg.chat.id, msg.from_user.id):
        return  # Admin bo'lmasa javob bermaymiz
    
    parts = msg.text.split()
    if len(parts) < 2:
        try:
            await bot.send_message(msg.from_user.id, "❌ Notog'ri format. Misol: /unmute 123456789")
        except Exception:
            pass
        return
    
    try:
        target_id = int(parts[1])
        
        # Remove from muted list
        g = get_group(msg.chat.id)
        if 'muted_users' not in g:
            g['muted_users'] = []
        
        if target_id in g['muted_users']:
            g['muted_users'].remove(target_id)
            update_group(msg.chat.id, g)
            
            try:
                await bot.send_message(msg.from_user.id, f"✅ Foydalanuvchi {target_id} mute olib tashlandi!")
            except Exception:
                pass
            
            # Try to unmute from group
            try:
                await bot.restrict_chat_member(msg.chat.id, target_id, can_send_messages=True)
            except Exception:
                pass
        else:
            try:
                await bot.send_message(msg.from_user.id, f"❌ Foydalanuvchi {target_id} mute qilingan emas!")
            except Exception:
                pass
                
    except ValueError:
        try:
            await bot.send_message(msg.from_user.id, "❌ Notog'ri ID!")
        except Exception:
            pass


@dp.message(Command("settings"), F.chat.type.in_({"group", "supergroup"}))
async def group_settings(msg: Message):
    if not await is_admin(msg.chat.id, msg.from_user.id):
        return  # Admin bo'lmasa javob bermaymiz
    
    # Send settings panel to admin's private chat
    try:
        await bot.send_message(
            msg.from_user.id,
            f"⚙️ Guruh {msg.chat.id} sozlamalari:\n\n"
            "Quyidagi tugmalardan foydalaning:",
            reply_markup=settings_main_kb(msg.chat.id)
        )
    except Exception:
        pass


# ================= HELPER FUNCTIONS FOR INLINE MENU =================
def shop_kb() -> InlineKeyboardMarkup:
    rows: List[List[InlineKeyboardButton]] = []
    for key, it in SHOP_ITEMS.items():
        price = it["price"]
        cur = "💵" if it["currency"] == "money" else "💎"
        rows.append([InlineKeyboardButton(text=f"{it['title']} — {price}{cur}", callback_data=f"buy:{key}")])
    rows.append([InlineKeyboardButton(text="❌ Yopish", callback_data="shop_close")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def roles_kb() -> InlineKeyboardMarkup:
    rows = []
    for role in ROLES_LIST:
        emoji = ROLE_EMOJI.get(role, "🎭")
        rows.append([InlineKeyboardButton(text=f"{emoji} {role}", callback_data=f"role:{role}")])
    rows.append([InlineKeyboardButton(text="❌ Yopish", callback_data="roles_close")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def settings_main_kb(chat_id: int) -> InlineKeyboardMarkup:
    g = get_group(chat_id)
    
    rows = [
        [InlineKeyboardButton(text="⏰ Ro'yxat vaqti", callback_data=f"set:time:{chat_id}:registration_seconds")],
        [InlineKeyboardButton(text="🌃 Tun vaqti", callback_data=f"set:time:{chat_id}:night_seconds")],
        [InlineKeyboardButton(text="☀️ Kun vaqti", callback_data=f"set:time:{chat_id}:day_seconds")],
        [InlineKeyboardButton(text="🗣 Muhokama vaqti", callback_data=f"set:time:{chat_id}:discussion_seconds")],
        [InlineKeyboardButton(text="🧞‍♂️ Afsun vaqti", callback_data=f"set:time:{chat_id}:afsun_seconds")],
        [InlineKeyboardButton(text="⚙️ TeamGame", callback_data=f"set:toggle:{chat_id}:allow_teamgame")],
        [InlineKeyboardButton(text="🌐 Til", callback_data=f"set:lang:{chat_id}")],
        [InlineKeyboardButton(text="🧹 Default", callback_data=f"set:default:{chat_id}")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data=f"set:main:{chat_id}")]
    ]
    
    return InlineKeyboardMarkup(inline_keyboard=rows)

async def start_game_func(chat_id: int):
    """Helper function to start game from inline menu"""
    game = get_game(chat_id)
    if game.get("started") or game["phase"] != PHASE_REG:
        return False, "❌ Avval ro'yxat oching."
    if len(game["players"]) < 4:
        return False, "❌ Kamida 4 ta o'yinchi kerak."

    players = list(game["players"].keys())
    # "next_role" shop logic (soddalashtirilgan): agar userda next_role bo'lsa va to'g'ri bo'lsa - o'shani beramiz.
    desired: Dict[str, str] = {}
    for uid in players:
        try:
            u = get_user(int(uid), game["players"][uid])
            nr = str(u.get("next_role", "-") or "-")
            if nr in ROLES_LIST:
                desired[uid] = nr
        except Exception:
            pass

    roles = assign_roles(len(players))
    for uid, role in zip(players, roles):
        game["roles"][uid] = role

    # apply desired roles if possible (swap within existing role pool)
    if desired:
        pool = roles.copy()
        for uid, want in desired.items():
            if want in pool:
                pool.remove(want)
                # put back current role
                cur = game["roles"].get(uid)
                if cur is not None:
                    pool.append(cur)
                game["roles"][uid] = want
                # consume next_role ticket
                try:
                    u = get_user(int(uid), game["players"][uid])
                    u["next_role"] = "-"
                    update_user(int(uid), u)
                except Exception:
                    pass

    game["alive"] = players.copy()
    game["started"] = True
    game["votes"] = {}
    game["night_turn"] = 0
    game["night_picks"] = {}
    game["mafia_votes"] = {}
    game["doc_self_used"] = set()
    game["afsun_revenge"] = None
    game["afsun_target"] = None

    game["night"] = {
        "heal": None,
        "heal_by": None,
        "block": None,
        "lawyer_protect": None,
        "watch": {},
        "killer_kill": None,
        "killer_by": None,
    }

    g = get_group(chat_id)
    text = ""
    if not g["silent_mode"]:
        # Create game summary with roles
        role_counts = {}
        for role in game["roles"].values():
            role_counts[role] = role_counts.get(role, 0) + 1
        
        # Group roles by category
        mafia_roles = ["Mafiya", "Don", "Advokat"]
        singleton_roles = ["G'azabkor", "Qotil", "Bo'ri"]
        civilian_roles = ["Tinch", "Komissar", "Doktor", "Daydi", "Afsungar", "Omadli", "Kezuvchi", "Serjant", "Suisid"]
        
        text = f"🎮 O'yin boshlandi! ({len(players)} o'yinchi)\n\n"
        
        # Mafia team
        mafia_count = sum(role_counts.get(r, 0) for r in mafia_roles)
        if mafia_count > 0:
            text += f"🤵🏻 Mafiya - {mafia_count}\n"
            for role in mafia_roles:
                count = role_counts.get(role, 0)
                if count > 0:
                    emoji = ROLE_EMOJI.get(role, "🎭")
                    text += f"{emoji} {role} - {count}\n"
        
        # Singleton team  
        singleton_count = sum(role_counts.get(r, 0) for r in singleton_roles)
        if singleton_count > 0:
            text += f"\n👨🏼 Singleton - {singleton_count}\n"
            for role in singleton_roles:
                count = role_counts.get(role, 0)
                if count > 0:
                    emoji = ROLE_EMOJI.get(role, "🎭")
                    text += f"{emoji} {role} - {count}\n"
        
        # Civilian team
        civilian_count = sum(role_counts.get(r, 0) for r in civilian_roles)
        if civilian_count > 0:
            text += f"\n🏘 Tinch aholilar - {civilian_count}\n"
            for role in civilian_roles:
                count = role_counts.get(role, 0)
                if count > 0:
                    emoji = ROLE_EMOJI.get(role, "🎭")
                    text += f"{emoji} {role} - {count}\n"
        
        text += f"\nJami: {len(players)}"

    # DM roles
    for uid in players:
        await safe_dm(uid, f"🎭 Sizning rolingiz: {game['roles'][uid]}\n/roles orqali vazifalar." if True else None)

    game["loop_task"] = asyncio.create_task(game_loop(chat_id))
    return True, text


# ================= REMOVED START COMMAND HANDLER =================
# /start command removed - use /menu for admin access


# ================= SETTINGS PANEL (group) =================
def _dot(on: bool) -> str:
    return "🟢 ON" if on else "🔴 OFF"


def settings_main_kb(chat_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🎁 Giveaway", callback_data=f"set:open:{chat_id}:giveaway")],
            [InlineKeyboardButton(text="🎭 Rollar", callback_data=f"set:open:{chat_id}:roles")],
            [InlineKeyboardButton(text="⏱ Vaqtlar", callback_data=f"set:open:{chat_id}:times")],
            [InlineKeyboardButton(text="🔇 Jimlik", callback_data=f"set:open:{chat_id}:silent")],
            [InlineKeyboardButton(text="🔫 Qurollar", callback_data=f"set:open:{chat_id}:weapons")],
            [InlineKeyboardButton(text="🧩 Boshqa sozlamalar", callback_data=f"set:open:{chat_id}:other")],
            [InlineKeyboardButton(text="🌐 Til", callback_data=f"set:open:{chat_id}:lang")],
            [InlineKeyboardButton(text="🛠 Boshqaruv paneli", callback_data=f"set:open:{chat_id}:panel")],
            [InlineKeyboardButton(text="🚪 Chiqish", callback_data=f"set:close:{chat_id}")],
        ]
    )


def settings_cat_kb(chat_id: int, cat: str) -> InlineKeyboardMarkup:
    g = get_group(chat_id)

    def toggle_btn(label: str, key: str, cat_name: str) -> InlineKeyboardButton:
        cur = bool(g.get(key, False))
        return InlineKeyboardButton(
            text=f"{_dot(cur)} {label}",
            callback_data=f"set:toggle:{chat_id}:{cat_name}:{key}"
        )

    rows: List[List[InlineKeyboardButton]] = []

    if cat == "giveaway":
        rows = [[toggle_btn("Giveaway", "allow_giveaway", "giveaway")]]
    elif cat == "roles":
        rows = [[toggle_btn("Rol ko'rsatish", "reveal_roles", "roles")]]
    elif cat == "silent":
        rows = [[toggle_btn("Jimlik (silent mode)", "silent_mode", "silent")]]
    elif cat == "weapons":
        rows = [[toggle_btn("Qurollar", "weapons_enabled", "weapons")]]
    elif cat == "other":
        rows = [[toggle_btn("TeamGame", "allow_teamgame", "other")]]
    elif cat == "times":
        night = int(g.get("night_seconds", 25))
        discuss = int(g.get("discussion_seconds", 15))
        day = int(g.get("day_seconds", 25))
        reg = int(g.get("registration_seconds", 60))
        rows = [
            [
                InlineKeyboardButton(text=f"🌙 Tun: {night}s", callback_data=f"set:time:{chat_id}:night:0")
            ],
            [
                InlineKeyboardButton(text="➖5", callback_data=f"set:time:{chat_id}:night:-5"),
                InlineKeyboardButton(text="➕5", callback_data=f"set:time:{chat_id}:night:5"),
            ],
            [
                InlineKeyboardButton(text=f"🗣 Muhokama: {discuss}s", callback_data=f"set:time:{chat_id}:discuss:0")
            ],
            [
                InlineKeyboardButton(text="➖5", callback_data=f"set:time:{chat_id}:discuss:-5"),
                InlineKeyboardButton(text="➕5", callback_data=f"set:time:{chat_id}:discuss:5"),
            ],
            [
                InlineKeyboardButton(text=f"☀️ Kun: {day}s", callback_data=f"set:time:{chat_id}:day:0")
            ],
            [
                InlineKeyboardButton(text="➖5", callback_data=f"set:time:{chat_id}:day:-5"),
                InlineKeyboardButton(text="➕5", callback_data=f"set:time:{chat_id}:day:5"),
            ],
            [
                InlineKeyboardButton(text=f"📢 Ro'yxat: {reg}s", callback_data=f"set:time:{chat_id}:reg:0")
            ],
            [
                InlineKeyboardButton(text="➖10", callback_data=f"set:time:{chat_id}:reg:-10"),
                InlineKeyboardButton(text="➕10", callback_data=f"set:time:{chat_id}:reg:10"),
            ],
        ]
    elif cat == "lang":
        # 10 til
        cur = g.get("lang", "uz")
        codes = list(LANGS.keys())
        # 2 ustunli grid
        grid: List[List[InlineKeyboardButton]] = []
        row: List[InlineKeyboardButton] = []
        for i, code in enumerate(codes, 1):
            mark = "✅ " if code == cur else ""
            row.append(
                InlineKeyboardButton(
                    text=f"{mark}{LANGS[code]}",
                    callback_data=f"set:lang:{chat_id}:{code}"
                )
            )
            if i % 2 == 0:
                grid.append(row)
                row = []
        if row:
            grid.append(row)
        rows = grid
    elif cat == "panel":
        # Boshqaruv paneli
        rows = [
            [InlineKeyboardButton(text="📊 Status (ko'rish)", callback_data=f"set:panel:{chat_id}:status")],
            [InlineKeyboardButton(text="🧹 Default qilish", callback_data=f"set:panel:{chat_id}:default")],
        ]

    # Back + Close
    rows.append([InlineKeyboardButton(text="⬅️ Orqaga", callback_data=f"set:main:{chat_id}")])
    rows.append([InlineKeyboardButton(text="🚪 Chiqish", callback_data=f"set:close:{chat_id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ---------------- /settings PANEL HANDLERS ----------------
@dp.message(Command("settings"), F.chat.type.in_({"group", "supergroup"}))
async def group_settings_panel(msg: Message):
    # faqat admin
    if not await is_admin(msg.chat.id, msg.from_user.id):
        return await msg.answer("❌ Faqat admin.")
    await msg.answer("Qanday parametrlarni o'zgartirmoqchisiz?", reply_markup=settings_main_kb(msg.chat.id))


@dp.callback_query(F.data.startswith("set:"))
async def cb_settings_router(cb: CallbackQuery):
    try:
        parts = cb.data.split(":")
        action = parts[1]
        chat_id = int(parts[2])
    except Exception:
        return await cb.answer()

    # close'dan boshqa barcha settings action'lar faqat admin uchun
    if action != "close":
        if not await is_admin(chat_id, cb.from_user.id):
            return await cb.answer("❌ Faqat admin.", show_alert=True)

    if action == "open":
        # set:open:{chat_id}:{cat}
        cat = parts[3]
        await cb.answer()
        await cb.message.edit_text(f"⚙️ Settings: {cat}", reply_markup=settings_cat_kb(chat_id, cat))
        return

    if action == "main":
        await cb.answer()
        await cb.message.edit_text("Qanday parametrlarni o'zgartirmoqchisiz?", reply_markup=settings_main_kb(chat_id))
        return

    if action == "close":
        await cb.answer()
        try:
            await cb.message.delete()
        except Exception:
            pass
        return

    if action == "toggle":
        # set:toggle:{chat_id}:{cat}:{key}
        cat = parts[3]
        key = parts[4]
        g = get_group(chat_id)
        if not isinstance(g.get(key, None), bool):
            # agar bo'sh bo'lsa default False qilamiz
            g[key] = False
        g[key] = not bool(g[key])
        update_group(chat_id, g)
        await cb.answer("✅ Saqlandi", show_alert=True)
        await cb.message.edit_text("Qanday parametrlarni o'zgartirmoqchisiz?", reply_markup=settings_main_kb(chat_id))
        return

    if action == "lang":
        # set:lang:{chat_id}:{code}
        code = parts[3]
        if code not in LANGS:
            return await cb.answer("❌ Til noto'g'ri", show_alert=True)
        g = get_group(chat_id)
        g["lang"] = code
        update_group(chat_id, g)
        await cb.answer("✅ Til saqlandi", show_alert=True)
        await cb.message.edit_text("Qanday parametrlarni o'zgartirmoqchisiz?", reply_markup=settings_main_kb(chat_id))
        return

    if action == "time":
        # set:time:{chat_id}:{which}:{delta}
        which = parts[3]
        delta = int(parts[4])
        g = get_group(chat_id)

        def clamp(val: int, lo: int, hi: int) -> int:
            return max(lo, min(hi, val))

        if which == "night":
            g["night_seconds"] = clamp(int(g.get("night_seconds", 25)) + delta, 10, 120)
        elif which == "discuss":
            g["discussion_seconds"] = clamp(int(g.get("discussion_seconds", 15)) + delta, 5, 120)
        elif which == "day":
            g["day_seconds"] = clamp(int(g.get("day_seconds", 25)) + delta, 10, 120)
        elif which == "reg":
            g["registration_seconds"] = clamp(int(g.get("registration_seconds", 60)) + delta, 30, 600)

        update_group(chat_id, g)
        await cb.answer("✅ Vaqt yangilandi", show_alert=True)
        await cb.message.edit_text("Qanday parametrlarni o'zgartirmoqchisiz?", reply_markup=settings_main_kb(chat_id))
        return

    if action == "panel":
        # set:panel:{chat_id}:{which}
        which = parts[3]
        g = get_group(chat_id)

        if which == "status":
            await cb.answer()
            await cb.message.edit_text(
                "📊 Status:\n"
                f"🔇 Jimlik: {_dot(g.get('silent_mode', False))}\n"
                f"🎭 Rol ko'rsatish: {_dot(g.get('reveal_roles', True))}\n"
                f"🔫 Qurollar: {_dot(g.get('weapons_enabled', False))}\n"
                f"🎁 Giveaway: {_dot(g.get('allow_giveaway', False))}\n"
                f"🔵🔴 TeamGame: {_dot(g.get('allow_teamgame', True))}\n"
                f"🌙 Tun: {int(g.get('night_seconds', 25))}s\n"
                f"🗣 Muhokama: {int(g.get('discussion_seconds', 15))}s\n"
                f"☀️ Kun: {int(g.get('day_seconds', 25))}s\n"
                f"📢 Ro'yxat: {int(g.get('registration_seconds', 60))}s\n"
                f"🌐 Til: {LANGS.get(g.get('lang', 'uz'), g.get('lang', 'uz'))}\n",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="⬅️ Orqaga", callback_data=f"set:main:{chat_id}")]
                ])
            )
            return

        if which == "default":
            await cb.answer("🧹 Default", show_alert=True)
            try:
                g_default = DEFAULT_GROUP.copy()
                update_group(chat_id, g_default)
            except Exception:
                pass

            await cb.message.edit_text(
                "🧹 Default settings o'rnatildi.",
                reply_markup=settings_main_kb(chat_id)
            )
            return

        if which == "toggle":
            key = parts[4]

            g[key] = not g.get(key, False)
            update_group(chat_id, g)

            await cb.answer("✅ O'zgartirildi")
            await cb.message.edit_reply_markup(reply_markup=settings_main_kb(chat_id))
            return

        if which == "time":
            key = parts[4]
            value = int(parts[5])

            g[key] = value
            update_group(chat_id, g)

            await cb.answer("⏱ Yangilandi")
            await cb.message.edit_reply_markup(reply_markup=settings_main_kb(chat_id))
            return

        if which == "lang":
            lang = parts[4]

            g["lang"] = lang
            update_group(chat_id, g)

            await cb.answer("🌐 Til o'zgardi")
            await cb.message.edit_reply_markup(reply_markup=settings_main_kb(chat_id))
            return

        if which == "times":
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="🌙 Tun 20s", callback_data=f"set:time:{chat_id}:night_seconds:20"),
                    InlineKeyboardButton(text="🌙 Tun 30s", callback_data=f"set:time:{chat_id}:night_seconds:30"),
                ],
                [
                    InlineKeyboardButton(text="☀️ Kun 20s", callback_data=f"set:time:{chat_id}:day_seconds:20"),
                    InlineKeyboardButton(text="☀️ Kun 30s", callback_data=f"set:time:{chat_id}:day_seconds:30"),
                ],
                [
                    InlineKeyboardButton(text="🗣 Muhokama 10s", callback_data=f"set:time:{chat_id}:discussion_seconds:10"),
                    InlineKeyboardButton(text="🗣 Muhokama 20s", callback_data=f"set:time:{chat_id}:discussion_seconds:20"),
                ],
                [
                    InlineKeyboardButton(text="📢 Ro'yxat 40s", callback_data=f"set:time:{chat_id}:registration_seconds:40"),
                    InlineKeyboardButton(text="📢 Ro'yxat 60s", callback_data=f"set:time:{chat_id}:registration_seconds:60"),
                ],
                [
                    InlineKeyboardButton(text="⬅️ Orqaga", callback_data=f"set:main:{chat_id}")
                ]
            ])

            await cb.answer()
            await cb.message.edit_text("⏱ Vaqt sozlamalari:", reply_markup=kb)
            return

        if which == "lang_menu":
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="🇺🇿 O'zbek", callback_data=f"set:lang:{chat_id}:uz"),
                    InlineKeyboardButton(text="🇷🇺 Русский", callback_data=f"set:lang:{chat_id}:ru"),
                ],
                [
                    InlineKeyboardButton(text="⬅️ Orqaga", callback_data=f"set:main:{chat_id}")
                ]
            ])

            await cb.answer()
            await cb.message.edit_text("🌐 Tilni tanlang:", reply_markup=kb)
            return


async def main():
    await setup_commands_menu()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
