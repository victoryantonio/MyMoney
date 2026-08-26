/**
 * MyMoney Telegram bot (Node/Telegraf) — thin client.
 *
 * Fase 0: scaffold webhook server (verifikasi secret + forward ke backend).
 * Fase 2: implementasi penuh (commands + NL parsing via backend REST).
 *
 * Pola v2 (ARCHITECTURE §3.2): bot TIDAK query Supabase / memanggil LLM
 * sendiri — semua logic di backend FastAPI. Bot menerima update dari
 * Telegram, meneruskannya ke `/api/telegram/webhook` backend dengan header
 * `X-Bot-Token` (BOT_SERVICE_TOKEN), lalu mengirim balasan yang dikembalikan
 * backend.
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

if (!BOT_TOKEN || !WEBHOOK_SECRET) {
  console.error("TELEGRAM_BOT_TOKEN / TELEGRAM_WEBHOOK_SECRET must be filled in the .env file");
  process.exit(1);
}

const bot = new Telegraf(BOT_TOKEN);

bot.command("start", (ctx) =>
  ctx.reply("MyMoney bot is active 🪙\nUse /help to see the list of commands."),
);
bot.command("help", (ctx) =>
  ctx.reply(
    "Commands: /start, /logout, /report, /undo, /edit — or send natural-language text (e.g., 'Beli kangkung 5k Cash').",
  ),
);

// Semua update lain diteruskan ke backend (Fase 2: parsing + reply)
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
    if (res.ok) {
      const data = (await res.json()) as { reply?: string };
      if (data.reply) await ctx.reply(data.reply);
    } else {
      console.error(`backend ${res.status}: ${await res.text()}`);
    }
  } catch (err) {
    console.error("Failed forward to backend:", err);
  }
});

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
