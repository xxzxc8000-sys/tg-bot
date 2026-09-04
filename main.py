import os
import logging
import asyncio
import threading
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
import aiohttp
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

# 提供完全無廣告、開源乾淨的 Cobalt Mini App 按鈕
def get_clean_keyboard():
    keyboard = [
        [
            InlineKeyboardButton(
                "✨ 開啟 Cobalt 無廣告線上下載器", 
                web_app=WebAppInfo(url="https://cobalt.tools")
            )
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

# 後台自動備用管道：使用 Cobalt 無廣告 API 下載
async def download_via_cobalt(url: str, output_path: Path) -> bool:
    api_url = "https://api.cobalt.tools/api/json"
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    payload = {"url": url, "vCodec": "h264"}
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(api_url, json=payload, headers=headers) as resp:
                if resp.status != 200:
                    return False
                data = await resp.json()
                download_url = data.get("url")
                
                if not download_url:
                    return False

            # 下載影片檔
            async with session.get(download_url) as file_resp:
                if file_resp.status == 200:
                    with open(output_path, "wb") as f:
                        f.write(await file_resp.read())
                    return True
    except Exception as e:
        logger.error(f"Cobalt 下載失敗: {e}")
    return False

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 歡迎使用 YoinkBot！\n\n"
        "1. 直接傳送影片網址，我會自動幫你下載。\n"
        "2. 點擊下方按鈕可開啟無廣告內建下載介面。\n"
        "3. 在任何聊天室輸入 `@OopsYoinkBot 網址` 即可快速呼叫！",
        reply_markup=get_clean_keyboard()
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()
    if not text.startswith("http"):
        await update.message.reply_text(
            "請傳送有效的網址（以 http 或 https 開頭）。",
            reply_markup=get_clean_keyboard()
        )
        return

    status_msg = await update.message.reply_text("⏳ 解析與下載中，請稍候...")
    local_path = TMP_DIR / f"{update.message.message_id}_video.mp4"

    try:
        # 第一階段：嘗試用本地 yt-dlp 下載
        ydl_opts = {
            'outtmpl': str(local_path),
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'quiet': True,
            'no_warnings': True,
            'extractor_args': {'youtube': {'player_client': ['mweb', 'android', 'ios']}},
        }

        def run_ytdlp():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([text])

        loop = asyncio.get_running_loop()
        try:
            await loop.run_in_executor(None, run_ytdlp)
        except Exception:
            logger.info("yt-dlp 失敗，自動切換至 Cobalt 無廣告 API...")

        # 第二階段：若 yt-dlp 失敗，自動改用 Cobalt 無廣告 API 抓取
        if not local_path.exists():
            success = await download_via_cobalt(text, local_path)
            if not success:
                await status_msg.edit_text(
                    "❌ 影片解析失敗或檔案過大。點擊下方可開啟無廣告下載頁面：",
                    reply_markup=get_clean_keyboard()
                )
                return

        await status_msg.edit_text("📤 下載完成，正在傳送影片給您...")

        with open(local_path, "rb") as f:
            await update.message.reply_video(video=f, filename="video.mp4")

        await status_msg.edit_text("✅ 完成！")

    except Exception as e:
        logger.exception("處理影片時發生錯誤")
        await status_msg.edit_text(
            "❌ 傳送失敗。您可以點擊下方按鈕開啟無廣告下載介面：",
            reply_markup=get_clean_keyboard()
        )
    finally:
        if local_path and local_path.exists():
            try:
                local_path.unlink()
            except OSError:
                pass

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
            reply_markup=get_clean_keyboard()
        )
    ]
    await update.inline_query.answer(results, cache_time=1)

def main():
    if not TOKEN:
        raise RuntimeError("環境變數 TELEGRAM_BOT_TOKEN 未設定")

    threading.Thread(target=run_dummy_server, daemon=True).start()

    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(InlineQueryHandler(inline_query))

    logger.info("YoinkBot 已啟動...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
