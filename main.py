import re
import json
import time
import logging
import os
import asyncio
import random
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from web3 import Web3
import google.generativeai as genai

# Library Resmi Browser Otomatis (Selenium) - Sudah Bersih & Rapi
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import StaleElementReferenceException, ElementClickInterceptedException

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
MEMORY_FILE = "data_memory.json"

def save_to_memory(url, action_name, xpath):
    data = {}
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, 'r') as f:
            data = json.load(f)
    
    if url not in data:
        data[url] = {}
    
    data[url][action_name] = xpath
    with open(MEMORY_FILE, 'w') as f:
        json.dump(data, f, indent=4)

def get_from_memory(url, action_name):
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, 'r') as f:
            data = json.load(f)
            return data.get(url, {}).get(action_name)
    return None

def initialize_selenium_driver():
    """Fungsi pembuka browser murni di dalam lingkungan Docker Linux"""
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new") # Wajib di server cloud
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=414,896")
    options.add_argument("user-agent=Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1")
    
    # Karena ini di Docker Chrome Resmi, lokasinya otomatis terbaca oleh sistem!
    driver = webdriver.Chrome(options=options)
    logger.info("🚀 DOCKER CHROME BERHASIL MENYALA SEMPURNA!")
    return driver



# 1. PERBAIKAN FUNGSI EKSEKUTOR (Lebih Simpel & Stabil)
def execute_web_action(driver, action_type, selector_type, selector_value, input_text=None):
    """Fungsi eksekutor bersih tanpa banyak argumen ribet"""
    try:
        by = By.XPATH if selector_type == "xpath" else By.ID if selector_type == "id" else By.CSS_SELECTOR
        element = WebDriverWait(driver, 10).until(EC.presence_of_element_located((by, selector_value)))
        
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
        
        if action_type == "click":
            element.click()
        elif action_type == "type":
            element.clear()
            element.send_keys(input_text)
        return True
    except Exception as e:
        logger.error(f"Gagal eksekusi: {e}")
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
    """Perintah untuk menutup browser dengan aman"""
    global tma_driver_instance
    if tma_driver_instance:
        try:
            tma_driver_instance.quit()
        except:
            pass
        tma_driver_instance = None
        await update.message.reply_text("🔒 Browser berhasil ditutup total, Boss!")
    else:
        await update.message.reply_text("Browser memang sudah dalam posisi mati, Boss.")

async def handle_ai_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global tma_driver_instance
    user_text = update.message.text
    
    if not tma_driver_instance:
        await update.message.reply_text("⚠️ Browser belum aktif! Ketik /open_web [URL] dulu, Boss.")
        return

    status_msg = await update.message.reply_text("🤖 *Menganalisis perintah...*")
    
    # 1. AI Menganalisis & Memberikan daftar aksi
    ai_reply = await asyncio.to_thread(get_ai_decision, user_text, tma_driver_instance.page_source[:2000])
    
    # 2. Jika AI mengeluarkan perintah [ACTION:...]
    if "[ACTION:" in ai_reply:
        # Menggunakan regex untuk menangkap SEMUA aksi (bisa lebih dari satu!)
        actions = re.findall(r"\[ACTION:(.*?)\|SELECTOR:(.*?)\|VALUE:(.*?)\|INPUT:(.*?)\]", ai_reply)
        
        if actions:
            clean_reply = ai_reply.split("[ACTION:")[0].strip()
            await status_msg.edit_text(f"🤖 {clean_reply}\n\n⚡ *Menjalankan {len(actions)} aksi...*")
            
            for action, sel_type, sel_val, inp_txt in actions:
                # Bersihkan input
                input_val = None if inp_txt == "none" else inp_txt
                
                # Eksekusi aksi satu per satu
                success = await asyncio.to_thread(execute_web_action, tma_driver_instance, action, sel_type, sel_val, input_val)
                
                if not success:
                    await update.message.reply_text(f"❌ *Gagal di:* {sel_val}. Mungkin elemen belum muncul/salah selector?")
                    return # Stop jika ada yang gagal
                
                await asyncio.sleep(1) # Jeda agar bot tidak diblokir web
            
            await update.message.reply_text("✅ *Semua aksi sukses dilakukan, Boss!*")
        else:
            await status_msg.edit_text("❌ AI mengeluarkan perintah tapi formatnya tidak terbaca.")
    else:
        # Jika bukan perintah aksi, tampilkan jawaban chat biasa
        await status_msg.edit_text(ai_reply)

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
