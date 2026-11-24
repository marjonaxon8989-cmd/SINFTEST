import asyncio
import itertools
import json
import logging
import os
import random
import sqlite3
from pathlib import Path

from aiohttp import web
from aiogram import BaseMiddleware, Bot, Dispatcher, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    BotCommand,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
)

from strings import LANGS, SUBJECTS, T, all_texts, grade_subjects, t

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("bot")

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
CHANNEL = os.environ.get("CHANNEL", "@DUELUM")
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "barhayot_madaminov")
DB_PATH = os.environ.get("DB_PATH", "bot.db")
PORT = int(os.environ.get("PORT", "10000"))
TEST_SIZE = 20
BASE = Path(__file__).parent

router = Router()
router.message.filter(F.chat.type == "private")

# ---------------------------------------------------------------- DB


def db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with db() as c:
        c.execute(
            """CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                name TEXT,
                lang TEXT,
                score INTEGER DEFAULT 0
            )"""
        )


def upsert_user(uid: int, name: str) -> None:
    with db() as c:
        c.execute(
            "INSERT INTO users (id, name) VALUES (?, ?) "
            "ON CONFLICT(id) DO UPDATE SET name = excluded.name",
            (uid, name),
        )


def get_user(uid: int):
    with db() as c:
        return c.execute("SELECT * FROM users WHERE id = ?", (uid,)).fetchone()


def set_lang(uid: int, lang: str) -> None:
    with db() as c:
        c.execute("UPDATE users SET lang = ? WHERE id = ?", (lang, uid))


def add_score(uid: int, pts: int) -> int:
    with db() as c:
        c.execute("UPDATE users SET score = score + ? WHERE id = ?", (pts, uid))
        return c.execute("SELECT score FROM users WHERE id = ?", (uid,)).fetchone()["score"]


def top_users(n: int = 20):
    with db() as c:
        return c.execute(
            "SELECT id, name, score FROM users WHERE score > 0 "
            "ORDER BY score DESC, id ASC LIMIT ?",
            (n,),
        ).fetchall()


def user_place(uid: int):
    u = get_user(uid)
    if not u:
        return None
    with db() as c:
        higher = c.execute("SELECT COUNT(*) AS n FROM users WHERE score > ?", (u["score"],)).fetchone()["n"]
    return higher + 1, u["score"]


# ---------------------------------------------------------------- savollar

QB: dict[tuple[int, str], list[dict]] = {}


def load_questions() -> None:
    for f in (BASE / "questions").glob("*.json"):
        if f.name.startswith("_"):
            continue
        try:
            grade_s, subj = f.stem.split("_", 1)
            QB[(int(grade_s), subj)] = json.loads(f.read_text(encoding="utf-8"))
        except Exception as e:  # noqa: BLE001
            log.error("Savol fayli o'qilmadi %s: %s", f.name, e)
    log.info("Yuklandi: %d ta fan fayli", len(QB))


def tr(value, lang: str):
    """Matn yoki ro'yxat tilga bog'liq (dict) yoki umumiy bo'lishi mumkin."""
    if isinstance(value, dict):
        return value.get(lang) or value.get("uz")
    return value


# ---------------------------------------------------------------- holat

STATE: dict[int, int] = {}  # uid -> tanlangan sinf
SESS: dict[int, dict] = {}  # uid -> joriy test
SID = itertools.count(1)

# ---------------------------------------------------------------- klaviaturalar


def main_kb(lang: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t(lang, "btn_test"))],
            [KeyboardButton(text=t(lang, "btn_rating")), KeyboardButton(text=t(lang, "btn_group"))],
            [KeyboardButton(text=t(lang, "btn_lang")), KeyboardButton(text=t(lang, "btn_admin"))],
        ],
        resize_keyboard=True,
    )


def subjects_kb(lang: str, grade: int) -> ReplyKeyboardMarkup:
    names = [KeyboardButton(text=SUBJECTS[k][lang]) for k in grade_subjects(grade)]
    rows = [names[i : i + 2] for i in range(0, len(names), 2)]
    rows.append([KeyboardButton(text=t(lang, "btn_back"))])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def lang_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=n, callback_data=f"lang:{c}")] for c, n in LANGS.items()]
    )


def grades_kb() -> InlineKeyboardMarkup:
    btns = [InlineKeyboardButton(text=str(g), callback_data=f"g:{g}") for g in range(1, 12)]
    rows = [btns[i : i + 4] for i in range(0, len(btns), 4)]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def sub_kb(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t(lang, "btn_sub"), url=f"https://t.me/{CHANNEL.lstrip('@')}")],
            [InlineKeyboardButton(text=t(lang, "btn_check"), callback_data="check_sub")],
        ]
    )


# ---------------------------------------------------------------- majburiy obuna


async def is_subscribed(bot: Bot, uid: int) -> bool:
    try:
        m = await bot.get_chat_member(CHANNEL, uid)
        return m.status in ("member", "administrator", "creator") or (
            m.status == "restricted" and getattr(m, "is_member", False)
        )
    except Exception as e:  # noqa: BLE001
        log.error("Obunani tekshirib bo'lmadi (bot kanalda admin emasmi?): %s", e)
        return False


def lang_of(user) -> str:
    row = get_user(user.id)
    if row and row["lang"]:
        return row["lang"]
    code = (user.language_code or "uz")[:2]
    return code if code in T else "uz"


class SubMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        user = data.get("event_from_user")
        chat = data.get("event_chat")
        if user is None or chat is None or chat.type != "private":
            return await handler(event, data)
        if isinstance(event, CallbackQuery) and event.data == "check_sub":
            return await handler(event, data)
        if await is_subscribed(data["bot"], user.id):
            return await handler(event, data)
        lang = lang_of(user)
        text = t(lang, "sub_required", channel=CHANNEL)
        if isinstance(event, CallbackQuery):
            await event.answer(t(lang, "not_subscribed"), show_alert=True)
            await event.message.answer(text, reply_markup=sub_kb(lang))
        else:
            await event.answer(text, reply_markup=sub_kb(lang))


router.message.outer_middleware(SubMiddleware())
router.callback_query.outer_middleware(SubMiddleware())

# ---------------------------------------------------------------- yordamchi


def btn(key: str):
    return F.text.in_(all_texts(key))


async def show_main(m: Message, uid: int, name: str) -> None:
    lang = get_user(uid)["lang"]
    STATE.pop(uid, None)
    SESS.pop(uid, None)
    await m.answer(t(lang, "welcome", name=name), reply_markup=main_kb(lang))


# ---------------------------------------------------------------- start / help / til


@router.message(CommandStart())
async def cmd_start(m: Message):
    upsert_user(m.from_user.id, m.from_user.full_name)
    u = get_user(m.from_user.id)
    if not u["lang"]:
        await m.answer(T["uz"]["choose_lang"], reply_markup=lang_kb())
        return
    await show_main(m, m.from_user.id, m.from_user.full_name)


@router.callback_query(F.data == "check_sub")
async def cb_check_sub(c: CallbackQuery, bot: Bot):
    lang = lang_of(c.from_user)
    if not await is_subscribed(bot, c.from_user.id):
        await c.answer(t(lang, "not_subscribed"), show_alert=True)
        return
    await c.answer()
    try:
        await c.message.delete()
    except Exception:  # noqa: BLE001
        pass
    upsert_user(c.from_user.id, c.from_user.full_name)
    u = get_user(c.from_user.id)
    if not u["lang"]:
        await c.message.answer(T["uz"]["choose_lang"], reply_markup=lang_kb())
    else:
        await show_main(c.message, c.from_user.id, c.from_user.full_name)


@router.message(Command("help"))
async def cmd_help(m: Message):
    await m.answer(t(lang_of(m.from_user), "help"))


@router.message(Command("language"))
@router.message(btn("btn_lang"))
async def cmd_language(m: Message):
    upsert_user(m.from_user.id, m.from_user.full_name)
    await m.answer(T["uz"]["choose_lang"], reply_markup=lang_kb())


@router.callback_query(F.data.startswith("lang:"))
async def cb_lang(c: CallbackQuery):
    code = c.data.split(":")[1]
    if code not in T:
        await c.answer()
        return
    upsert_user(c.from_user.id, c.from_user.full_name)
    set_lang(c.from_user.id, code)
    await c.answer(t(code, "lang_changed"))
    try:
        await c.message.delete()
    except Exception:  # noqa: BLE001
        pass
    await show_main(c.message, c.from_user.id, c.from_user.full_name)


# ---------------------------------------------------------------- menyu tugmalari


@router.message(btn("btn_rating"))
async def show_rating(m: Message):
    lang = lang_of(m.from_user)
    rows = top_users(20)
    if not rows:
        await m.answer(t(lang, "rating_empty"))
        return
    lines = [t(lang, "rating_title")]
    for i, r in enumerate(rows, 1):
        lines.append(t(lang, "rating_row", pos=i, name=r["name"], id=r["id"], score=r["score"]))
    me = user_place(m.from_user.id)
    if me:
        lines.append(t(lang, "rating_me", pos=me[0], score=me[1]))
    await m.answer("\n".join(lines))


@router.message(btn("btn_group"))
async def add_group(m: Message, bot: Bot):
    lang = lang_of(m.from_user)
    me = await bot.me()
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t(lang, "btn_add_group"), url=f"https://t.me/{me.username}?startgroup=true")]
        ]
    )
    await m.answer(t(lang, "group_text"), reply_markup=kb)


@router.message(btn("btn_admin"))
async def admin(m: Message):
    lang = lang_of(m.from_user)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=t(lang, "btn_admin_link"), url=f"https://t.me/{ADMIN_USERNAME}")]]
    )
    await m.answer(t(lang, "admin_text"), reply_markup=kb)


@router.message(btn("btn_back"))
async def back(m: Message):
    upsert_user(m.from_user.id, m.from_user.full_name)
    if not get_user(m.from_user.id)["lang"]:
        await m.answer(T["uz"]["choose_lang"], reply_markup=lang_kb())
        return
    await show_main(m, m.from_user.id, m.from_user.full_name)


# ---------------------------------------------------------------- test


@router.message(btn("btn_test"))
async def choose_grade(m: Message):
    lang = lang_of(m.from_user)
    await m.answer(t(lang, "choose_grade"), reply_markup=grades_kb())


@router.callback_query(F.data.startswith("g:"))
async def cb_grade(c: CallbackQuery):
    grade = int(c.data.split(":")[1])
    lang = lang_of(c.from_user)
    STATE[c.from_user.id] = grade
    await c.answer()
    try:
        await c.message.delete()
    except Exception:  # noqa: BLE001
        pass
    await c.message.answer(t(lang, "choose_subject", grade=grade), reply_markup=subjects_kb(lang, grade))


def question_text(sess: dict) -> str:
    q = sess["qs"][sess["i"]]
    lines = [t(sess["lang"], "q_head", i=sess["i"] + 1, n=len(sess["qs"])), "", q["text"], ""]
    for letter, opt in zip("ABCD", q["opts"]):
        lines.append(f"{letter}) {opt[0]}")
    return "\n".join(lines)


def question_kb(sess: dict) -> InlineKeyboardMarkup:
    row = [
        InlineKeyboardButton(text=letter, callback_data=f"a:{sess['sid']}:{sess['i']}:{k}")
        for k, letter in enumerate("ABCD"[: len(sess["qs"][sess["i"]]["opts"])])
    ]
    return InlineKeyboardMarkup(inline_keyboard=[row])


@router.callback_query(F.data.startswith("a:"))
async def cb_answer(c: CallbackQuery):
    _, sid, qi, k = c.data.split(":")
    sess = SESS.get(c.from_user.id)
    if not sess or str(sess["sid"]) != sid or str(sess["i"]) != qi:
        await c.answer()
        return
    lang = sess["lang"]
    q = sess["qs"][sess["i"]]
    if int(k) == q["ci"]:
        sess["score"] += 1
        feedback = t(lang, "right")
    else:
        feedback = t(lang, "wrong", ans=q["opts"][q["ci"]][0])
    sess["i"] += 1
    await c.answer()
    if sess["i"] < len(sess["qs"]):
        await c.message.edit_text(feedback + "\n\n" + question_text(sess), reply_markup=question_kb(sess))
        return
    total = add_score(c.from_user.id, sess["score"])
    SESS.pop(c.from_user.id, None)
    result = t(
        lang,
        "finished",
        grade=sess["grade"],
        subject=SUBJECTS[sess["subj"]][lang],
        score=sess["score"],
        n=len(sess["qs"]),
        total=total,
    )
    await c.message.edit_text(feedback + "\n\n" + result)


async def start_test(m: Message, grade: int, subj: str, lang: str) -> None:
    bank = QB.get((grade, subj))
    if not bank:
        await m.answer(t(lang, "no_questions"))
        return
    prepared = []
    for q in random.sample(bank, min(TEST_SIZE, len(bank))):
        opts = [(o, i == q["a"]) for i, o in enumerate(tr(q["o"], lang))]
        random.shuffle(opts)
        prepared.append(
            {
                "text": tr(q["q"], lang),
                "opts": opts,
                "ci": next(i for i, o in enumerate(opts) if o[1]),
            }
        )
    sess = {"sid": next(SID), "qs": prepared, "i": 0, "score": 0, "grade": grade, "subj": subj, "lang": lang}
    SESS[m.from_user.id] = sess
    await m.answer(question_text(sess), reply_markup=question_kb(sess))


@router.message(F.text)
async def on_text(m: Message):
    uid = m.from_user.id
    lang = lang_of(m.from_user)
    grade = STATE.get(uid)
    if grade:
        for key in grade_subjects(grade):
            if m.text in SUBJECTS[key].values():
                await start_test(m, grade, key, lang)
                return
    if get_user(uid) and get_user(uid)["lang"]:
        await m.answer(t(lang, "use_menu"), reply_markup=main_kb(lang))


# ---------------------------------------------------------------- web (Render uchun) va ishga tushirish


async def start_web() -> None:
    app = web.Application()

    async def ok(_):
        return web.Response(text="ok")

    app.router.add_get("/", ok)
    app.router.add_get("/health", ok)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", PORT).start()
    log.info("Health server: port %s", PORT)


async def set_commands(bot: Bot) -> None:
    for code in T:
        cmds = [
            BotCommand(command="start", description=T[code]["cmd_start"]),
            BotCommand(command="help", description=T[code]["cmd_help"]),
            BotCommand(command="language", description=T[code]["cmd_language"]),
        ]
        if code == "uz":
            await bot.set_my_commands(cmds)  # standart
        await bot.set_my_commands(cmds, language_code=code)


async def main() -> None:
    if not BOT_TOKEN:
        raise SystemExit("BOT_TOKEN o'rnatilmagan")
    init_db()
    load_questions()
    bot = Bot(BOT_TOKEN)
    dp = Dispatcher()
    dp.include_router(router)
    await start_web()
    await bot.delete_webhook(drop_pending_updates=True)
    await set_commands(bot)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
