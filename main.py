import os
import threading
import psycopg2
import telebot
from flask import Flask

# 1. Cấu hình Flask để "đánh lừa" Render không bị tắt (Web Service)
app = Flask(__name__)


@app.route("/")
def home():
    return "Bot đang chạy ngon lành!"


def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)


# 2. Kết nối Database Neon Postgres
DATABASE_URL = os.environ.get("DATABASE_URL")


def init_db():
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        # Tạo bảng mẫu để lưu nhật ký/dữ liệu nếu chưa có
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS bot_logs (
                id SERIAL PRIMARY KEY,
                user_id BIGINT,
                username TEXT,
                message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """
        )
        conn.commit()
        cursor.close()
        conn.close()
        print("Khởi tạo database Neon thành công!")
    except Exception as e:
        print(f"Lỗi database: {e}")


# 3. Cấu hình Telegram Bot
BOT_TOKEN = os.environ.get("BOT_TOKEN")
bot = telebot.TeleBot(BOT_TOKEN)


@bot.message_handler(commands=["start"])
def send_welcome(message):
    bot.reply_to(
        message,
        "Chào mừng bạn! Bot đã kết nối thành công với database Neon trên Render. Hãy gửi tin nhắn để lưu thử vào database.",
    )


@bot.message_handler(func=lambda message: True)
def save_to_db(message):
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO bot_logs (user_id, username, message) VALUES (%s, %s, %s)",
            (message.from_user.id, message.from_user.username, message.text),
        )
        conn.commit()
        cursor.close()
        conn.close()
        bot.reply_to(message, "Đã lưu thông tin vào database Neon!")
    except Exception as e:
        bot.reply_to(message, f"Gặp lỗi khi lưu vào database: {e}")


if __name__ == "__main__":
    # Khởi chạy database
    init_db()

    # Chạy Web Server ở luồng riêng để Render vượt qua kiểm tra Port
    threading.Thread(target=run_web_server, daemon=True).start()

    # Bắt đầu chạy bot
    print("Bot đang bắt đầu lắng nghe...")
    bot.infinity_polling()
