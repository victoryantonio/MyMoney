/**
 * MyMoney Telegram bot (Node/Telegraf) — thin proxy (Fase 2).
 *
 * Pola v2 (ARCHITECTURE §3.2): bot TIDAK memproses apa pun sendiri — semua
 * logic ada di backend FastAPI (telegram_service.py: /start, /logout, /undo,
 * /edit, /report, NL parsing, foto OCR). Bot hanya:
 *
 *   1. Menerima update dari Telegram via webhook (memverifikasi secret).
 *   2. Meneruskannya ke `${BACKEND_URL}/api/telegram/webhook` dengan header
 *      `X-Bot-Token` (BOT_SERVICE_TOKEN).
 *   3. Tidak membalas sendiri — backend yang membalas via Bot API
 *      (sendMessage), sehingga tidak terjadi double reply.
 *
 * Fallback: jika backend tidak merespons 200 (mati / rate limit), bot
 * mengirim satu pesan singkat agar user tidak dibiarkan diam.
 */

import http from "node:http";
import { Telegraf } from "telegraf";
import "dotenv/config";

const PORT = Number(process.env.PORT ?? 3000);
const BOT_TOKEN = process.env.TELEGRAM_BOT_TOKEN ?? "";
const WEBHOOK_SECRET = process.env.TELEGRAM_WEBHOOK_SECRET ?? "";
const BACKEND_URL = (process.env.APP_BASE_URL ?? "http://localhost:8000").replace(/\/$/, "");
const BOT_SERVICE_TOKEN = process.env.BOT_SERVICE_TOKEN ?? "";
const WEBHOOK_PATH = "/webhook";

if (!BOT_TOKEN || !WEBHOOK_SECRET || !BOT_SERVICE_TOKEN) {
  console.error(
    "TELEGRAM_BOT_TOKEN / TELEGRAM_WEBHOOK_SECRET / BOT_SERVICE_TOKEN must be set in the .env file",
  );
  process.exit(1);
}

const bot = new Telegraf(BOT_TOKEN);

// Semua update (termasuk /start, /help, teks natural-language, foto)
// diteruskan ke backend. Backend memproses dan membalas via Bot API —
// handler ini TIDAK mengirim balasan sendiri.
bot.on("message", async (ctx) => {
  try {
    const res = await fetch(`${BACKEND_URL}/api/telegram/webhook`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Bot-Token": BOT_SERVICE_TOKEN,
      },
      body: JSON.stringify(ctx.update),
    });
    if (!res.ok) {
      console.error(`backend ${res.status}: ${await res.text()}`);
      await ctx.reply("⚠️ Layanan sedang sibuk. Coba lagi sebentar lagi ya.");
    }
  } catch (err) {
    console.error("Failed to forward update to backend:", err);
    await ctx.reply("⚠️ Gagal terhubung ke layanan. Coba lagi sebentar lagi ya.").catch(() => {});
  }
});

// ── HTTP server: webhook endpoint (Telegraf) ─────────────────────────────────
// Telegram memanggil `${BOT_PUBLIC_URL}/webhook` dengan header
// `X-Telegram-Bot-Api-Secret-Token`; kita tolak selain itu.
const server = http.createServer((req, res) => {
  if (req.headers["x-telegram-bot-api-secret-token"] !== WEBHOOK_SECRET) {
    res.writeHead(403);
    res.end();
    return;
  }
  bot.webhookCallback(WEBHOOK_PATH)(req, res);
});

server.listen(PORT, () => {
  console.log(`MyMoney bot listening on :${PORT} (webhook ${WEBHOOK_PATH})`);
});
