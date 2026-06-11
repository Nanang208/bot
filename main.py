import logging
import os
import asyncio
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from web3 import Web3

# Memuat data rahasia dari file .env
load_dotenv()

# Konfigurasi Logging agar bot bisa lapor kalau ada eror
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Mengambil data dari .env
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
WALLET_PRIVATE_KEY = os.getenv("WALLET_PRIVATE_KEY")
WEB3_PROVIDER_URL = os.getenv("WEB3_PROVIDER_URL")

# --- KUMPULAN FUNGSI HANDLER ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('Halo Boss! Asisten Cuan Maximal siap menerima perintah. Ketik /check_balance atau /random_task.')

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
    await asyncio.sleep(2) # Jeda 2 detik seolah-olah bot lagi loading
    await update.message.reply_text('✅ Task selesai! Cuan berhasil diamankan. 💸')

# --- FUNGSI UTAMA (MESIN BOT) ---

def main():
    if not TELEGRAM_BOT_TOKEN:
        print("ERROR PARAH: Token bot belum diisi di file .env!")
        return

    # Membuat aplikasi bot dari Token
    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    # Mendaftarkan "resepsionis" (Handler)
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("check_balance", check_balance))
    application.add_handler(CommandHandler("random_task", random_task))

    print("Bot berhasil dinyalakan dan siap menerima perintah dari Telegram!")
    
    # Membiarkan bot menyala 24 jam nonstop
    application.run_polling()

if __name__ == '__main__':
    main()