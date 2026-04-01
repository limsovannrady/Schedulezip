import os
import json
from datetime import datetime, timezone, timedelta
from telegram import (
    Update,
    InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup, ReplyKeyboardRemove, KeyboardButton,
    MessageEntity, ForceReply
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    ContextTypes, ChatMemberHandler, MessageHandler, filters
)

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CAMBODIA_TZ = timezone(timedelta(hours=7))
ADMIN_ID = int(os.environ.get("ADMIN_ID", 5002402843))

DATA_DIR = "/tmp" if os.environ.get("VERCEL") else "."
GROUPS_FILE = os.path.join(DATA_DIR, "groups.json")
USER_GROUPS_FILE = os.path.join(DATA_DIR, "user_groups.json")
PENDING_FILE = os.path.join(DATA_DIR, "pending_schedules.json")
SCHEDULED_FILE = os.path.join(DATA_DIR, "scheduled_messages.json")

STEP_SELECT_GROUP = "select_group"
STEP_ENTER_TIME = "enter_time"
STEP_COLLECT_MESSAGES = "collect_messages"

SCHEDULE_EMOJI_CHAR = "\U0001F4E4"
SCHEDULE_EMOJI_ID   = "5470060791883374114"
LIST_EMOJI_CHAR     = "\U0001F4CB"
LIST_EMOJI_ID       = "5197269100878907942"
TRASH_EMOJI         = "🗑"
TRASH_EMOJI_ID      = "6204044494879330925"

BTN_SCHEDULE = f"{SCHEDULE_EMOJI_CHAR} រៀបចំ"
BTN_LIST     = f"{LIST_EMOJI_CHAR} បញ្ជី"
BTN_CANCEL   = "🚫 បោះបង់"


def make_delete_button(sn, group_title, first_idx):
    label = f"លុប #{sn} ({group_title})"
    return InlineKeyboardButton(
        text=label,
        callback_data=f"del:{first_idx}:{sn}",
        icon_custom_emoji_id=TRASH_EMOJI_ID,
    )


# ─── Helpers ────────────────────────────────────────────────────────────────

def load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def is_admin(user_id) -> bool:
    return int(user_id) == ADMIN_ID


CUSTOM_EMOJI_ID = "5445267414562389170"
CUSTOM_EMOJI_CHAR = "\U0001F4E8"

async def reply_custom_emoji(message, reply_markup=None, do_quote=False):
    entity = MessageEntity(
        type=MessageEntity.CUSTOM_EMOJI,
        offset=0,
        length=len(CUSTOM_EMOJI_CHAR.encode("utf-16-le")) // 2,
        custom_emoji_id=CUSTOM_EMOJI_ID,
    )
    await message.reply_text(
        CUSTOM_EMOJI_CHAR,
        entities=[entity],
        reply_markup=reply_markup,
        do_quote=do_quote,
    )


def register_user_in_group(user_id: str, chat_id: str, chat_title: str):
    user_groups = load_json(USER_GROUPS_FILE, {})
    if user_id not in user_groups:
        user_groups[user_id] = {}
    if chat_id not in user_groups[user_id]:
        user_groups[user_id][chat_id] = chat_title
        save_json(USER_GROUPS_FILE, user_groups)


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [[KeyboardButton(BTN_SCHEDULE), KeyboardButton(BTN_LIST)]],
        resize_keyboard=True,
        one_time_keyboard=False
    )


def collect_keyboard(count: int) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [[KeyboardButton(BTN_CANCEL), KeyboardButton(f"✅ រួចរាល់ ({count})")]],
        resize_keyboard=True,
        one_time_keyboard=False
    )


def format_display_time(scheduled_time_raw: str) -> tuple:
    try:
        st = scheduled_time_raw
        if st.endswith("Z"):
            st = st.replace("Z", "+00:00")
        send_time = datetime.fromisoformat(st)
        if send_time.tzinfo is None:
            send_time = send_time.replace(tzinfo=CAMBODIA_TZ)
        display_str = send_time.astimezone(CAMBODIA_TZ).strftime("%d-%m-%Y %H:%M")
        return send_time, display_str
    except Exception:
        return None, scheduled_time_raw


def parse_time_input(text: str):
    text = text.strip()
    formats = [
        "%d-%m-%Y %H:%M",
        "%d/%m/%Y %H:%M",
        "%Y-%m-%d %H:%M",
        "%d-%m-%Y %I:%M%p",
        "%d-%m-%Y %I:%M %p",
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(text, fmt)
            return dt.replace(tzinfo=CAMBODIA_TZ)
        except ValueError:
            continue
    return None


# ─── /start ────────────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user

    if chat.type in ("group", "supergroup"):
        groups = load_json(GROUPS_FILE, {})
        if str(chat.id) in groups:
            register_user_in_group(str(user.id), str(chat.id), chat.title)
        return

    name = user.first_name or "អ្នក"

    if is_admin(user.id):
        pending = load_json(PENDING_FILE, {})
        pending.pop(str(user.id), None)
        save_json(PENDING_FILE, pending)

        await update.message.reply_text(
            f"សួស្តី *{name}*",
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard(),
            do_quote=True
        )
    else:
        return


# ─── Schedule flow: show group selection ────────────────────────────────────

async def do_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat

    groups = load_json(GROUPS_FILE, {})
    if not groups:
        await update.message.reply_text(
            "សូមបន្ថែម Bot ទៅក្រុមជាមុនសិន។",
            reply_markup=main_menu_keyboard(),
            do_quote=True
        )
        return

    bot_me = await context.bot.get_me()
    bot_id = bot_me.id
    active_groups = {}
    stale_ids = []
    for gid, info in groups.items():
        try:
            member = await context.bot.get_chat_member(chat_id=int(gid), user_id=bot_id)
            if member.status in ("member", "administrator"):
                active_groups[gid] = info
            else:
                stale_ids.append(gid)
        except Exception:
            stale_ids.append(gid)

    if stale_ids:
        for gid in stale_ids:
            groups.pop(gid, None)
        save_json(GROUPS_FILE, groups)

    if not active_groups:
        await update.message.reply_text(
            "សូមបន្ថែម Bot ទៅក្រុមជាមុនសិន។",
            reply_markup=main_menu_keyboard(),
            do_quote=True
        )
        return

    buttons = []
    for gid, info in active_groups.items():
        title = info.get("title", gid)
        buttons.append([InlineKeyboardButton(f"🟢 {title}", callback_data=f"grp:{gid}:{title}")])
    buttons.append([InlineKeyboardButton("🔴 បោះបង់", callback_data="grp:cancel")])

    pending = load_json(PENDING_FILE, {})
    pending[str(user.id)] = {"step": STEP_SELECT_GROUP}
    save_json(PENDING_FILE, pending)

    await update.message.reply_text(
        "*ជ្រើសរើសក្រុមដែលចង់ផ្ញើ៖*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons),
        do_quote=True
    )


# ─── List schedules ──────────────────────────────────────────────────────────

async def do_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    scheduled = load_json(SCHEDULED_FILE, [])
    if not scheduled:
        await update.message.reply_sticker(
            "CAACAgQAAxkBAAEC-TZpyMfCr8fEXLqEwmduZ-LV7sLQcwACcAIAAjcyiws-urnnxWWBsToE",
            reply_markup=main_menu_keyboard(),
            do_quote=True
        )
        return

    groups_map = {}
    for i, item in enumerate(scheduled):
        sn = item.get("schedule_number", i)
        if sn not in groups_map:
            groups_map[sn] = {"item": item, "indices": []}
        groups_map[sn]["indices"].append(i)

    text = f"📋 *Schedule ទាំងអស់ ({len(groups_map)} entries)*\n\n"
    buttons = []
    for sn, data in sorted(groups_map.items()):
        item = data["item"]
        _, display_str = format_display_time(item.get("scheduled_time", ""))
        msg_count = len(data["indices"])
        group_title = item.get("group_title", "?")
        text += (
            f"🔹 *#{sn}* — {group_title}\n"
            f"   ⏰ {display_str}  |  📨 {msg_count} សារ\n\n"
        )
        first_idx = data["indices"][0]
        buttons.append([make_delete_button(sn, group_title, first_idx)])

    await update.message.reply_text(
        text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons),
        do_quote=True
    )


# ─── Callback Query Handler ──────────────────────────────────────────────────

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = update.effective_user
    if not is_admin(user.id):
        await query.answer()
        return
    await query.answer()
    data = query.data

    if data.startswith("grp:"):
        parts = data.split(":", 2)
        if parts[1] == "cancel":
            pending = load_json(PENDING_FILE, {})
            pending.pop(str(user.id), None)
            save_json(PENDING_FILE, pending)
            await query.edit_message_reply_markup(None)
            await reply_custom_emoji(
                query.message,
                reply_markup=main_menu_keyboard(),
                do_quote=True,
            )
            return

        selected_chat_id = parts[1]
        selected_title = parts[2] if len(parts) > 2 else selected_chat_id

        pending = load_json(PENDING_FILE, {})
        pending[str(user.id)] = {
            "step": STEP_ENTER_TIME,
            "group_id": selected_chat_id,
            "group_title": selected_title,
        }
        save_json(PENDING_FILE, pending)

        now_kh = datetime.now(CAMBODIA_TZ).strftime("%d-%m-%Y %H:%M")
        await query.answer()
        await query.message.reply_text(
            f"👥 ក្រុម: *{selected_title}*\n\n"
            f"សូមបញ្ចូលម៉ោងផ្ញើ:\n"
            f"Format: `DD-MM-YYYY HH:MM`\n\n"
            f"ឧទាហរណ៍: `{now_kh}`",
            parse_mode="Markdown",
            reply_markup=ForceReply(selective=True)
        )
        return

    if data.startswith("del:"):
        parts = data.split(":")
        try:
            del_idx = int(parts[1])
            sn = parts[2] if len(parts) > 2 else "?"
        except (ValueError, IndexError):
            await query.edit_message_text("❌ មិនអាចលុបបាន!")
            return

        scheduled = load_json(SCHEDULED_FILE, [])
        if 0 <= del_idx < len(scheduled):
            target_sn = scheduled[del_idx].get("schedule_number")
            scheduled = [s for s in scheduled if s.get("schedule_number") != target_sn]
            save_json(SCHEDULED_FILE, scheduled)
            await query.edit_message_text(f"✅ បានលុប Schedule #{sn} រួចរាល់!")
        else:
            await query.edit_message_text("❌ Schedule នោះមិនមានទៀតហើយ!")
        return


# ─── Group tracking ──────────────────────────────────────────────────────────

async def track_group_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    if not user or chat.type not in ("group", "supergroup"):
        return
    groups = load_json(GROUPS_FILE, {})
    chat_id = str(chat.id)
    if chat_id not in groups:
        groups[chat_id] = {"title": chat.title or chat_id, "type": chat.type}
        save_json(GROUPS_FILE, groups)
    register_user_in_group(str(user.id), chat_id, groups[chat_id]["title"])


async def track_my_chat_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = update.my_chat_member
    if result is None:
        return
    chat = result.chat
    new_status = result.new_chat_member.status
    groups = load_json(GROUPS_FILE, {})

    if new_status in ("member", "administrator") and chat.type in ("group", "supergroup"):
        groups[str(chat.id)] = {"title": chat.title, "type": chat.type}
        save_json(GROUPS_FILE, groups)
    elif new_status in ("left", "kicked"):
        chat_id = str(chat.id)
        groups.pop(chat_id, None)
        save_json(GROUPS_FILE, groups)
        user_groups = load_json(USER_GROUPS_FILE, {})
        changed = False
        for uid in user_groups:
            if chat_id in user_groups[uid]:
                del user_groups[uid][chat_id]
                changed = True
        if changed:
            save_json(USER_GROUPS_FILE, user_groups)


# ─── Send helpers ────────────────────────────────────────────────────────────

async def send_any_message(bot, chat_id: int, item: dict, reply_to_message_id: int = None):
    msg_type = item.get("msg_type", "text")
    content = item.get("content") or item.get("message", "")
    caption = item.get("caption")
    reply_kwargs = {"reply_to_message_id": reply_to_message_id} if reply_to_message_id else {}

    if msg_type == "forward":
        await bot.forward_message(chat_id=chat_id, from_chat_id=int(caption), message_id=int(content))
    elif msg_type == "photo":
        await bot.send_photo(chat_id=chat_id, photo=content, caption=caption, **reply_kwargs)
    elif msg_type == "video":
        await bot.send_video(chat_id=chat_id, video=content, caption=caption, **reply_kwargs)
    elif msg_type == "document":
        await bot.send_document(chat_id=chat_id, document=content, caption=caption, **reply_kwargs)
    elif msg_type == "sticker":
        await bot.send_sticker(chat_id=chat_id, sticker=content, **reply_kwargs)
    elif msg_type == "voice":
        await bot.send_voice(chat_id=chat_id, voice=content, caption=caption, **reply_kwargs)
    elif msg_type == "audio":
        await bot.send_audio(chat_id=chat_id, audio=content, caption=caption, **reply_kwargs)
    elif msg_type == "animation":
        await bot.send_animation(chat_id=chat_id, animation=content, caption=caption, **reply_kwargs)
    elif msg_type == "video_note":
        await bot.send_video_note(chat_id=chat_id, video_note=content, **reply_kwargs)
    elif msg_type == "contact":
        d = json.loads(content)
        await bot.send_contact(chat_id=chat_id, phone_number=d["phone_number"], first_name=d["first_name"], last_name=d.get("last_name"), vcard=d.get("vcard"), **reply_kwargs)
    elif msg_type == "location":
        d = json.loads(content)
        await bot.send_location(chat_id=chat_id, latitude=d["latitude"], longitude=d["longitude"], **reply_kwargs)
    elif msg_type == "venue":
        d = json.loads(content)
        await bot.send_venue(chat_id=chat_id, latitude=d["latitude"], longitude=d["longitude"], title=d["title"], address=d["address"], **reply_kwargs)
    elif msg_type == "poll":
        d = json.loads(content)
        await bot.send_poll(chat_id=chat_id, question=d["question"], options=d["options"], is_anonymous=d.get("is_anonymous", True), type=d.get("type", "regular"), allows_multiple_answers=d.get("allows_multiple_answers", False), **reply_kwargs)
    elif msg_type == "dice":
        await bot.send_dice(chat_id=chat_id, emoji=content, **reply_kwargs)
    else:
        await bot.send_message(chat_id=chat_id, text=content, **reply_kwargs)


async def check_scheduled_messages(context):
    scheduled = load_json(SCHEDULED_FILE, [])
    if not scheduled:
        return

    now = datetime.now(timezone.utc)
    remaining = []

    for item in scheduled:
        try:
            send_time_str = item["scheduled_time"]
            if send_time_str.endswith("Z"):
                send_time_str = send_time_str.replace("Z", "+00:00")
            send_time = datetime.fromisoformat(send_time_str)
            if send_time.tzinfo is None:
                send_time = send_time.replace(tzinfo=CAMBODIA_TZ)

            if now >= send_time:
                try:
                    reply_id = item.get("reply_to_message_id")
                    await send_any_message(
                        context.bot, int(item["group_id"]), item,
                        reply_to_message_id=int(reply_id) if reply_id else None
                    )
                except Exception as send_err:
                    print(f"[Scheduler] Error sending: {send_err}")
                    remaining.append(item)
            else:
                remaining.append(item)
        except Exception as e:
            print(f"[Scheduler] Parse error: {e}")
            remaining.append(item)

    save_json(SCHEDULED_FILE, remaining)


# ─── Extract message content ─────────────────────────────────────────────────

def extract_message_content(msg):
    if msg.forward_origin is not None:
        return "forward", str(msg.message_id), str(msg.chat.id)
    if msg.text:
        return "text", msg.text, None
    elif msg.photo:
        return "photo", msg.photo[-1].file_id, msg.caption
    elif msg.video:
        return "video", msg.video.file_id, msg.caption
    elif msg.document:
        return "document", msg.document.file_id, msg.caption
    elif msg.sticker:
        return "sticker", msg.sticker.file_id, None
    elif msg.voice:
        return "voice", msg.voice.file_id, msg.caption
    elif msg.audio:
        return "audio", msg.audio.file_id, msg.caption
    elif msg.animation:
        return "animation", msg.animation.file_id, msg.caption
    elif msg.video_note:
        return "video_note", msg.video_note.file_id, None
    elif msg.contact:
        c = msg.contact
        return "contact", json.dumps({"phone_number": c.phone_number, "first_name": c.first_name, "last_name": c.last_name, "vcard": c.vcard}), None
    elif msg.location and not msg.venue:
        loc = msg.location
        return "location", json.dumps({"latitude": loc.latitude, "longitude": loc.longitude}), None
    elif msg.venue:
        v = msg.venue
        return "venue", json.dumps({"latitude": v.location.latitude, "longitude": v.location.longitude, "title": v.title, "address": v.address}), None
    elif msg.poll:
        p = msg.poll
        return "poll", json.dumps({"question": p.question, "options": [o.text for o in p.options], "is_anonymous": p.is_anonymous, "type": p.type, "allows_multiple_answers": p.allows_multiple_answers}), None
    elif msg.dice:
        return "dice", msg.dice.emoji, None
    return None, None, None


# ─── Private message handler ─────────────────────────────────────────────────

async def handle_private_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        return

    user_id = str(user.id)
    pending = load_json(PENDING_FILE, {})
    text = update.message.text or ""

    if is_admin(user.id):
        if text == BTN_SCHEDULE:
            await do_schedule(update, context)
            return

        if text == BTN_LIST:
            await do_list(update, context)
            return

    if text == BTN_CANCEL:
        if user_id in pending:
            del pending[user_id]
            save_json(PENDING_FILE, pending)
        await reply_custom_emoji(
            update.message,
            reply_markup=main_menu_keyboard() if is_admin(user.id) else ReplyKeyboardRemove(),
            do_quote=True,
        )
        return

    if text.startswith("✅ រួចរាល់"):
        if user_id not in pending or pending[user_id].get("step") != STEP_COLLECT_MESSAGES:
            await update.message.reply_text(
                "❌ គ្មានការ schedule ដែលត្រូវបញ្ជាក់!",
                reply_markup=main_menu_keyboard() if is_admin(user.id) else ReplyKeyboardRemove(),
                do_quote=True
            )
            return

        schedule = pending[user_id]
        messages = schedule.get("messages", [])

        if not messages:
            await update.message.reply_text(
                "❌ សូមបញ្ចូលសារជាមុនសិន!",
                reply_markup=collect_keyboard(0),
                do_quote=True
            )
            return

        del pending[user_id]
        save_json(PENDING_FILE, pending)

        group_id = schedule["group_id"]
        group_title = schedule["group_title"]
        scheduled_time_raw = schedule["scheduled_time"]
        reply_to_message_id = schedule.get("reply_to_message_id")
        if reply_to_message_id:
            reply_to_message_id = int(reply_to_message_id)
        send_time, display_str = format_display_time(scheduled_time_raw)
        now = datetime.now(timezone.utc)
        chat_id = update.effective_chat.id
        prompt_msg_ids = schedule.get("prompt_msg_ids", [])

        if send_time and now >= send_time:
            try:
                for msg_item in messages:
                    await send_any_message(context.bot, int(group_id), msg_item, reply_to_message_id=reply_to_message_id)
                await update.message.reply_text(
                    f"✅ សារត្រូវបានផ្ញើទៅក្រុម *{group_title}* រួចរាល់",
                    parse_mode="Markdown",
                    reply_markup=main_menu_keyboard(),
                    do_quote=True
                )
            except Exception as e:
                await update.message.reply_text(
                    f"❌ មានបញ្ហា: {e}",
                    reply_markup=main_menu_keyboard(),
                    do_quote=True
                )
        else:
            scheduled = load_json(SCHEDULED_FILE, [])
            existing_keys = set()
            for s in scheduled:
                key = str(s.get("group_id", "")) + "|" + str(s.get("scheduled_time", ""))
                existing_keys.add(key)
            schedule_number = len(existing_keys) + 1
            for msg_item in messages:
                scheduled.append({
                    "group_id": str(group_id),
                    "group_title": group_title,
                    "msg_type": msg_item["msg_type"],
                    "content": msg_item["content"],
                    "caption": msg_item["caption"],
                    "scheduled_time": scheduled_time_raw,
                    "scheduled_time_display": display_str,
                    "user_chat_id": str(update.effective_chat.id),
                    "reply_to_message_id": reply_to_message_id,
                    "schedule_number": schedule_number
                })
            save_json(SCHEDULED_FILE, scheduled)

            await update.message.reply_text(
                f"✅ Schedule រួចរាល់ *#{schedule_number}*\n\n"
                f"🔸 ក្រុម: *{group_title}*\n"
                f"🔸 ម៉ោងផ្ញើ: {display_str}\n"
                f"🔸 សារ: {len(messages)} សារ",
                parse_mode="Markdown",
                reply_markup=main_menu_keyboard(),
                do_quote=True
            )

        for msg_id in prompt_msg_ids:
            try:
                await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
            except Exception:
                pass
        return

    if user_id in pending and pending[user_id].get("step") == STEP_ENTER_TIME:
        if not text:
            await update.message.reply_text(
                "ទម្រង់មិនត្រឹមត្រូវ `DD-MM-YYYY HH:MM`",
                parse_mode="Markdown",
                do_quote=True
            )
            return

        dt = parse_time_input(text)
        if dt is None:
            await update.message.reply_text(
                "ទម្រង់មិនត្រឹមត្រូវ `DD-MM-YYYY HH:MM`",
                parse_mode="Markdown",
                do_quote=True
            )
            return

        if dt <= datetime.now(CAMBODIA_TZ):
            await update.message.reply_text(
                "សូមជ្រើសរើសម៉ោងពេលខាងមុខ។",
                do_quote=True
            )
            return

        schedule = pending[user_id]
        display_str = dt.strftime("%d-%m-%Y %H:%M")
        schedule["step"] = STEP_COLLECT_MESSAGES
        schedule["scheduled_time"] = dt.isoformat()
        schedule["messages"] = []
        schedule["prompt_msg_ids"] = []
        pending[user_id] = schedule
        save_json(PENDING_FILE, pending)

        prompt_msg = await update.message.reply_text(
            f"⏰ ម៉ោង: *{display_str}*\n\n"
            f"📨 សូមផ្ញើសារដែលចង់ schedule:\n"
            f"🔸 ក្រុម: *{schedule['group_title']}*\n"
            f"🔸 ម៉ោងផ្ញើ: {display_str}\n\n"
            f"_(ផ្ញើបានច្រើនសារ បន្ទាប់មកចុច \"✅ រួចរាល់\")_",
            parse_mode="Markdown",
            reply_markup=collect_keyboard(0),
            do_quote=True
        )
        schedule["prompt_msg_ids"].append(prompt_msg.message_id)
        pending[user_id] = schedule
        save_json(PENDING_FILE, pending)
        return

    if user_id in pending and pending[user_id].get("step") == STEP_COLLECT_MESSAGES:
        schedule = pending[user_id]
        msg_type, content, caption = extract_message_content(update.message)

        if msg_type is None:
            await update.message.reply_text(
                "❌ ប្រភេទសារនេះមិនអាច schedule បានទេ!",
                do_quote=True
            )
            return

        if "messages" not in schedule:
            schedule["messages"] = []
        schedule["messages"].append({"msg_type": msg_type, "content": content, "caption": caption})
        pending[user_id] = schedule
        save_json(PENDING_FILE, pending)

        group_title = schedule["group_title"]
        _, display_str = format_display_time(schedule["scheduled_time"])
        count = len(schedule["messages"])

        prompt_msg = await update.message.reply_text(
            f"📨 *{count} សារ* បានបញ្ចូល\n\n"
            f"🔸 ក្រុម: *{group_title}*\n"
            f"🔸 ម៉ោងផ្ញើ: {display_str}\n\n"
            f"_(ផ្ញើសារបន្ថែម ឬ ចុច \"✅ រួចរាល់\" ដើម្បីបញ្ជាក់)_",
            parse_mode="Markdown",
            reply_markup=collect_keyboard(count),
            do_quote=True
        )
        if "prompt_msg_ids" not in schedule:
            schedule["prompt_msg_ids"] = []
        schedule["prompt_msg_ids"].append(prompt_msg.message_id)
        pending[user_id] = schedule
        save_json(PENDING_FILE, pending)
        return

    if is_admin(user.id):
        await update.message.reply_text(
            "ជ្រើសរើសមុខងារ៖",
            reply_markup=main_menu_keyboard(),
            do_quote=True
        )


# ─── Application builder ──────────────────────────────────────────────────────

def build_application(with_job_queue: bool = True):
    builder = ApplicationBuilder().token(TOKEN)
    application = builder.build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(handle_callback))
    application.add_handler(ChatMemberHandler(track_my_chat_member, ChatMemberHandler.MY_CHAT_MEMBER))
    application.add_handler(MessageHandler(
        ~filters.COMMAND & filters.ChatType.GROUPS,
        track_group_message
    ))
    application.add_handler(MessageHandler(
        ~filters.COMMAND & filters.ChatType.PRIVATE,
        handle_private_message
    ))

    if with_job_queue and application.job_queue:
        application.job_queue.run_repeating(check_scheduled_messages, interval=1, first=1)

    return application
