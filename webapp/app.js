"use strict";

// Served same-origin from Flask, so the API and /files URLs are all relative.
const API = "/api";
const TOKEN_KEY = "eyewaz_token";

const $ = (sel) => document.querySelector(sel);
const live = $("#live");

/** Announce a message to screen-reader users (and show it visually). */
function announce(msg, kind = "") {
  live.textContent = "";
  // Re-set on next tick so repeated identical messages are still announced.
  setTimeout(() => (live.textContent = msg), 30);
  const status = $("#status");
  status.textContent = msg;
  status.className = "status" + (kind ? " " + kind : "");
  guide(msg);
}

/* ---------------------------- Voice guidance toggle ------------------------- */
const ttsToggle = $("#ttsToggle");
function renderToggle() {
  ttsToggle.textContent = guidanceOn ? "🔊 Voice: on" : "🔇 Voice: off";
  ttsToggle.setAttribute("aria-pressed", String(guidanceOn));
}
renderToggle();
ttsToggle.addEventListener("click", () => {
  guidanceOn = !guidanceOn;
  localStorage.setItem("eyewaz_guidance", guidanceOn ? "on" : "off");
  renderToggle();
  if (guidanceOn) TTS.speak("Voice guidance on", "en");
  else TTS.stop();
});

function getToken() { return localStorage.getItem(TOKEN_KEY); }
function setToken(t) { localStorage.setItem(TOKEN_KEY, t); }
function clearToken() { localStorage.removeItem(TOKEN_KEY); }

/* ------------------------- Browser text-to-speech --------------------------- */
// Uses the Web Speech API (speechSynthesis) so the app can read text aloud with
// the device's own voices — instant, offline, no server round-trip.
const TTS = (() => {
  const synth = window.speechSynthesis;
  let voices = [];
  const load = () => { voices = synth ? synth.getVoices() : []; };
  if (synth) { load(); synth.addEventListener("voiceschanged", load); }

  function pickVoice(langPrefix) {
    const p = langPrefix.toLowerCase();
    return voices.find((v) => v.lang.toLowerCase().replace("_", "-").startsWith(p)) || null;
  }
  function speak(text, langPrefix, { rate = 0.95, onend } = {}) {
    if (!synth || !text) return false;
    synth.cancel();
    const u = new SpeechSynthesisUtterance(text);
    const v = pickVoice(langPrefix);
    if (v) { u.voice = v; u.lang = v.lang; } else { u.lang = langPrefix; }
    u.rate = rate;
    if (onend) u.addEventListener("end", onend);
    synth.speak(u);
    return true;
  }
  return {
    speak,
    stop: () => synth && synth.cancel(),
    hasVoice: (p) => !!pickVoice(p),
    get supported() { return !!synth; },
  };
})();

// Voice guidance: speak prompts/status aloud (helps users without a screen reader).
let guidanceOn = localStorage.getItem("eyewaz_guidance") !== "off";
function guide(text) {
  if (guidanceOn && TTS.supported) TTS.speak(text, "en");
}

async function api(path, { method = "GET", body, auth = true, isForm = false } = {}) {
  const headers = {};
  if (auth && getToken()) headers["Authorization"] = "Bearer " + getToken();
  if (!isForm && body) headers["Content-Type"] = "application/json";
  const res = await fetch(API + path, {
    method,
    headers,
    body: isForm ? body : body ? JSON.stringify(body) : undefined,
  });
  let data = null;
  try { data = await res.json(); } catch (_) { /* non-JSON error page */ }
  if (!res.ok) {
    const msg = (data && (data.message || data.error)) || `Request failed (${res.status})`;
    throw new Error(msg);
  }
  return data;
}

/* ------------------------------ View switching ------------------------------ */

function showView(name) {
  $("#authView").hidden = name !== "auth";
  $("#captureView").hidden = name !== "capture";
  $("#logoutBtn").hidden = name !== "capture";
  const heading = name === "auth" ? "#authHeading" : "#captureHeading";
  $("#main").focus();
  $(heading).scrollIntoView({ block: "start" });
}

/* --------------------------------- Auth ------------------------------------- */

$("#showSignup").addEventListener("click", () => {
  $("#loginForm").hidden = true;
  $("#signupForm").hidden = false;
  $("#authHeading").textContent = "Create account";
  $("#suName").focus();
});
$("#showLogin").addEventListener("click", () => {
  $("#signupForm").hidden = true;
  $("#loginForm").hidden = false;
  $("#authHeading").textContent = "Sign in";
  $("#loginEmail").focus();
});

$("#loginForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  announce("Signing in…", "busy");
  try {
    const data = await api("/login", {
      method: "POST",
      auth: false,
      body: { email: $("#loginEmail").value.trim(), password: $("#loginPassword").value },
    });
    if (!data.token) throw new Error("Invalid email or password.");
    setToken(data.token);
    announce("Signed in.", "ok");
    enterApp();
  } catch (err) {
    announce(err.message || "Could not sign in.", "error");
  }
});

$("#signupForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  if ($("#suPassword").value !== $("#suConfirm").value) {
    return announce("Passwords do not match.", "error");
  }
  announce("Creating your account…", "busy");
  try {
    await api("/signup", {
      method: "POST",
      auth: false,
      body: {
        name: $("#suName").value.trim(),
        email: $("#suEmail").value.trim(),
        phone: $("#suPhone").value.trim(),
        password: $("#suPassword").value,
        confirmPassword: $("#suConfirm").value,
      },
    });
    announce("Account created. Signing you in…", "ok");
    // Auto-login for a smooth first run.
    const data = await api("/login", {
      method: "POST", auth: false,
      body: { email: $("#suEmail").value.trim(), password: $("#suPassword").value },
    });
    setToken(data.token);
    enterApp();
  } catch (err) {
    announce(err.message || "Could not create account.", "error");
  }
});

$("#logoutBtn").addEventListener("click", () => {
  clearToken();
  showView("auth");
  announce("Logged out.");
});

/* ------------------------------- Capture flow ------------------------------- */

let selectedFile = null;

$("#photoInput").addEventListener("change", (e) => {
  const file = e.target.files && e.target.files[0];
  if (!file) return;
  selectedFile = file;
  const url = URL.createObjectURL(file);
  $("#preview").src = url;
  $("#previewWrap").hidden = false;
  $("#result").hidden = true;
  announce("Photo selected. Press “Read it to me”.", "ok");
  $("#readBtn").focus();
});

function chosenVoice() {
  const r = document.querySelector('input[name="voice"]:checked');
  return r ? r.value : "female";
}

$("#readBtn").addEventListener("click", async () => {
  if (!selectedFile) return announce("Please choose a photo first.", "error");
  const btn = $("#readBtn");
  btn.disabled = true;
  announce("Reading your photo. Extracting text, translating to Urdu, and creating audio… this can take a few seconds.", "busy");
  try {
    const form = new FormData();
    form.append("file", selectedFile);
    const doc = await api("/document-translation-and-speech", { method: "POST", isForm: true, body: form });
    renderResult(doc);
    loadLibrary();
  } catch (err) {
    announce(err.message || "Something went wrong while reading the photo.", "error");
  } finally {
    btn.disabled = false;
  }
});

function audioUrlFor(doc, voice) {
  return voice === "male" ? doc.male_audio_url : doc.female_audio_url;
}

let currentDoc = null;

function renderResult(doc) {
  currentDoc = doc;
  const voice = chosenVoice();
  $("#urduText").textContent = doc.trans_text || "(no text found)";
  $("#engText").textContent = doc.eng_text || "(no English text detected)";
  const player = $("#player");
  player.src = audioUrlFor(doc, voice) || "";

  // Hint if the device has no Urdu voice for the browser-TTS buttons.
  const hint = $("#ttsHint");
  if (TTS.supported && !TTS.hasVoice("ur")) {
    hint.textContent = "Tip: no Urdu device voice is installed, so “Speak Urdu” may sound off — the natural Urdu audio above is best. English uses your device voice.";
    hint.hidden = false;
  } else {
    hint.hidden = true;
  }

  $("#result").hidden = false;
  $("#resultHeading").setAttribute("tabindex", "-1");
  $("#resultHeading").focus();
  announce("Done. Here is the Urdu reading.", "ok");
  // Try to autoplay the natural Urdu audio; browsers may block without a gesture.
  player.play().catch(() => {
    announce("Ready. Press play to listen.", "ok");
    $("#replayBtn").focus();
  });
}

$("#replayBtn").addEventListener("click", () => {
  const p = $("#player");
  p.currentTime = 0;
  p.play();
});

/* ----------------------- Browser-TTS "Speak" buttons ------------------------ */
function speakWith(btn, text, langPrefix) {
  if (!TTS.supported) return announce("Your browser does not support speech.", "error");
  if (!text) return;
  TTS.stop();
  document.querySelectorAll(".primary-btn.speaking").forEach((b) => b.classList.remove("speaking"));
  btn.classList.add("speaking");
  TTS.speak(text, langPrefix, { onend: () => btn.classList.remove("speaking") });
}
$("#speakUrduBtn").addEventListener("click", (e) =>
  speakWith(e.currentTarget, currentDoc && currentDoc.trans_text, "ur"));
$("#speakEngBtn").addEventListener("click", (e) =>
  speakWith(e.currentTarget, currentDoc && currentDoc.eng_text, "en"));
$("#stopSpeakBtn").addEventListener("click", () => {
  TTS.stop();
  document.querySelectorAll(".primary-btn.speaking").forEach((b) => b.classList.remove("speaking"));
});

/* -------------------------------- Library ----------------------------------- */

async function loadLibrary() {
  try {
    const data = await api("/document-translation-and-speech", { method: "GET" });
    const files = (data && data.myFiles) || [];
    const ul = $("#library");
    ul.innerHTML = "";
    if (!files.length) {
      ul.innerHTML = '<li class="lede">Nothing yet — read your first photo above.</li>';
      return;
    }
    // Newest first.
    files.reverse().forEach((doc) => {
      const li = document.createElement("li");
      const btn = document.createElement("button");
      btn.className = "lib-item";
      btn.type = "button";
      const ur = (doc.trans_text || doc.doc_name || "Document").slice(0, 60);
      btn.innerHTML = `<span class="lib-ur" lang="ur" dir="rtl">${escapeHtml(ur)}</span><span class="lib-play" aria-hidden="true">▶</span>`;
      btn.setAttribute("aria-label", "Play: " + ur);
      btn.addEventListener("click", () => renderResult(doc));
      li.appendChild(btn);
      ul.appendChild(li);
    });
  } catch (_) { /* library is best-effort */ }
}

function escapeHtml(s) {
  return s.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

/* --------------------------------- Boot ------------------------------------- */

function enterApp() {
  showView("capture");
  loadLibrary();
}

if (getToken()) {
  enterApp();
} else {
  showView("auth");
}
