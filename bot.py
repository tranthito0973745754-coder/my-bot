import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
import requests
import logging
import threading
import time
import os
import json
import datetime
from collections import defaultdict
import io
from PIL import Image, ImageDraw, ImageFont

# ==========================================
# ⚙️ CẤU HÌNH BẢO MẬT (LẤY TỪ RENDER)
# ==========================================
BOT_TOKEN = os.getenv("BOT_TOKEN")
DB_CHANNEL_ID = os.getenv("DB_CHANNEL_ID") 
GEMINI_KEYS = os.getenv("GEMINI_KEYS", "").split(",")

MODEL_NAME = "gemini-1.5-flash"

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("MeoMuop")

bot = telebot.TeleBot(BOT_TOKEN.strip() if BOT_TOKEN else "MISSING", threaded=True, num_threads=6)

group_streaks = {}
data_message_id = None 

# ==========================================
# 💾 CƠ CHẾ DATABASE QUA TELEGRAM
# ==========================================
def load_database_from_telegram():
    global group_streaks, data_message_id
    try:
        if not DB_CHANNEL_ID: return
        chat = bot.get_chat(DB_CHANNEL_ID)
        pinned = chat.pinned_message
        if pinned and "STREAK_DB:" in pinned.text:
            json_str = pinned.text.replace("STREAK_DB:", "").strip()
            group_streaks = json.loads(json_str)
            data_message_id = pinned.message_id
            log.info("Tải dữ liệu thành công!")
    except Exception as e:
        log.error(f"Lỗi tải DB: {e}")

def save_database_to_telegram():
    global data_message_id
    try:
        if not DB_CHANNEL_ID: return
        json_str = "STREAK_DB: " + json.dumps(group_streaks, ensure_ascii=False)
        if data_message_id:
            try:
                bot.edit_message_text(json_str, DB_CHANNEL_ID, data_message_id)
                return
            except: pass
        msg = bot.send_message(DB_CHANNEL_ID, json_str)
        data_message_id = msg.message_id
        try: bot.pin_chat_message(DB_CHANNEL_ID, data_message_id)
        except: pass
    except Exception as e:
        log.error(f"Lỗi lưu DB: {e}")

# ==========================================
# 🎨 XƯỞNG VẼ ẢNH
# ==========================================
def generate_streak_image_in_memory(days, today_msg, total_msg, tier, color_name):
    width, height = 800, 800
    try: img = Image.open("meo_template.png").convert("RGBA").resize((width, height))
    except: img = Image.new("RGBA", (width, height), (25, 30, 40, 255))
    
    draw = ImageDraw.Draw(img)
    try:
        font_title = ImageFont.truetype("arial.ttf", 55)
        font_streak = ImageFont.truetype("arial.ttf", 160)
    except: font_title = font_streak = ImageFont.load_default()

    color_map = {"Đục": (150,150,150), "⚪ Trắng": (255,255,255), "🔵 Xanh Dương": (100,180,255), "🟣 Tím": (200,100,255), "🔴 Đỏ": (255,80,80), "🟡 Vàng Kim": (255,215,0)}
    main_color = color_map.get(color_name, (255, 255, 255))

    draw.text((50, 60), "🔥 CHUỖI GẮN KẾT NHÓM 🔥", fill=(255, 180, 0), font=font_title)
    draw.text((50, 320), f"{days} NGÀY", fill=main_color, font=font_streak)
    
    bio = io.BytesIO()
    img.save(bio, 'PNG')
    bio.seek(0)
    return bio

# ==========================================
# 🧠 AI ENGINE
# ==========================================
def ask_ai(prompt):
    for key in GEMINI_KEYS:
        if not key.strip(): continue
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_NAME}:generateContent?key={key.strip()}"
            payload = {"contents": [{"parts": [{"text": prompt}]}]}
            r = requests.post(url, json=payload, timeout=10)
            if r.status_code == 200:
                return r.json()['candidates'][0]['content']['parts'][0]['text']
        except: continue
    return "Mèo đang bận, Sen thử lại sau nhé!"

# ==========================================
# 🎮 HANDLERS
# ==========================================
@bot.message_handler(func=lambda m: m.text == "🐾 THẾ GIỚI MÈO MƯỚP")
def pet_dashboard(message):
    m = InlineKeyboardMarkup()
    m.add(InlineKeyboardButton("🔥 Khoe Chuỗi Nhóm", callback_data="pet_group_streak"))
    bot.reply_to(message, "Menu quản lý nhóm:", reply_markup=m)

@bot.callback_query_handler(func=lambda call: call.data == "pet_group_streak")
def handle_streak_callback(call):
    chat_id = str(call.message.chat.id)
    g = group_streaks.get(chat_id, {"streak": 0, "today_msg": 0, "total_msg": 0})
    days = g["streak"]
    
    if days < 3: tier, color = "Chưa Sáng", "Đục"
    elif days < 10: tier, color = "Sơ Cấp", "⚪ Trắng"
    else: tier, color = "Hiếm", "🔵 Xanh Dương"

    img_bio = generate_streak_image_in_memory(days, g["today_msg"], g["total_msg"], tier, color)
    bot.send_photo(chat_id, photo=img_bio, caption=f"Chuỗi của nhóm: {days} ngày! 🔥")

@bot.message_handler(func=lambda _: True)
def main_chat(message):
    if not message.text: return
    chat_id = str(message.chat.id)
    
    if chat_id not in group_streaks:
        group_streaks[chat_id] = {"streak": 0, "last_date": "", "today_msg": 0, "total_msg": 0}
        
    g = group_streaks[chat_id]
    today = datetime.date.today().isoformat()
    
    if g["last_date"] != today:
        if g["last_date"]:
            delta = (datetime.date.today() - datetime.date.fromisoformat(g["last_date"])).days
            g["streak"] = g["streak"] + 1 if delta == 1 else 1
        else: g["streak"] = 1
        g["last_date"] = today
        g["today_msg"] = 0

    g["today_msg"] += 1
    g["total_msg"] += 1
    
    if g["today_msg"] % 5 == 0:
        threading.Thread(target=save_database_to_telegram).start()

    if f"@{bot.get_me().username}" in message.text or message.chat.type == "private":
        reply = ask_ai(message.text)
        bot.reply_to(message, reply)

if __name__ == "__main__":
    load_database_from_telegram()
    log.info("Mèo Mướp V35 đã sẵn sàng!")
    bot.infinity_polling()
