import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.constants import ParseMode, ChatAction
from memory import add_knowledge, get_all_knowledge, delete_knowledge, build_system_prompt
from ai_engine import get_ai_response
from tools import get_crypto_price, is_price_query

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

OWNER_ID = int(os.getenv("OWNER_TELEGRAM_ID", "0"))

def is_owner(update: Update) -> bool:
    return update.effective_user.id == OWNER_ID

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update): return
    await update.message.reply_text(
        "🤖 *AirdropBot AI aktif!*\n\n"
        "Aku siap bantu kamu bikin kode, debug error, cek harga crypto, dan otomatisasi airdrop/farming.\n\n"
        "*Commands:*\n"
        "💬 Chat langsung — ngobrol, minta kode, tanya harga crypto\n"
        "/learn — ajari aku kode atau pengetahuan baru\n"
        "/knowledge — lihat semua yang sudah aku pelajari\n"
        "/forget [no] — hapus pengetahuan tertentu\n"
        "/help — panduan lengkap",
        parse_mode=ParseMode.MARKDOWN
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update): return
    await update.message.reply_text(
        "📖 *Panduan AirdropBot AI*\n\n"
        "*💬 Chat:*\n"
        "Ketik langsung — ngobrol, minta kode, paste error, tanya harga crypto\n\n"
        "*💰 Harga Crypto Real-time:*\n"
        "Cukup tanya: `harga BTC`, `price ETH`, `berapa harga SOL`\n\n"
        "*🧠 Ajarkan Pengetahuan:*\n"
        "`/learn [kode atau info]`\n"
        "Tersimpan permanen di database!\n\n"
        "*📚 Kelola Pengetahuan:*\n"
        "`/knowledge` — lihat semua\n"
        "`/forget 3` — hapus nomor 3\n\n"
        "*💡 Tips:*\n"
        "• Paste error langsung ke chat untuk diperbaiki\n"
        "• Bot auto fallback Gemini → Groq jika limit\n"
        "• Semua pembelajaran tersimpan permanen di MongoDB",
        parse_mode=ParseMode.MARKDOWN
    )

async def learn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update): return
    text = update.message.text.replace("/learn", "").strip()
    if not text:
        await update.message.reply_text(
            "❓ Format: `/learn [kode atau info yang mau diajarkan]`",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    await update.message.reply_chat_action(ChatAction.TYPING)

    analysis_prompt = f"""User ingin mengajarkan kamu pengetahuan/kode baru ini:

{text}

Analisa dalam 3-4 kalimat singkat:
1. Ini kode/info tentang apa
2. Teknik atau library apa yang dipakai
3. Bagaimana ini berguna ke depannya

Jawab santai dalam bahasa Indonesia."""

    reply, _ = get_ai_response(analysis_prompt)

    text_lower = text.lower()
    if any(w in text_lower for w in ["import", "def ", "class ", "selenium", "playwright", "requests"]):
        label = "kode"
    elif any(w in text_lower for w in ["game", "airdrop", "farm", "claim", "token"]):
        label = "airdrop/game"
    elif any(w in text_lower for w in ["api", "endpoint", "http", "url"]):
        label = "api/endpoint"
    else:
        label = "umum"

    kid = add_knowledge(text, label)

    await update.message.reply_text(
        f"✅ *Pengetahuan #{kid} tersimpan permanen!*\n"
        f"📂 Kategori: `{label}`\n\n"
        f"🧠 *Analisa:*\n{reply}",
        parse_mode=ParseMode.MARKDOWN
    )

async def knowledge(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update): return
    items = get_all_knowledge()
    if not items:
        await update.message.reply_text("📭 Belum ada pengetahuan.\n\nGunakan /learn untuk mengajariku!")
        return

    text = f"📚 *Pengetahuan Bot ({len(items)} item):*\n\n"
    for k in items:
        preview = k["content"][:80] + "..." if len(k["content"]) > 80 else k["content"]
        text += f"*#{k['id']}* [{k['label']}] — {k['added_at']}\n`{preview}`\n\n"
    text += "Hapus dengan: `/forget [nomor]`"

    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

async def forget(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update): return
    args = context.args
    if not args or not args[0].isdigit():
        await update.message.reply_text("Format: `/forget [nomor]`", parse_mode=ParseMode.MARKDOWN)
        return

    kid = int(args[0])
    if delete_knowledge(kid):
        await update.message.reply_text(f"🗑️ Pengetahuan #{kid} dihapus.")
    else:
        await update.message.reply_text(f"❌ Pengetahuan #{kid} tidak ditemukan.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update): return

    user_text = update.message.text
    await update.message.reply_chat_action(ChatAction.TYPING)

    # Cek dulu apakah tanya harga crypto
    if is_price_query(user_text):
        price_result = get_crypto_price(user_text)
        if price_result:
            await update.message.reply_text(price_result, parse_mode=ParseMode.MARKDOWN)
            return

    # Chat biasa ke AI
    reply, provider = get_ai_response(user_text)

    footer = "\n\n_⚡ via Groq_" if provider == "groq" else ""
    full_reply = reply + footer

    if len(full_reply) > 4096:
        chunks = [full_reply[i:i+4096] for i in range(0, len(full_reply), 4096)]
        for chunk in chunks:
            try:
                await update.message.reply_text(chunk, parse_mode=ParseMode.MARKDOWN)
            except:
                await update.message.reply_text(chunk)
    else:
        try:
            await update.message.reply_text(full_reply, parse_mode=ParseMode.MARKDOWN)
        except:
            await update.message.reply_text(reply)

def main():
    token = os.getenv("TELEGRAM_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_TOKEN tidak ditemukan!")
    if OWNER_ID == 0:
        raise ValueError("OWNER_TELEGRAM_ID tidak ditemukan!")

    app = Application.builder().token(token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("learn", learn))
    app.add_handler(CommandHandler("knowledge", knowledge))
    app.add_handler(CommandHandler("forget", forget))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("🤖 AirdropBot AI berjalan...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
