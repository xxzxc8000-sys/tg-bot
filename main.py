import os
import logging
import asyncio
import threading
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
import yt_dlp
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    WebAppInfo,
    InlineQueryResultArticle,
    InputTextMessageContent,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    InlineQueryHandler,
    ContextTypes,
    filters,
)

# 設定 Log 紀錄格式
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TMP_DIR = Path("tmp_downloads")
TMP_DIR.mkdir(exist_ok=True)

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB 上限

# 假 Web 伺服器通過 Render Health Check
class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is live!")

def run_dummy_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), SimpleHTTPRequestHandler)
    server.serve_forever()

# 建立備用下載管道按鈕（Mini App 與 Web 連結）
def get_fallback_keyboard(url: str = ""):
    keyboard = [
        [
            InlineKeyboardButton(
                "🚀 開啟 YT1S 下載器 (Mini App)", 
                web_app=WebAppInfo(url="https://wwv-yt1s.com")
            )
        ],
        [
            InlineKeyboardButton("🌐 SSYOU 線上下載", url="https://ssyou.online/"),
            InlineKeyboardButton("⚡ YT1S 備用網頁", url="https://wwv-yt1s.com")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 歡迎使用 YoinkBot！\n\n"
        "1. 直接傳送影片網址，我會自動幫你下載。\n"
        "2. 點擊下方按鈕可直接開啟內建下載介面。\n"
        "3. 在任何聊天室輸入 `@OopsYoinkBot 網址` 即可快速呼叫！",
        reply_markup=get_fallback_keyboard()
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()
    if not text.startswith("http"):
        await update.message.reply_text(
            "請傳送有效的網址（以 http 或 https 開頭）。",
            reply_markup=get_fallback_keyboard()
        )
        return

    status_msg = await update.message.reply_text("⏳ 解析與下載中，請稍候...")
    local_path: Path | None = None

    try:
        output_template = str(TMP_DIR / f"{update.message.message_id}_%(title)s.%(ext)s")
        ydl_opts = {
            'outtmpl': output_template,
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'max_filesize': MAX_FILE_SIZE,
            'quiet': True,
            'no_warnings': True,
            'extractor_args': {
                'youtube': {
                    'player_client': ['mweb', 'android', 'ios'],
                }
            },
        }

        def run_ytdlp():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(text, download=True)
                filename = ydl.prepare_filename(info)
                return Path(filename)

        loop = asyncio.get_running_loop()
        local_path = await loop.run_in_executor(None, run_ytdlp)

        if not local_path.exists():
            await status_msg.edit_text(
                "❌ 解析失敗。請嘗試使用以下備用管道下載：",
                reply_markup=get_fallback_keyboard(text)
            )
            return

        await status_msg.edit_text("📤 下載完成，正在傳送影片給您...")

        with open(local_path, "rb") as f:
            await update.message.reply_video(video=f, filename=local_path.name)

        await status_msg.edit_text("✅ 完成！")

    except Exception as e:
        logger.exception("處理影片時發生錯誤")
        await status_msg.edit_text(
            f"❌ 直接下載失敗（可能超過 50MB 上限或觸發限制）。\n您可以改用以下線上管道下載：",
            reply_markup=get_fallback_keyboard(text)
        )
    finally:
        if local_path and local_path.exists():
            try:
                local_path.unlink()
            except OSError:
                pass

# Inline Mode 行內搜尋處理
async def inline_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.inline_query.query.strip()
    if not query:
        return

    results = [
        InlineQueryResultArticle(
            id="1",
            title="🎬 解析並下載此影片",
            description=f"網址: {query}",
            input_message_content=InputTextMessageContent(query),
            reply_markup=get_fallback_keyboard(query)
        )
    ]
    await update.inline_query.answer(results, cache_time=1)

def main():
    if not TOKEN:
        raise RuntimeError("環境變數 TELEGRAM_BOT_TOKEN 未設定")

    threading.Thread(target=run_dummy_server, daemon=True).start()

    app = Application.builder().token(TOKEN).build()
    
    # 註冊 Handler
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(InlineQueryHandler(inline_query))

    logger.info("YoinkBot 已啟動...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
