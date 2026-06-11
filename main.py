import logging
import os
import asyncio
import json
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from web3 import Web3
# Library tambahan untuk AI Gemini
import google.generativeai as genai

# Memuat data rahasia dari file .env
load_dotenv(override=True) 

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

if not TOKEN:
    print("ERROR: Variabel TELEGRAM_BOT_TOKEN tidak ditemukan!")
    exit(1)
print("Bot berhasil mengambil token, sedang berjalan...")

# Konfigurasi Logging agar bot bisa lapor kalau ada eror
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Mengambil data dari .env
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
WALLET_PRIVATE_KEY = os.getenv("WALLET_PRIVATE_KEY")
WEB3_PROVIDER_URL = os.getenv("WEB3_PROVIDER_URL")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Inisialisasi AI Gemini jika kunci API tersedia
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
else:
    print("PERINGATAN: GEMINI_API_KEY tidak ditemukan di .env. Fitur AI tidak akan merespon chat biasa.")

# --- KUMPULAN FUNGSI OTODIDAK AI ---

def get_ai_response(user_message: str) -> str:
    """Fungsi untuk mengirim pesan kamu ke AI Gemini dan mengambil jawabannya."""
    if not GEMINI_API_KEY:
        return "Maaf Boss, otak AI saya belum diaktifkan karena GEMINI_API_KEY belum dipasang di .env."
    
    try:
        # Menggunakan model gemini-1.5-flash yang cepat dan pintar
        model = genai.GenerativeModel('models/gemini-1.5-flash')
        
        # Memberikan instruksi sifat/karakter si AI (System Prompt)
        system_instruction = (
            "Kamu adalah Asisten Cuan Maximal, seorang AI Agent programmer yang ahli dalam "
            "otomatisasi airdrop crypto dan blockchain. Jawablah pertanyaan user dengan santai, "
            "panggil user dengan sebutan 'Boss', gunakan bahasa Indonesia yang mudah dipahami, "
            "dan berikan sedikit sentuhan humor tentang dunia crypto/cuan jika cocok."
        )
        
        full_prompt = f"{system_instruction}\n\nUser berkata: {user_message}"
        response = model.generate_content(full_prompt)
        return response.text
    except Exception as e:
        return f"Aduh Boss, otak AI saya sedang error: {e}"

# --- KUMPULAN FUNGSI HANDLER TELEGRAM ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('Halo Boss! Asisten Cuan Maximal siap menerima perintah. Ketik /check_balance, /random_task, atau langsung CHAT saja apa yang mau kamu tanyakan ke AI!')

async def check_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('Mengecek saldo di blockchain... mohon tunggu.')
    if not WEB3_PROVIDER_URL:
        await update.message.reply_text('URL Provider Web3 belum diisi di .env!')
        return
        
    try:
        w3 = Web3(Web3.HTTPProvider(WEB3_PROVIDER_URL))
        if w3.is_connected():
            from eth_account import Account
            account = Account.from_key(WALLET_PRIVATE_KEY)
            balance_wei = w3.eth.get_balance(account.address)
            balance_eth = w3.from_wei(balance_wei, 'ether')
            await update.message.reply_text(f'✅ Koneksi Web3 Sukses!\n\nAlamat Dompet: {account.address}\nSaldo: {balance_eth} ETH')
        else:
            await update.message.reply_text('❌ Gagal terhubung ke blockchain.')
    except Exception as e:
        await update.message.reply_text(f'Terjadi kesalahan: {e}')

async def random_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('Memulai task acak... bot sedang bekerja (pura-puranya).')
    await asyncio.sleep(2) 
    await update.message.reply_text('✅ Task selesai! Cuan berhasil diamankan. 💸')

async def handle_ai_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Menangani chat teks biasa dari user dan menjawabnya menggunakan Gemini AI."""
    user_text = update.message.text
    
    # Memberi tahu user kalau AI sedang mengetik/berpikir
    status_msg = await update.message.reply_text("🤖 *Asisten sedang berpikir...*")
    
    # Menjalankan fungsi Gemini secara asinkron agar bot tidak macet
    loop = asyncio.get_running_loop()
    ai_reply = await loop.run_in_executor(None, get_ai_response, user_text)
    
    # Mengubah pesan "sedang berpikir" menjadi jawaban asli dari AI
    await status_msg.edit_text(ai_reply)

# --- FUNGSI UTAMA (MESIN BOT) ---

def main():
    if not TELEGRAM_BOT_TOKEN:
        print("ERROR PARAH: Token bot belum diisi di file .env!")
        return

    # Membuat aplikasi bot dari Token
    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    # Mendaftarkan perintah garis miring (/)
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("check_balance", check_balance))
    application.add_handler(CommandHandler("random_task", random_task))

    # BARU: Mendaftarkan resepsionis untuk membaca CHAT TEKS BIASA dan menjawab pakai AI
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_ai_chat))

    print("Bot berhasil dinyalakan dan siap menerima perintah serta chat AI dari Telegram!")
    
    # Membiarkan bot menyala 24 jam nonstop
    application.run_polling()

if __name__ == '__main__':
    main()
