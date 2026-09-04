import os
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes
import yt_dlp

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

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

def main():
    # 請換上你的真實 Bot Token
    TOKEN = "你的真實_BOT_TOKEN"
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))

    print("Bot is polling...")
    # 使用 run_polling，讓 Render 背景穩定抓取訊息
    app.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
