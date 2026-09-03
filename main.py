import os
import logging
import asyncio
from pathlib import Path
import yt_dlp
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# 設定 Log 紀錄格式
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# 從環境變數讀取 Bot Token
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TMP_DIR = Path("tmp_downloads")
TMP_DIR.mkdir(exist_ok=True)

# Telegram Bot API 單檔傳送上限（50MB）
MAX_FILE_SIZE = 50 * 1024 * 1024

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 歡迎使用影片下載 Bot！\n請直接傳送影片網址（如 YouTube / IG 等），我會幫你下載並回傳給你。"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()
    if not text.startswith("http"):
        await update.message.reply_text("請傳送有效的網址（需以 http:// 或 https:// 開頭）。")
        return

    status_msg = await update.message.reply_text("⏳ 解析與下載中，請稍候...")
    local_path: Path | None = None

    try:
        # 設定檔案下載樣板與 yt-dlp 參數
        output_template = str(TMP_DIR / f"{update.message.message_id}_%(title)s.%(ext)s")
        ydl_opts = {
            'outtmpl': output_template,
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'max_filesize': MAX_FILE_SIZE,
            'quiet': True,
            'no_warnings': True,
        }

        # 執行同步下載邏輯
        def run_ytdlp():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(text, download=True)
                filename = ydl.prepare_filename(info)
                return Path(filename)

        # 避免阻塞 Telegram 輪詢，將同步下載丟至背景執行
        loop = asyncio.get_running_loop()
        local_path = await loop.run_in_executor(None, run_ytdlp)

        if not local_path.exists():
            await status_msg.edit_text("❌ 解析失敗或找不到下載檔案。")
            return

        await status_msg.edit_text("📤 下載完成，正在傳送影片給您...")

        # 傳送影片回 Telegram 聊天室
        with open(local_path, "rb") as f:
            await update.message.reply_video(video=f, filename=local_path.name)

        await status_msg.edit_text("✅ 完成！")

    except Exception as e:
        logger.exception("處理影片時發生錯誤")
        await status_msg.edit_text(f"❌ 處理失敗（可能無效連結或檔案超過 50MB 上限）：{e}")
    finally:
        # 下載完成或失敗後，自動清除伺服器暫存檔
        if local_path and local_path.exists():
            try:
                local_path.unlink()
            except OSError:
                pass

def main():
    if not TOKEN:
        raise RuntimeError("環境變數 TELEGRAM_BOT_TOKEN 未設定")

    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info("Bot 已啟動...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
