import os
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes
import yt_dlp

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

async def handle_incoming(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = None
    
    # 判斷是從 Mini App 傳回的資料，還是直接傳送的訊息
    if update.message and update.message.web_app_data:
        url = update.message.web_app_data.data
    elif update.message and update.message.text:
        url = update.message.text.strip()

    if not url or not url.startswith("http"):
        return

    status_msg = await update.message.reply_text("⏳ 正在透過高速核心解析並下載影片，請稍候...")

    output_template = "video_temp.mp4"
    ydl_opts = {
        'format': 'best[filesize<50M]/best', # 自動選擇小於50MB的最高畫質以符合TG限制
        'outtmpl': output_template,
        'noplaylist': True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)

        # 直接將乾淨的影片檔發送到聊天室
        with open(filename, 'rb') as video_file:
            await update.message.reply_video(video=video_file, caption="✅ 下載完成！由 YoinkBot 提供")

        # 清理暫存檔
        if os.path.exists(filename):
            os.remove(filename)
        await status_msg.delete()

    except Exception as e:
        logging.error(f"Download error: {e}")
        await status_msg.edit_text("❌ 下載失敗：可能是影片過大、網址失效或受區域限制。")

def main():
    # 請換上你的真實 Bot Token
    app = ApplicationBuilder().token("YOUR_BOT_TOKEN").build()

    # 監聽一般文字訊息與 Mini App 傳回的資料
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_incoming))
    app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, handle_incoming))

    print("Bot is running...")
    app.run_polling()

if __name__ == '__main__':
    main()
