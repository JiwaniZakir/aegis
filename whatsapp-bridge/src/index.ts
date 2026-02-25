/**
 * Aegis WhatsApp Bridge — whatsapp-web.js sidecar.
 *
 * Connects to WhatsApp Web via Puppeteer, exposes a REST API for
 * sending/receiving messages, and forwards incoming messages to the
 * Aegis API for processing.
 */

import express from "express";
import { Client, LocalAuth } from "whatsapp-web.js";
import qrcode from "qrcode-terminal";

const PORT = Number(process.env.PORT ?? 3001);
const API_URL = process.env.API_URL ?? "http://api:8000";
const API_TOKEN = process.env.API_TOKEN ?? "";

const app = express();
app.use(express.json());

// --------------------------------------------------------------------------
// WhatsApp client
// --------------------------------------------------------------------------

let clientReady = false;
let qrCode: string | null = null;

const client = new Client({
  authStrategy: new LocalAuth({ dataPath: "/app/.wwebjs_auth" }),
  puppeteer: {
    headless: true,
    args: [
      "--no-sandbox",
      "--disable-setuid-sandbox",
      "--disable-dev-shm-usage",
      "--disable-gpu",
    ],
    executablePath: process.env.PUPPETEER_EXECUTABLE_PATH ?? undefined,
  },
});

client.on("qr", (qr: string) => {
  qrCode = qr;
  console.log("[WhatsApp] Scan QR code to authenticate:");
  qrcode.generate(qr, { small: true });
});

client.on("ready", () => {
  clientReady = true;
  qrCode = null;
  console.log("[WhatsApp] Client is ready.");
});

client.on("disconnected", (reason: string) => {
  clientReady = false;
  console.log(`[WhatsApp] Disconnected: ${reason}`);
});

client.on("message", async (msg) => {
  if (!API_TOKEN) return;

  try {
    const body = {
      from: msg.from,
      body: msg.body,
      timestamp: msg.timestamp,
      type: msg.type,
    };

    await fetch(`${API_URL}/api/v1/whatsapp/incoming`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${API_TOKEN}`,
      },
      body: JSON.stringify(body),
    });
  } catch (err) {
    console.error("[WhatsApp] Failed to forward message:", err);
  }
});

// --------------------------------------------------------------------------
// REST API
// --------------------------------------------------------------------------

app.get("/status", (_req, res) => {
  res.json({
    ready: clientReady,
    qr_pending: qrCode !== null,
  });
});

app.get("/qr", (_req, res) => {
  if (clientReady) {
    res.json({ status: "authenticated" });
  } else if (qrCode) {
    res.json({ status: "pending", qr: qrCode });
  } else {
    res.json({ status: "initializing" });
  }
});

app.post("/send", async (req, res) => {
  if (!clientReady) {
    res.status(503).json({ error: "WhatsApp client not ready" });
    return;
  }

  const { to, message } = req.body;
  if (!to || !message) {
    res.status(400).json({ error: "Missing 'to' or 'message' field" });
    return;
  }

  try {
    const chatId = to.includes("@") ? to : `${to}@c.us`;
    await client.sendMessage(chatId, message);
    res.json({ success: true, to: chatId });
  } catch (err) {
    console.error("[WhatsApp] Send failed:", err);
    res.status(500).json({ error: "Failed to send message" });
  }
});

// --------------------------------------------------------------------------
// Start
// --------------------------------------------------------------------------

app.listen(PORT, "0.0.0.0", () => {
  console.log(`[WhatsApp Bridge] Listening on port ${PORT}`);
  client.initialize().catch((err: Error) => {
    console.error("[WhatsApp] Failed to initialize:", err.message);
  });
});
