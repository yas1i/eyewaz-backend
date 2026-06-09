/* EYEWAZ Read Aloud — background service worker (MV3).
   Turns selected web-page text into Urdu speech via the EYEWAZ TTS service.
   The service worker can't play audio itself, so it fetches the WAV and hands a
   data: URL to an offscreen document that owns an <audio> element. */

const DEFAULTS = {
  ttsUrl: "http://167.233.35.30:8090",   // your self-hosted EYEWAZ TTS service
  apiKey: "",                             // X-API-Key for that service (optional)
  speed: 1.0,                             // 0.5–2.0
  maxChars: 4000,                         // safety cap per request
};

async function settings() {
  const s = await chrome.storage.sync.get(DEFAULTS);
  return { ...DEFAULTS, ...s };
}

/* ---- Context menu ---- */
chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: "eyewaz-read",
    title: "Read with EYEWAZ (Urdu)",
    contexts: ["selection"],
  });
});

chrome.contextMenus.onClicked.addListener((info) => {
  if (info.menuItemId === "eyewaz-read" && info.selectionText) {
    speak(info.selectionText);
  }
});

/* ---- Keyboard commands ---- */
chrome.commands.onCommand.addListener(async (command) => {
  if (command === "stop-speech") return stop();
  if (command === "read-selection") {
    const text = await getActiveSelection();
    if (text) speak(text);
    else notify("Select some text first, then press the shortcut.");
  }
});

/* ---- Messages from popup ---- */
chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (msg.type === "EYEWAZ_SPEAK_ACTIVE") {
    getActiveSelection().then((t) => {
      if (t) { speak(t); sendResponse({ ok: true }); }
      else sendResponse({ ok: false, error: "No text selected on the page." });
    });
    return true; // async
  }
  if (msg.type === "EYEWAZ_SPEAK_TEXT") { speak(msg.text); sendResponse({ ok: true }); return; }
  if (msg.type === "EYEWAZ_STOP") { stop(); sendResponse({ ok: true }); return; }
});

/* ---- Read the selection from the focused tab ---- */
async function getActiveSelection() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab || !tab.id) return "";
  try {
    const [res] = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: () => (window.getSelection ? window.getSelection().toString() : ""),
    });
    return (res && res.result || "").trim();
  } catch (_) {
    return "";
  }
}

/* ---- Synthesize + play ---- */
async function speak(text) {
  const cfg = await settings();
  text = (text || "").trim().slice(0, cfg.maxChars);
  if (!text) return;
  try {
    const headers = { "Content-Type": "application/json" };
    if (cfg.apiKey) headers["X-API-Key"] = cfg.apiKey;
    const url = cfg.ttsUrl.replace(/\/+$/, "") + "/tts";
    const r = await fetch(url, {
      method: "POST",
      headers,
      body: JSON.stringify({ text, speed: Number(cfg.speed) || 1.0 }),
    });
    if (!r.ok) {
      notify(`EYEWAZ voice error (${r.status}). Check the service URL/key in the popup.`);
      return;
    }
    const buf = await r.arrayBuffer();
    const dataUrl = "data:audio/wav;base64," + bytesToBase64(new Uint8Array(buf));
    await ensureOffscreen();
    chrome.runtime.sendMessage({ target: "offscreen", type: "PLAY", dataUrl });
  } catch (e) {
    notify("Could not reach the EYEWAZ voice service. Is it running and reachable?");
  }
}

async function stop() {
  await ensureOffscreen();
  chrome.runtime.sendMessage({ target: "offscreen", type: "STOP" });
}

/* ---- Offscreen audio document ---- */
let creating = null;
async function ensureOffscreen() {
  const exists = await chrome.offscreen.hasDocument();
  if (exists) return;
  if (!creating) {
    creating = chrome.offscreen.createDocument({
      url: "offscreen.html",
      reasons: ["AUDIO_PLAYBACK"],
      justification: "Play synthesized Urdu speech for the selected text.",
    });
  }
  await creating;
  creating = null;
}

/* ---- Helpers ---- */
function bytesToBase64(bytes) {
  let bin = "";
  const chunk = 0x8000;
  for (let i = 0; i < bytes.length; i += chunk) {
    bin += String.fromCharCode.apply(null, bytes.subarray(i, i + chunk));
  }
  return btoa(bin);
}

function notify(message) {
  try {
    chrome.notifications && chrome.notifications.create({
      type: "basic", iconUrl: "icons/icon-48.png", title: "EYEWAZ Read Aloud", message,
    });
  } catch (_) { /* notifications permission optional */ }
  console.warn("[EYEWAZ]", message);
}
