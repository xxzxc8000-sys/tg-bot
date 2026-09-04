import os
import yt_dlp
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text
    if not url.startswith("http"):
        return

    msg = await update.message.reply_text("📥 正在為您處理並下載無廣告影片，請稍候...")

    ydl_opts = {
        'format': 'best',
        'outtmpl': 'downloaded_video.mp4',
        'max_filesize': 50 * 1024 * 1024, # 限制 50MB 內直接傳送
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)

        # 直接將影片檔案發送給使用者
        with open(filename, 'rb') as video_file:
            await update.message.reply_video(videoär=video_file)
        
        os.remove(filename)
        await msg.delete()
    except Exception as e:
        await msg.edit_text(f"❌ 下載失敗：請確保網址正確或檔案小於 50MB。")

# 啟動 Bot
app = ApplicationBuilder().token("YOUR_BOT_TOKEN").build()
app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
app.run_polling()
