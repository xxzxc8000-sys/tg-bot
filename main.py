import os
import logging
from flask import Flask, request
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes
import yt_dlp

logging.basicConfig(level=logging.INFO)

TOKEN = "你的真實_BOT_TOKEN"
app_flask = Flask(__name__)

# 初始化 python-telegram-bot
telegram_app = Application.builder().token(TOKEN).build()

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text
    if not url or not url.startswith("http"):
        return

    status_msg = await update.message.reply_text("⏳ 正在下載無廣告影片，請稍候...")

    output_template = "video_temp.mp4"
    ydl_opts = {
        'format': 'best[filesize<50M]/best',
        'outtmpl': output_template,
        'noplaylist': True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)

        with open(filename, 'rb') as video_file:
            await update.message.reply_video(video=video_file, caption="✅ 下載完成！")

        if os.path.exists(filename):
            os.remove(filename)
        await status_msg.delete()
    except Exception as e:
        logging.error(f"Error: {e}")
        await status_msg.edit_text("❌ 下載失敗：請確保網址正確或檔案小於 50MB。")

telegram_app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))

@app_flask.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), telegram_app.bot)
    telegram_app.update_queue.put(update)
    return "OK"

@app_flask.route("/")
def index():
    return "Bot is running!"

async def setup_webhook():
    # 自動綁定 Render 網址 (請把下方網址換成你的 Render 網址)
    render_url = f"https://你的專案名稱.onrender.com/{TOKEN}"
    await telegram_app.bot.set_webhook(url=render_url)

if __name__ == "__main__":
    # 啟動時順便設定 Webhook
    import asyncio
    asyncio.run(setup_webhook())
    
    port = int(os.environ.get("PORT", 10000))
    app_flask.run(host="0.0.0.0", port=port)
