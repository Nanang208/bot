import logging
import os
import asyncio
import random
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from web3 import Web3
import google.generativeai as genai

# Library Baru untuk Browser Otomatis (Selenium)
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

# Memuat data rahasia
load_dotenv(override=True) 

# Konfigurasi Logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
WALLET_PRIVATE_KEY = os.getenv("WALLET_PRIVATE_KEY")
WEB3_PROVIDER_URL = os.getenv("WEB3_PROVIDER_URL")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Inisialisasi AI Gemini
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
else:
    print("PERINGATAN: GEMINI_API_KEY tidak ditemukan!")

# Variabel Global untuk menyimpan browser yang sedang aktif
tma_driver_instance = None

# --- FUNGSI MESIN BROWSER (SELENIUM) ---

def initialize_selenium_driver():
    """Fungsi pembuka browser yang memaksa sistem mengabaikan cache manager"""
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new") 
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=414,896") 
    options.add_argument("user-agent=Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1")
    
    # Beritahu lokasi Chromium bawaan dari railway.json
    options.binary_location = "/usr/bin/chromium"
    
    # Set opsi agar driver tidak mencoba mencari versi terbaru ke internet
    options.set_capability("browserVersion", "stable")
    
    try:
        # Panggil langsung lewat executable_path di dalam Service tanpa embel-embel
        service = Service(executable_path="/usr/bin/chromedriver")
        driver = webdriver.Chrome(service=service, options=options)
        logger.info("Sukses besar! Browser berhasil dijalankan lewat sistem Railway.")
    except Exception as e:
        logger.warning(f"Metode utama gagal, mencoba fallback: {e}")
        # Jika dicoba di laptop Windows pribadi Boss Nanang
        driver = webdriver.Chrome(options=options)
        
    return driver

def automate_tma_action(driver, action, selector_type, selector_value, input_text=None):
    """Fungsi eksekutor tangan robot untuk nge-klik atau mengetik"""
    try:
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC

        # Ubah teks jenis selector menjadi objek Selenium By
        by_type = By.XPATH
        if selector_type == "id": by_type = By.ID
        elif selector_type == "css": by_type = By.CSS_SELECTOR
        elif selector_type == "class_name": by_type = By.CLASS_NAME

        # Tunggu sampai elemen muncul di layar (maksimal 10 detik)
        element = WebDriverWait(driver, 10).until(
            EC.presence_of_element_transform((by_type, selector_value)) if hasattr(EC, 'presence_of_element_transform') else EC.presence_of_element_located((by_type, selector_value))
        )

        if action == "click":
            element.click()
            return True
        elif action == "type" and input_text:
            element.clear()
            element.send_keys(input_text)
            return True
        return False
    except Exception as e:
        logger.error(f"Gagal melakukan aksi {action}: {e}")
        return False

# --- FUNGSI OTAK AI DENGAN KONTEKS BROWSER ---

def get_ai_decision(user_message: str, page_source: str) -> str:
    """Fungsi otak AI untuk memutuskan tindakan berdasarkan isi halaman web saat ini"""
    if not GEMINI_API_KEY:
        return "Otak AI belum aktif."
    
    try:
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        # System prompt agar AI membalas normal ATAU memberikan instruksi kode rahasia jika diperintah aksi web
        system_instruction = (
            "Kamu adalah Asisten Cuan Maximal, AI Agent otomatisasi airdrop crypto.\n"
            "Panggil user dengan 'Boss'. Jika user menyuruh melakukan sesuatu di halaman web, "
            "kamu harus menganalisis HTML yang diberikan dan sertakan format perintah khusus di akhir jawabanmu "
            "dengan format: [ACTION:action_type|SELECTOR:type|VALUE:value|INPUT:text].\n"
            "Contoh jika disuruh klik tombol claim: 'Siap Boss, saya klik tombol claimnya sekarang! [ACTION:click|SELECTOR:id|VALUE:claim-btn|INPUT:none]'\n"
            "Jika hanya obrolan biasa atau HTML kosong, jawablah seperti biasa tanpa format tanda kurung tersebut."
        )
        
        # Batasi HTML agar tidak kepenuhan (4000 karakter pertama)
        html_context = page_source[:4000] if page_source else "Browser belum dibuka / halaman kosong."
        
        full_prompt = f"{system_instruction}\n\nHTML Halaman Saat Ini:\n\"\"\"\n{html_context}\n\"\"\"\n\nUser berkata: {user_message}"
        response = model.generate_content(full_prompt)
        return response.text
    except Exception as e:
        return f"Aduh Boss, otak AI saya sedang error: {e}"

# --- KUMPULAN HANDLER TELEGRAM ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('Halo Boss! Asisten Cuan Maximal + Agen Otomatisasi Browser siap! Ketik /open_web [URL] untuk buka web, atau langsung CHAT saja.')

async def open_web(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Perintah untuk menyuruh bot membuka browser ke URL tertentu"""
    global tma_driver_instance
    if not context.args:
        await update.message.reply_text("Contoh penggunaan: /open_web https://example.com")
        return
        
    url = context.args[0]
    await update.message.reply_text(f"🌐 Sedang membuka browser ke {url}... Mohon tunggu, Boss.")
    
    try:
        loop = asyncio.get_running_loop()
        if not tma_driver_instance:
            tma_driver_instance = await loop.run_in_executor(None, initialize_selenium_driver)
            
        await loop.run_in_executor(None, tma_driver_instance.get, url)
        await update.message.reply_text("✅ Browser Berhasil dibuka! Sekarang Boss bisa perintah saya lewat chat biasa untuk klik atau isi form di web itu.")
    except Exception as e:
        await update.message.reply_text(f"❌ Gagal membuka browser: {e}")

async def close_web(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Perintah untuk menutup browser"""
    global tma_driver_instance
    if tma_driver_instance:
        tma_driver_instance.quit()
        tma_driver_instance = None
        await update.message.reply_text("🔒 Browser berhasil ditutup, Boss!")
    else:
        await update.message.reply_text("Browser memang sudah dalam posisi mati, Boss.")

async def handle_ai_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Membaca chat biasa, dikirim ke AI, lalu AI otomatis menggerakkan browser jika ada perintah web"""
    global tma_driver_instance
    user_text = update.message.text
    status_msg = await update.message.reply_text("🤖 *Asisten sedang membaca situasi...*")
    
    try:
        loop = asyncio.get_running_loop()
        
        # Ambil isi halaman web saat ini (jika browser terbuka)
        page_source = ""
        if tma_driver_instance:
            page_source = await loop.run_in_executor(None, lambda: tma_driver_instance.page_source)
            
        # Tanya ke AI Gemini
        ai_reply = await loop.run_in_executor(None, get_ai_decision, user_text, page_source)
        
        # Cek apakah AI menyisipkan perintah rahasia [ACTION:...]
        if "[ACTION:" in ai_reply:
            # Tampilkan teks jawaban AI ke user dulu
            clean_reply = ai_reply.split("[ACTION:")[0].strip()
            await status_msg.edit_text(f"🤖 {clean_reply}\n\n⚡ *Menjalankan aksi otomatisasi...*")
            
            # Ekstrak data perintah rahasia dari teks AI
            import re
            match = re.search(r"\[ACTION:(.*?)\|SELECTOR:(.*?)\|VALUE:(.*?)\|INPUT:(.*?)\]", ai_reply)
            if match and tma_driver_instance:
                action, sel_type, sel_val, inp_txt = match.groups()
                if inp_txt == "none": inp_txt = None
                
                # Eksekusi gerakan Selenium secara asinkron
                success = await loop.run_in_executor(None, automate_tma_action, tma_driver_instance, action, sel_type, sel_val, inp_txt)
                
                if success:
                    await update.message.reply_text("✅ *Aksi Sukses, Boss!* Ada perintah selanjutnya?")
                else:
                    await update.message.reply_text("❌ *Gagal:* Saya tahu apa yang harus diklik, tapi elemennya mendadak hilang atau berubah di halaman web.")
        else:
            # Jika chat biasa tanpa perintah gerak browser
            await status_msg.edit_text(ai_reply)
            
    except Exception as e:
        await status_msg.edit_text(f"Aduh Boss, ada kendala teknis: {e}")

# --- FUNGSI UTAMA ---
def main():
    if not TELEGRAM_BOT_TOKEN: return
    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("open_web", open_web))
    application.add_handler(CommandHandler("close_web", close_web))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_ai_chat))

    print("Bot AI Agent + Browser siap grak!")
    application.run_polling()

if __name__ == '__main__':
    main()
