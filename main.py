import time
import undetected_chromedriver as uc
import logging
import os
import asyncio
import random
from selenium.common.exceptions import StaleElementReferenceException, ElementClickInterceptedException
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from web3 import Web3
import google.generativeai as genai

# Library Baru untuk Browser Otomatis (Selenium)
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
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



def automate_tma_action(driver, action_data):
    """Fungsi eksekusi aksi otomatis yang kebal dari elemen hilang/berubah"""
    try:
        selector_type = action_data.get("selector_type", "").lower()
        selector_value = action_data.get("selector_value", "")
        action_type = action_data.get("action_type", "").lower()
        text_to_type = action_data.get("text_to_type", "")

        # Pemetaan Selector
        by_type = By.CSS_SELECTOR
        if selector_type == "xpath":
            by_type = By.XPATH
        elif selector_type == "id":
            by_type = By.ID

        # Trik 1: Beri jeda 1 detik agar halaman benar-benar tenang/selesai memuat
        time.sleep(1.5)

        # Trik 2: Lakukan perulangan (Retries) sebanyak 3 kali jika elemen mendadak berubah
        for attempt in range(3):
            try:
                element = WebDriverWait(driver, 15).until(
                    EC.presence_of_element_located((by_type, selector_value))
                )
                
                # Pastikan elemen bisa diklik
                element = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((by_type, selector_value))
                )

                if action_type == "click":
                    # Trik 3: Gunakan JavaScript Click jika klik standar Selenium diblokir/berubah
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
                    time.sleep(0.5)
                    try:
                        element.click()
                    except (ElementClickInterceptedException, StaleElementReferenceException):
                        driver.execute_script("arguments[0].click();", element)
                        
                elif action_type == "type":
                    element.clear()
                    element.send_keys(text_to_type)
                
                return True # Sukses! Keluar dari fungsi
                
            except StaleElementReferenceException:
                if attempt == 2: raise # Jika sudah 3x gagal, lempar eror
                logger.warning(f"Elemen berubah mendadak, mencoba ulang ke-{attempt+1}...")
                time.sleep(1) # Tunggu semenit sebelum coba lagi
                
    except Exception as e:
        logger.error(f"Gagal eksekusi aksi otomatis: {e}")
        raise e

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
