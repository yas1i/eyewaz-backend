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
  // Split long text into <=220-char chunks on sentence boundaries. This avoids
  // the well-known browser bug where long utterances cut off after ~15s.
  function chunk(text) {
    const sentences = text.replace(/\s+/g, " ").match(/[^.!?]+[.!?]+|\S[^.!?]*$/g) || [text];
    const out = [];
    let cur = "";
    for (const s of sentences) {
      if ((cur + s).length > 220) { if (cur.trim()) out.push(cur.trim()); cur = s; }
      else cur += s;
    }
    if (cur.trim()) out.push(cur.trim());
    return out;
  }

  // Speak long text chunk-by-chunk. onChunk(index) fires as each chunk starts.
  function speakLong(text, langPrefix, { rate = 0.95, onChunk, onend } = {}) {
    if (!synth || !text) return [];
    synth.cancel();
    const v = pickVoice(langPrefix);
    const chunks = chunk(text);
    let i = 0;
    const next = () => {
      if (i >= chunks.length) { onend && onend(); return; }
      const idx = i++;
      const u = new SpeechSynthesisUtterance(chunks[idx]);
      if (v) { u.voice = v; u.lang = v.lang; } else { u.lang = langPrefix; }
      u.rate = rate;
      if (onChunk) u.addEventListener("start", () => onChunk(idx));
      u.addEventListener("end", next);
      u.addEventListener("error", next);
      synth.speak(u);
    };
    next();
    return chunks;
  }

  return {
    speak,
    speakLong,
    chunk,
    stop: () => synth && synth.cancel(),
    pause: () => synth && synth.pause(),
    resume: () => synth && synth.resume(),
    hasVoice: (p) => !!pickVoice(p),
    get supported() { return !!synth; },
  };
})();

// Voice guidance: speak prompts/status aloud (helps users without a screen reader).
let guidanceOn = localStorage.getItem("eyewaz_guidance") !== "off";
function guide(text) {
  if (guidanceOn && TTS.supported) TTS.speak(text, "en");
}

/* ---------------------------- Voice guidance toggle ------------------------- */
const ttsToggle = $("#ttsToggle");
function renderToggle() {
  if (!ttsToggle) return;
  const use = ttsToggle.querySelector("use");
  if (use) use.setAttribute("href", guidanceOn ? "#ic-voice-on" : "#ic-voice-off");
  ttsToggle.classList.toggle("is-off", !guidanceOn);
  ttsToggle.setAttribute("aria-pressed", String(guidanceOn));
  const label = guidanceOn ? "Voice guidance on" : "Voice guidance off";
  ttsToggle.setAttribute("aria-label", label);
  ttsToggle.title = label;
}
if (ttsToggle) {
  renderToggle();
  ttsToggle.addEventListener("click", () => {
    guidanceOn = !guidanceOn;
    localStorage.setItem("eyewaz_guidance", guidanceOn ? "on" : "off");
    renderToggle();
    if (guidanceOn) TTS.speak("Voice guidance on", "en");
    else TTS.stop();
  });
}

/* When voice guidance is on, read out icon controls as they get focus, so a
   blind user knows what each icon is. */
document.addEventListener("focusin", (e) => {
  if (!guidanceOn) return;
  const btn = e.target.closest && e.target.closest(".tab, .icon-btn, .bb-btn");
  if (!btn) return;
  const name = btn.getAttribute("aria-label") || (btn.textContent || "").trim();
  if (name) guide(name);
});

/* Bottom navigation bar */
const bottomBar = $("#bottomBar");
if (bottomBar) {
  bottomBar.addEventListener("click", (e) => {
    const btn = e.target.closest(".bb-btn"); if (!btn) return;
    const nav = btn.dataset.nav;
    document.querySelectorAll(".bb-btn").forEach((b) => b.classList.toggle("is-on", b === btn));
    if (nav === "profile") { openAccount(); return; }
    showView("capture");
    if (nav === "favourites") { activeFolder = "★ Favourites"; showTab("booksPanel"); }
    else if (nav === "add") { showTab("photoPanel"); announce("Add. Take a photo, or pick another reading mode at the top.", "ok"); }
    else { showTab("booksPanel"); if (nav === "folders") announce("Folders", "ok"); }
  });
}

async function api(path, { method = "GET", body, auth = true, isForm = false } = {}) {
  const headers = {};
  if (auth && getToken()) headers["Authorization"] = "Bearer " + getToken();
  if (!isForm && body) headers["Content-Type"] = "application/json";
  // Gentle hint if the (free) server is cold-starting.
  const slow = setTimeout(() => {
    const st = $("#status");
    if (st && st.classList.contains("busy") && !st.dataset.waking) {
      st.dataset.waking = "1";
      st.textContent += " — the server may be waking up (up to a minute)…";
    }
  }, 7000);
  let res;
  try {
    res = await fetch(API + path, {
      method,
      headers,
      body: isForm ? body : body ? JSON.stringify(body) : undefined,
    });
  } finally {
    clearTimeout(slow);
    const st = $("#status"); if (st) delete st.dataset.waking;
  }
  let data = null;
  try { data = await res.json(); } catch (_) { /* non-JSON error page */ }
  if (!res.ok) {
    const msg = (data && (data.message || data.error)) || `Request failed (${res.status})`;
    if (res.status === 402 && data && data.quota_exceeded) {
      try { Billing.onQuota(data); } catch (_) {}
    }
    const err = new Error(msg); err.status = res.status; err.data = data;
    throw err;
  }
  return data;
}

/* ------------------------------ View switching ------------------------------ */

function showView(name) {
  const loggedIn = name === "capture" || name === "account";
  $("#authView").hidden = name !== "auth";
  $("#captureView").hidden = name !== "capture";
  $("#accountView").hidden = name !== "account";
  $("#logoutBtn").hidden = !loggedIn;
  $("#accountBtn").hidden = !loggedIn;
  const bb = $("#bottomBar"); if (bb) bb.hidden = !loggedIn;   // bottom nav only when signed in
  const headingMap = { auth: "#authHeading", capture: "#captureHeading", account: "#accountHeading" };
  $("#main").focus();
  const h = $(headingMap[name]);
  if (h) h.scrollIntoView({ block: "start" });
}

/* --------------------------------- Auth ------------------------------------- */

let pendingEmail = null;
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

// Accessible error handling: shows a persistent message AND announces it.
function showAuthError(msg, focusSel) {
  const el = $("#authError");
  el.textContent = msg;
  el.hidden = false;
  announce(msg, "error");
  if (focusSel) { const f = $(focusSel); if (f) { f.setAttribute("aria-invalid", "true"); f.focus(); } }
  return false;
}
function clearAuthError(...sels) {
  $("#authError").hidden = true;
  $("#authError").textContent = "";
  sels.forEach((s) => $(s)?.removeAttribute("aria-invalid"));
}

// Show one auth card: 'login' | 'signup' | 'otp' | 'forgot' | 'reset'.
function showAuthForm(name) {
  clearAuthError();
  $("#loginForm").hidden = name !== "login";
  $("#signupForm").hidden = name !== "signup";
  $("#otpForm").hidden = name !== "otp";
  $("#forgotForm").hidden = name !== "forgot";
  $("#resetForm").hidden = name !== "reset";
  // Social buttons only make sense on the initial login/signup steps.
  $("#socialBlock").hidden = !(name === "login" || name === "signup");
  const headings = {
    login: "Welcome back", signup: "Create your account",
    otp: "Verify your email", forgot: "Reset your password", reset: "Reset your password",
  };
  const ledes = {
    login: "Sign in to turn text into spoken Urdu.",
    signup: "Create an account to get started.",
    otp: "", forgot: "", reset: "",
  };
  $("#authHeading").textContent = headings[name];
  if (ledes[name]) { $("#authLede").textContent = ledes[name]; $("#authLede").hidden = false; }
  else $("#authLede").hidden = true;
}

$("#showSignup").addEventListener("click", () => { showAuthForm("signup"); $("#suName").focus(); });
$("#showLogin").addEventListener("click", () => { showAuthForm("login"); $("#loginEmail").focus(); });
$("#backToLogin").addEventListener("click", () => { showAuthForm("login"); $("#loginEmail").focus(); });
$("#showForgot").addEventListener("click", () => { showAuthForm("forgot"); $("#forgotEmail").focus(); });
$("#forgotBackToLogin").addEventListener("click", () => { showAuthForm("login"); $("#loginEmail").focus(); });

// Password show/hide toggles (delegated; works for every .pw-toggle).
document.addEventListener("click", (e) => {
  const t = e.target.closest(".pw-toggle");
  if (!t) return;
  const input = document.getElementById(t.dataset.target);
  if (!input) return;
  const show = input.type === "password";
  input.type = show ? "text" : "password";
  t.textContent = show ? "Hide" : "Show";
  t.setAttribute("aria-pressed", String(show));
  t.setAttribute("aria-label", show ? "Hide password" : "Show password");
});

// Social sign-in: full-page redirect into the provider's OAuth flow.
document.querySelectorAll(".social-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    window.location.href = "/api/auth/" + btn.dataset.provider + "/start";
  });
});

// Forgot password: request a reset code.
$("#forgotForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  clearAuthError("#forgotEmail");
  if (!EMAIL_RE.test($("#forgotEmail").value.trim()))
    return showAuthError("Please enter a valid email address.", "#forgotEmail");
  announce("Sending a reset code…", "busy");
  try {
    const data = await api("/forgot-password", {
      method: "POST", auth: false, body: { email: $("#forgotEmail").value.trim() },
    });
    pendingEmail = $("#forgotEmail").value.trim();
    showAuthForm("reset");
    if (data.dev_code) {
      $("#resetDevCode").textContent = "Your code is " + data.dev_code;
      $("#resetDevCode").hidden = false;
      $("#resetCode").value = data.dev_code;
    } else {
      $("#resetDevCode").hidden = true;
    }
    $("#resetCode").focus();
    announce(data.message || "If that email has an account, we sent a code.", "ok");
  } catch (err) {
    showAuthError(err.message || "Could not send a reset code.");
  }
});

// Reset password: verify code + set new password (then logged in).
$("#resetForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  clearAuthError("#resetCode", "#resetPassword");
  if (!/^[0-9]{6}$/.test($("#resetCode").value.trim()))
    return showAuthError("Enter the 6-digit reset code.", "#resetCode");
  if ($("#resetPassword").value.length < 8)
    return showAuthError("Your new password must be at least 8 characters.", "#resetPassword");
  announce("Updating your password…", "busy");
  try {
    const data = await api("/reset-password", {
      method: "POST", auth: false,
      body: { email: pendingEmail, code: $("#resetCode").value.trim(), newPassword: $("#resetPassword").value },
    });
    if (!data.token) throw new Error("Could not reset password.");
    setToken(data.token);
    announce("Password updated. Welcome!", "ok");
    enterApp();
  } catch (err) {
    showAuthError(err.message || "Could not reset your password.", "#resetCode");
  }
});

// After password/signup succeeds, the server emails a code — move to the OTP step.
function goToOtp(email, data) {
  pendingEmail = email;
  $("#otpInstructions").textContent =
    (data.message || "We emailed you a 6-digit code.") + " Enter it below to continue.";
  const banner = $("#devCodeBanner");
  if (data.dev_code) {
    banner.textContent = "Your code is " + data.dev_code;
    banner.hidden = false;
    $("#otpCode").value = data.dev_code;   // prefill so it works without email
  } else {
    banner.hidden = true;
    $("#otpCode").value = "";
  }
  showAuthForm("otp");
  $("#otpCode").focus();
  const spoken = data.dev_code
    ? "Email is not set up. Your code is " + data.dev_code.split("").join(" ") + ". Press verify."
    : "We emailed you a verification code.";
  announce(spoken, "ok");
}

$("#loginForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  clearAuthError("#loginEmail", "#loginPassword");
  if (!EMAIL_RE.test($("#loginEmail").value.trim()))
    return showAuthError("Please enter a valid email address.", "#loginEmail");
  if (!$("#loginPassword").value)
    return showAuthError("Please enter your password.", "#loginPassword");
  announce("Checking your details…", "busy");
  try {
    const data = await api("/login", {
      method: "POST", auth: false,
      body: { email: $("#loginEmail").value.trim(), password: $("#loginPassword").value },
    });
    goToOtp($("#loginEmail").value.trim(), data);
  } catch (err) {
    showAuthError(err.message === "Invalid credentials"
      ? "That email or password is incorrect." : (err.message || "Could not sign in."));
  }
});

$("#signupForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  clearAuthError("#suName", "#suEmail", "#suPassword", "#suConfirm");
  if (!$("#suName").value.trim())
    return showAuthError("Please enter your name.", "#suName");
  if (!EMAIL_RE.test($("#suEmail").value.trim()))
    return showAuthError("Please enter a valid email address.", "#suEmail");
  if ($("#suPassword").value.length < 8)
    return showAuthError("Your password must be at least 8 characters.", "#suPassword");
  if ($("#suPassword").value !== $("#suConfirm").value)
    return showAuthError("The two passwords do not match.", "#suConfirm");
  announce("Creating your account…", "busy");
  try {
    const data = await api("/signup", {
      method: "POST", auth: false,
      body: {
        name: $("#suName").value.trim(),
        email: $("#suEmail").value.trim(),
        phone: $("#suPhone").value.trim(),
        password: $("#suPassword").value,
        confirmPassword: $("#suConfirm").value,
      },
    });
    goToOtp($("#suEmail").value.trim(), data);
  } catch (err) {
    if ((err.message || "").includes("already exists")) {
      showAuthError("An account with this email already exists. Please sign in instead.", "#suEmail");
      showAuthForm("login");
      $("#loginEmail").value = $("#suEmail").value.trim();
      showAuthError("This email already has an account — please sign in.");
    } else {
      showAuthError(err.message || "Could not create account.");
    }
  }
});

$("#otpForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  clearAuthError("#otpCode");
  const code = $("#otpCode").value.trim();
  if (!/^[0-9]{6}$/.test(code))
    return showAuthError("Enter the 6-digit code.", "#otpCode");
  announce("Verifying your code…", "busy");
  try {
    const data = await api("/verify-otp", {
      method: "POST", auth: false,
      body: { email: pendingEmail, code },
    });
    if (!data.token) throw new Error("Verification failed.");
    setToken(data.token);
    announce("Verified. Welcome!", "ok");
    enterApp();
  } catch (err) {
    showAuthError(err.message || "Could not verify the code.", "#otpCode");
  }
});

$("#resendOtp").addEventListener("click", async () => {
  if (!pendingEmail) return;
  announce("Sending a new code…", "busy");
  try {
    const data = await api("/resend-otp", { method: "POST", auth: false, body: { email: pendingEmail } });
    if (data.dev_code) {
      $("#devCodeBanner").textContent = "Your code is " + data.dev_code;
      $("#devCodeBanner").hidden = false;
      $("#otpCode").value = data.dev_code;
      announce("Your new code is " + data.dev_code.split("").join(" "), "ok");
    } else {
      announce(data.message || "A new code is on its way.", "ok");
    }
  } catch (err) {
    showAuthError(err.message || "Could not resend the code.");
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

const RTL_LANGS = ["ar", "ur", "fa", "he", "ps", "sd", "ug", "yi", "dv"];
function isRTL(lang) { return RTL_LANGS.includes((lang || "").slice(0, 2)); }
function applyLangDir(el, lang) {
  el.lang = (lang || "").slice(0, 2) || "en";
  el.dir = isRTL(lang) ? "rtl" : "ltr";
}

function renderResult(doc) {
  currentDoc = doc;
  const t = $("#urduText");
  t.textContent = doc.trans_text || "(no text found)";
  applyLangDir(t, doc.trans_lang);
  $("#engText").textContent = doc.eng_text || "(no text detected)";
  const player = $("#player");
  player.src = (doc.female_audio_url || doc.male_audio_url) || "";

  // Hint if the device has no voice for the result's language.
  const hint = $("#ttsHint");
  if (TTS.supported && !TTS.hasVoice(doc.trans_lang)) {
    hint.textContent = "Tip: your device may not have a voice for this language, so “Speak” can sound off — the natural audio above is best.";
    hint.hidden = false;
  } else {
    hint.hidden = true;
  }

  $("#result").hidden = false;
  $("#resultHeading").setAttribute("tabindex", "-1");
  $("#resultHeading").focus();
  announce("Done. Here is your reading.", "ok");
  // Try to autoplay the natural audio; browsers may block without a gesture.
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
$("#speakUrduBtn")?.addEventListener("click", (e) =>
  speakWith(e.currentTarget, currentDoc && currentDoc.trans_text, (currentDoc && currentDoc.trans_lang) || "ur"));
$("#speakEngBtn")?.addEventListener("click", (e) =>
  speakWith(e.currentTarget, currentDoc && currentDoc.eng_text, (currentDoc && currentDoc.lang) || "en"));
$("#stopSpeakBtn")?.addEventListener("click", () => {
  TTS.stop();
  document.querySelectorAll(".primary-btn.speaking").forEach((b) => b.classList.remove("speaking"));
});

/* ---------------------------- Read a web page ------------------------------- */
let pagePaused = false;

$("#urlForm")?.addEventListener("submit", async (e) => {
  e.preventDefault();
  const url = $("#urlInput").value.trim();
  if (!url) return;
  announce("Opening the page…", "busy");
  try {
    const data = await api("/read-url", { method: "POST", body: { url } });
    showPage(data);
  } catch (err) {
    announce(err.message || "Could not read that page.", "error");
  }
});

function clearPageHighlight() {
  document.querySelectorAll("#pageText .speaking-chunk").forEach((s) => s.classList.remove("speaking-chunk"));
}

function showPage(data) {
  $("#pageResultHeading").textContent = data.title || "Page";
  const container = $("#pageText");
  container.innerHTML = "";
  // Render each speakable chunk as its own span so the current one can be lit up.
  TTS.chunk(data.text).forEach((c, i) => {
    const span = document.createElement("span");
    span.id = "chunk-" + i;
    span.textContent = c + " ";
    container.appendChild(span);
  });
  $("#pageResult").hidden = false;
  $("#pageResultHeading").focus();
  startPageReading();
}

function startPageReading() {
  if (!TTS.supported) return announce("Your browser does not support speech.", "error");
  pagePaused = false;
  announce("Reading the page aloud.", "ok");
  TTS.speakLong($("#pageText").textContent, "en", {
    rate: userPrefs.rate,
    onChunk: (i) => {
      clearPageHighlight();
      const el = document.getElementById("chunk-" + i);
      if (el) { el.classList.add("speaking-chunk"); el.scrollIntoView({ block: "nearest" }); }
    },
    onend: () => { clearPageHighlight(); announce("Finished reading the page.", "ok"); },
  });
}

$("#pagePlayBtn")?.addEventListener("click", () => {
  if (pagePaused) { TTS.resume(); pagePaused = false; }
  else startPageReading();
});
$("#pagePauseBtn")?.addEventListener("click", () => { TTS.pause(); pagePaused = true; });
$("#pageStopBtn")?.addEventListener("click", () => { TTS.stop(); pagePaused = false; clearPageHighlight(); });

$("#pageUrduBtn")?.addEventListener("click", async (e) => {
  const text = $("#pageText").textContent.trim();
  if (!text) return;
  const btn = e.currentTarget;
  btn.disabled = true;
  announce("Translating the page… this can take a moment.", "busy");
  try {
    const data = await api("/translate", { method: "POST", body: { text, to: userPrefs.language } });
    const translated = data.translated || "";
    const out = $("#pageUrduText");
    out.textContent = translated;
    applyLangDir(out, userPrefs.language);
    $("#pageUrduWrap").hidden = false;
    $("#pageUrduWrap").scrollIntoView({ block: "nearest" });

    // Synthesize with the user's chosen Azure voice (browsers rarely have these).
    announce("Creating the audio… this can take a few seconds.", "busy");
    const speech = await api("/speak", { method: "POST", body: { text: translated, voiceName: userPrefs.voice, rate: userPrefs.rate } });
    const player = $("#pageUrduAudio");
    player.src = speech.audio_url;
    const note = speech.truncated ? " (reading the first part of a long page)" : "";
    announce("Playing the page in Urdu" + note + ".", "ok");
    player.play().catch(() => announce("Urdu audio ready — press play to listen.", "ok"));
  } catch (err) {
    announce(err.message || "Could not translate or read the page.", "error");
  } finally {
    btn.disabled = false;
  }
});

/* ------------------- My Books: on-device recordings + folders --------------- */

// IndexedDB store for audio blobs (so recordings replay offline, no server).
function idbOpen() {
  return new Promise((res, rej) => {
    const r = indexedDB.open("eyewaz", 1);
    r.onupgradeneeded = () => {
      if (!r.result.objectStoreNames.contains("recordings"))
        r.result.createObjectStore("recordings", { keyPath: "id" });
    };
    r.onsuccess = () => res(r.result);
    r.onerror = () => rej(r.error);
  });
}
async function recPut(rec) {
  const db = await idbOpen();
  return new Promise((res, rej) => {
    const t = db.transaction("recordings", "readwrite");
    t.objectStore("recordings").put(rec);
    t.oncomplete = res; t.onerror = () => rej(t.error);
  });
}
async function recAll() {
  const db = await idbOpen();
  return new Promise((res, rej) => {
    const q = db.transaction("recordings").objectStore("recordings").getAll();
    q.onsuccess = () => res(q.result || []); q.onerror = () => rej(q.error);
  });
}
async function recDel(id) {
  const db = await idbOpen();
  return new Promise((res, rej) => {
    const t = db.transaction("recordings", "readwrite");
    t.objectStore("recordings").delete(id);
    t.oncomplete = res; t.onerror = () => rej(t.error);
  });
}

function getFolders() { try { return JSON.parse(localStorage.getItem("eyewaz_folders") || "[]"); } catch (_) { return []; } }
function setFolders(list) { localStorage.setItem("eyewaz_folders", JSON.stringify(list)); }
let activeFolder = "All";

// Fetch the audio and store it on the device, in the active folder.
async function saveRecording(audioUrl, title, lang) {
  if (!audioUrl) throw new Error("Nothing to save yet.");
  const limit = Billing.recordingsLimit();
  const existing = await recAll().catch(() => []);
  if (existing.length >= limit) {
    throw new Error(`Your plan saves up to ${limit} recordings. Upgrade to keep more.`);
  }
  const blob = await (await fetch(audioUrl)).blob();
  const folder = activeFolder === "All" ? "Unfiled" : activeFolder;
  await recPut({
    id: "rec_" + Date.now() + "_" + Math.random().toString(36).slice(2, 7),
    title: (title || "Recording").trim().slice(0, 80) || "Recording",
    lang: lang || "", folder, createdAt: Date.now(), blob,
  });
}

let recObjectUrl = null;
let recPlaying = null;       // the recording currently in the player
let recSaveAt = 0;           // throttle position writes
function fmtTime(s) {
  s = Math.max(0, Math.floor(s || 0));
  return Math.floor(s / 60) + ":" + String(s % 60).padStart(2, "0");
}
function playRecording(rec) {
  const a = $("#recAudio");
  if (recObjectUrl) URL.revokeObjectURL(recObjectUrl);
  recObjectUrl = URL.createObjectURL(rec.blob);
  recPlaying = rec;
  a.src = recObjectUrl; a.hidden = false;
  // Resume from where the listener left off (unless near the end).
  a.onloadedmetadata = () => {
    if (isFinite(a.duration) && a.duration > 0 && rec.duration !== a.duration) {
      rec.duration = a.duration; recPut(rec);   // remember length for progress bars
    }
    if (rec.position && rec.position < (a.duration || 1e9) - 2) a.currentTime = rec.position;
    a.play().catch(() => {});
  };
  const at = rec.position > 5 ? ` from ${fmtTime(rec.position)}` : "";
  announce("Playing " + rec.title + at, "ok");
}
// Persist playback position so the next play resumes (favourites + resume).
(function bindRecAudio() {
  const a = $("#recAudio"); if (!a) return;
  a.addEventListener("timeupdate", () => {
    if (!recPlaying) return;
    const now = Date.now();
    if (now - recSaveAt > 5000) { recSaveAt = now; recPlaying.position = a.currentTime; recPut(recPlaying); }
  });
  a.addEventListener("pause", () => {
    if (recPlaying) { recPlaying.position = a.currentTime; recPut(recPlaying); }
  });
  a.addEventListener("ended", () => {
    if (recPlaying) {
      recPlaying.position = 0; recPlaying.completed = true; recPut(recPlaying);
      recPlaying = null; loadRecordings();   // moves it to the Completed tab
    }
  });
})();

// Every folder name the user has, whether created empty or in use by a recording.
function allFolderNames(recs) {
  return [...new Set([...getFolders(), ...recs.map((r) => r.folder)])]
    .filter((f) => f && f !== "Unfiled")
    .sort((a, b) => a.localeCompare(b));
}

// Move a recording into another folder (re-stores the same blob with a new folder).
async function moveRecording(rec, folder) {
  rec.folder = folder || "Unfiled";
  await recPut(rec);
  announce(`Moved “${rec.title}” to ${rec.folder}.`, "ok");
  loadRecordings();
}

// Delete a folder: its recordings fall back to Unfiled, the folder is removed.
async function deleteFolder(name) {
  if (!name || name === "All" || name === "Unfiled") return;
  if (!window.confirm(`Delete the folder “${name}”? Its recordings move to Unfiled.`)) return;
  let recs = [];
  try { recs = await recAll(); } catch (_) {}
  for (const r of recs.filter((r) => r.folder === name)) {
    r.folder = "Unfiled"; await recPut(r);
  }
  setFolders(getFolders().filter((f) => f !== name));
  activeFolder = "All";
  announce(`Folder “${name}” deleted.`, "ok");
  loadRecordings();
}

// --- My Library view state + helpers ---
let activeSeg = "todo";   // "todo" | "done"
let recQuery = "";        // search text
let openMenuId = null;    // id of the card whose ⋮ menu is open
let menuMode = "main";    // "main" | "move"  (which menu page is showing)
let recSort = localStorage.getItem("eyewaz_sort") || "new";  // new|old|az|prog
const SORT_LABELS = { new: "Newest", old: "Oldest", az: "A–Z", prog: "In progress" };
const SORT_CYCLE = ["new", "old", "az", "prog"];
function sortRecs(list) {
  const a = list.slice();
  if (recSort === "old") a.sort((x, y) => x.createdAt - y.createdAt);
  else if (recSort === "az") a.sort((x, y) => (x.title || "").localeCompare(y.title || ""));
  else if (recSort === "prog") a.sort((x, y) => recProgress(y) - recProgress(x) || y.createdAt - x.createdAt);
  else a.sort((x, y) => y.createdAt - x.createdAt);   // newest
  return a;
}

function _initials(t) {
  const parts = (t || "?").trim().split(/\s+/).slice(0, 2);
  return (parts.map((p) => p[0] || "").join("") || "?").toUpperCase();
}
function _coverColor(t) {
  let h = 0; for (let i = 0; i < (t || "").length; i++) h = (h * 31 + t.charCodeAt(i)) % 360;
  return `hsl(${h}, 42%, 60%)`;
}
function fmtDuration(sec) {
  sec = Math.round(sec || 0);
  if (!sec) return "";
  const m = Math.round(sec / 60);
  return (m < 1 ? 1 : m) + " min";
}
function recProgress(rec) {
  if (rec.completed) return 100;
  if (rec.duration && rec.position) return Math.min(100, Math.round((rec.position / rec.duration) * 100));
  return 0;
}

function bindLibraryControls() {
  const search = $("#recSearch");
  if (search && !search.dataset.bound) {
    search.dataset.bound = "1";
    let t = 0;
    search.addEventListener("input", () => {
      clearTimeout(t);
      t = setTimeout(() => { recQuery = search.value.trim().toLowerCase(); loadRecordings(); }, 180);
    });
  }
  const todo = $("#segTodo"), done = $("#segDone");
  if (todo && !todo.dataset.bound) { todo.dataset.bound = "1"; todo.addEventListener("click", () => { activeSeg = "todo"; loadRecordings(); }); }
  if (done && !done.dataset.bound) { done.dataset.bound = "1"; done.addEventListener("click", () => { activeSeg = "done"; loadRecordings(); }); }
  const sortBtn = $("#recSort");
  if (sortBtn && !sortBtn.dataset.bound) {
    sortBtn.dataset.bound = "1";
    sortBtn.addEventListener("click", () => {
      recSort = SORT_CYCLE[(SORT_CYCLE.indexOf(recSort) + 1) % SORT_CYCLE.length];
      localStorage.setItem("eyewaz_sort", recSort);
      announce("Sorted by " + SORT_LABELS[recSort], "ok");
      loadRecordings();
    });
  }
  if (!document._libMenuClose) {
    document._libMenuClose = true;
    document.addEventListener("click", (e) => {
      if (openMenuId && !e.target.closest(".lib-card-wrap")) { openMenuId = null; menuMode = "main"; loadRecordings(); }
    });
  }
}

async function loadRecordings() {
  const ul = $("#recList"); if (!ul) return;
  bindLibraryControls();
  let recs = [];
  try { recs = await recAll(); } catch (_) {}
  const custom = allFolderNames(recs);
  const FAV = "★ Favourites";
  const chipFolders = ["All", FAV, ...custom, "Unfiled"];
  if (!chipFolders.includes(activeFolder)) activeFolder = "All";

  // Segmented To-do / Completed
  const segTodo = $("#segTodo"), segDone = $("#segDone");
  if (segTodo) { segTodo.classList.toggle("is-on", activeSeg === "todo"); segTodo.setAttribute("aria-selected", String(activeSeg === "todo")); }
  if (segDone) { segDone.classList.toggle("is-on", activeSeg === "done"); segDone.setAttribute("aria-selected", String(activeSeg === "done")); }
  const sortBtn = $("#recSort");
  if (sortBtn) sortBtn.textContent = "Sort: " + SORT_LABELS[recSort];

  // Folder chips (counts) + delete control for a custom folder
  const bar = $("#folderBar"); bar.innerHTML = "";
  chipFolders.forEach((f) => {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "folder-chip" + (f === activeFolder ? " is-active" : "");
    const count = f === "All" ? recs.length : f === FAV ? recs.filter((r) => r.fav).length : recs.filter((r) => r.folder === f).length;
    b.textContent = f === "All" ? `All (${count})` : `${f} (${count})`;
    b.setAttribute("aria-pressed", String(f === activeFolder));
    b.addEventListener("click", () => { activeFolder = f; loadRecordings(); });
    bar.appendChild(b);
  });
  if (activeFolder !== "All" && activeFolder !== "Unfiled" && activeFolder !== FAV) {
    const del = document.createElement("button");
    del.type = "button"; del.className = "folder-chip folder-del";
    del.innerHTML = `<svg class="ic" aria-hidden="true"><use href="#ic-trash"/></svg> Delete “${escapeHtml(activeFolder)}”`;
    del.setAttribute("aria-label", `Delete folder ${activeFolder}`);
    del.addEventListener("click", () => deleteFolder(activeFolder));
    bar.appendChild(del);
  }

  const moveOptions = ["Unfiled", ...custom];

  // Filter: folder -> segment (completed?) -> search, then sort.
  const shown = sortRecs(recs
    .filter((r) => activeFolder === "All" ? true : activeFolder === FAV ? r.fav : r.folder === activeFolder)
    .filter((r) => activeSeg === "done" ? !!r.completed : !r.completed)
    .filter((r) => !recQuery || (r.title || "").toLowerCase().includes(recQuery)));

  ul.innerHTML = "";
  const empty = $("#recEmpty");
  if (empty) {
    empty.hidden = shown.length > 0;
    if (!shown.length) empty.textContent = recQuery
      ? "No recordings match your search."
      : (activeSeg === "done" ? "Nothing completed yet." : "Nothing to do here yet.");
  }
  if (!shown.length) return;

  shown.forEach((rec) => {
    const li = document.createElement("li");
    li.className = "lib-card-wrap";
    const pct = recProgress(rec);
    const date = new Date(rec.createdAt).toLocaleDateString(undefined, { day: "numeric", month: "short" });
    const meta = [fmtDuration(rec.duration), date].filter(Boolean).join(" · ");
    const opts = moveOptions.map((f) => `<option value="${escapeHtml(f)}"${f === rec.folder ? " selected" : ""}>${escapeHtml(f)}</option>`).join("");
    const menuOpen = openMenuId === rec.id;
    const resume = (rec.position > 5 && !rec.completed) ? " · resume " + fmtTime(rec.position) : "";
    // Clean tap-menu — no native dropdowns. Two pages: main actions + folder picker.
    let menuHtml = "";
    if (menuOpen && menuMode === "move") {
      menuHtml = `<div class="lib-menu" role="menu">` +
        `<div class="lib-menu-head">Move to folder</div>` +
        moveOptions.map((f) =>
          `<button class="lib-menu-item${f === rec.folder ? " current" : ""}" data-mv="${escapeHtml(f)}" role="menuitem">${f === rec.folder ? "✓ " : ""}${escapeHtml(f)}</button>`
        ).join("") +
        `<button class="lib-menu-item accent" data-mv="__new" role="menuitem">＋ New folder…</button>` +
        `<button class="lib-menu-item back" data-act="back" role="menuitem">‹ Back</button>` +
      `</div>`;
    } else if (menuOpen) {
      menuHtml = `<div class="lib-menu" role="menu">` +
        `<button class="lib-menu-item" data-act="fav" role="menuitem">${rec.fav ? "Remove from favourites" : "Add to favourites"}</button>` +
        `<button class="lib-menu-item" data-act="move" role="menuitem">Move to folder…</button>` +
        `<button class="lib-menu-item" data-act="toggle" role="menuitem">${rec.completed ? "Mark as to-do" : "Mark completed"}</button>` +
        `<button class="lib-menu-item danger" data-act="delete" role="menuitem">Delete</button>` +
      `</div>`;
    }
    li.innerHTML =
      `<div class="lib-card">` +
        `<button class="lib-cover" aria-label="Play ${escapeHtml(rec.title)}" style="--cv:${_coverColor(rec.title)}">` +
          `<span class="lib-cover-ini" aria-hidden="true">${escapeHtml(_initials(rec.title))}</span>` +
          `<span class="lib-cover-play" aria-hidden="true"><svg class="ic" aria-hidden="true"><use href="#ic-play"/></svg></span>` +
        `</button>` +
        `<div class="lib-body">` +
          `<div class="lib-line1">` +
            `<strong class="lib-title">${escapeHtml(rec.title)}</strong>` +
            `<span class="lib-meta">${escapeHtml(meta)}</span>` +
            `<button class="lib-kebab" aria-haspopup="true" aria-expanded="${menuOpen}" aria-label="More options for ${escapeHtml(rec.title)}">⋮</button>` +
          `</div>` +
          `<p class="lib-sub">${escapeHtml(rec.folder || "Unfiled")}${resume}</p>` +
          `<div class="lib-line3">` +
            `<span class="lib-bar"><span class="lib-bar-fill" style="width:${pct}%"></span></span>` +
            `<button class="lib-heart${rec.fav ? " is-fav" : ""}" aria-pressed="${!!rec.fav}" aria-label="${rec.fav ? "Remove from" : "Add to"} favourites">${rec.fav ? "♥" : "♡"}</button>` +
          `</div>` +
        `</div>` +
      `</div>` + menuHtml;

    li.querySelector(".lib-cover").addEventListener("click", () => playRecording(rec));
    li.querySelector(".lib-heart").addEventListener("click", async () => {
      rec.fav = !rec.fav; await recPut(rec);
      announce(rec.fav ? `Added “${rec.title}” to favourites.` : "Removed from favourites.", "ok");
      loadRecordings();
    });
    li.querySelector(".lib-kebab").addEventListener("click", (e) => {
      e.stopPropagation();
      openMenuId = menuOpen ? null : rec.id; menuMode = "main"; loadRecordings();
    });
    const menuEl = li.querySelector(".lib-menu");
    if (menuEl) {
      menuEl.addEventListener("click", (e) => e.stopPropagation());
      menuEl.querySelectorAll("[data-act]").forEach((b) => b.addEventListener("click", async () => {
        const act = b.dataset.act;
        if (act === "move") { menuMode = "move"; loadRecordings(); }
        else if (act === "back") { menuMode = "main"; loadRecordings(); }
        else if (act === "fav") {
          rec.fav = !rec.fav; await recPut(rec); openMenuId = null; menuMode = "main";
          announce(rec.fav ? `Added “${rec.title}” to favourites.` : "Removed from favourites.", "ok");
          loadRecordings();
        } else if (act === "toggle") {
          rec.completed = !rec.completed; if (rec.completed) rec.position = 0;
          await recPut(rec); openMenuId = null; menuMode = "main"; loadRecordings();
        } else if (act === "delete") {
          if (window.confirm("Delete this recording from your device?")) { await recDel(rec.id); openMenuId = null; menuMode = "main"; loadRecordings(); }
        }
      }));
      menuEl.querySelectorAll("[data-mv]").forEach((b) => b.addEventListener("click", async () => {
        let target = b.dataset.mv;
        if (target === "__new") {
          const name = (window.prompt("New folder name:") || "").trim().slice(0, 30);
          if (!name || name === "All" || name === "Unfiled") { return; }
          const fs = getFolders(); if (!fs.includes(name)) { fs.push(name); setFolders(fs); }
          target = name;
        }
        openMenuId = null; menuMode = "main";
        await moveRecording(rec, target);   // announces + reloads
      }));
    }
    ul.appendChild(li);
  });
}

function createFolder() {
  const name = ($("#newFolderName").value || "").trim().slice(0, 30);
  if (!name) { announce("Type a folder name first.", ""); return; }
  if (name === "All" || name === "Unfiled") { announce("Please choose a different name.", ""); return; }
  const folders = getFolders();
  if (!folders.includes(name)) { folders.push(name); setFolders(folders); }
  $("#newFolderName").value = "";
  activeFolder = name;
  announce(`Folder “${name}” created.`, "ok");
  loadRecordings();
}
$("#newFolderBtn")?.addEventListener("click", createFolder);
$("#newFolderName")?.addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); createFolder(); } });

// Old callers used loadLibrary() (the server shelf) — keep them working.
function loadLibrary() { loadRecordings(); }

function escapeHtml(s) {
  return s.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

/* ------------------------------ Account & voice ----------------------------- */

let userPrefs = { engine: "azure", language: "ur-PK", voice: "ur-PK-UzmaNeural", rate: 1.0 };
let azureVoices = null;

let userProfile = {};
async function loadPrefs() {
  try {
    const p = await api("/profile", { method: "GET" });
    userProfile = p || {};
    if (p && p.preferences) userPrefs = p.preferences;
    Billing.set(p && p.usage);
    return p;
  } catch (_) { return null; }
}

/* ------------------------------ Membership / quota -------------------------- */
let userUsage = null;
const Billing = (() => {
  function set(u) { userUsage = u || null; render(); }
  function render() {
    if (userUsage) {
      const u = userUsage;
      const line = document.getElementById("planLine");
      if (line) {
        line.textContent = `Plan: ${u.plan_label} — ${u.remaining} of ${u.limit} commands left this month. `;
        const a = document.createElement("a");
        a.href = "#"; a.className = "upgrade-link";
        a.textContent = (u.plan === "supermax" ? "Manage plan" : "Upgrade") + " ↗";
        a.addEventListener("click", (e) => { e.preventDefault(); openAccount(); });
        line.appendChild(a);
      }
      const cur = document.getElementById("currentPlanText");
      if (cur) cur.textContent =
        `You're on the ${u.plan_label} plan — ${u.remaining} of ${u.limit} commands left this month.`;
    }
    document.querySelectorAll(".plan-card").forEach((c) =>
      c.classList.toggle("is-current", !!userUsage && c.dataset.plan === userUsage.plan));
  }
  async function refresh() { try { const d = await api("/usage"); set(d.usage); } catch (_) {} }
  function onQuota(data) {
    if (data && data.usage) set(data.usage);
    announce(data && data.message ? data.message
      : "You've reached this month's command limit. Upgrade for more.", "error");
  }
  function recordingsLimit() { return userUsage ? userUsage.recordings_limit : 3; }
  function remindersLimit() { return userUsage ? userUsage.reminders_limit : 1; }
  // Charge one command for the text reader (its only server calls are shared utilities).
  async function consumeOne() {
    try { const d = await api("/usage", { method: "POST" }); set(d.usage); return true; }
    catch (_) { return false; }   // api() already surfaced the upgrade prompt on 402
  }
  return { set, render, refresh, onQuota, recordingsLimit, remindersLimit, consumeOne };
})();

// Prices shown on the plan cards (£/month). Set the real figures here.
const PLAN_PRICES = { monthly: "4.99", supermax: "9.99" };

const Plan = (() => {
  let cfg = null;          // /api/paypal/config result
  let sdkLoading = null;   // promise so we load the SDK once

  function init() {
    document.querySelectorAll("[data-price]").forEach((el) => {
      const p = PLAN_PRICES[el.dataset.price]; if (p) el.textContent = p;
    });
    document.querySelectorAll(".plan-upgrade").forEach((b) => {
      if (b.dataset.bound) return;
      b.dataset.bound = "1";
      b.addEventListener("click", () => placeholder(b.dataset.plan));
    });
    const cancel = document.getElementById("cancelSubBtn");
    if (cancel && !cancel.dataset.bound) {
      cancel.dataset.bound = "1";
      cancel.addEventListener("click", cancelSubscription);
    }
    document.querySelectorAll(".stripe-btn").forEach((b) => {
      if (b.dataset.bound) return;
      b.dataset.bound = "1";
      b.addEventListener("click", () => stripeCheckout(b.dataset.plan));
    });
    Billing.render();
    setupPayPal();
    setupStripe();
  }

  async function setupStripe() {
    let sc = null;
    try { sc = await api("/stripe/config", { auth: false }); } catch (_) {}
    if (sc && sc.enabled) {
      document.querySelectorAll(".stripe-btn").forEach((b) => (b.hidden = false));
    }
  }

  async function stripeCheckout(plan) {
    announce("Opening secure card and Klarna checkout…", "busy");
    try {
      const d = await api("/stripe/checkout", { method: "POST", body: { plan } });
      if (d && d.url) { window.location.href = d.url; }   // redirect to Stripe
    } catch (e) { announce(e.message || "Could not start checkout.", "error"); }
  }

  function placeholder(plan) {
    announce("PayPal checkout is being set up. It will appear here once payments are switched on.", "");
    window.alert("PayPal checkout for the " + plan + " plan is being set up and will appear here soon.");
  }

  async function setupPayPal() {
    try { cfg = await api("/paypal/config", { auth: false }); } catch (_) { cfg = null; }
    const setupBtn = document.getElementById("paypalSetupBtn");
    // Creds present but plans not created yet → offer a one-click finish (key-gated).
    if (setupBtn) {
      const needsSetup = cfg && cfg.configured && !cfg.enabled;
      setupBtn.hidden = !needsSetup;
      if (needsSetup && !setupBtn.dataset.bound) {
        setupBtn.dataset.bound = "1";
        setupBtn.addEventListener("click", finishPayPalSetup);
      }
    }
    const enabled = cfg && cfg.enabled && cfg.client_id;
    if (!enabled) return;                       // keep placeholder buttons
    try { await loadSdk(cfg.client_id, cfg.currency || "GBP"); }
    catch (_) { return; }                       // SDK blocked → keep placeholders
    ["monthly", "supermax"].forEach((plan) => renderButton(plan));
    // Offer cancellation if the user is already on a paid plan.
    const cancel = document.getElementById("cancelSubBtn");
    if (cancel && userUsage && userUsage.plan !== "free") cancel.hidden = false;
  }

  async function finishPayPalSetup() {
    const key = window.prompt("Enter your DEV_PLAN_KEY to create the PayPal plans:");
    if (!key) return;
    announce("Creating PayPal plans…", "busy");
    try {
      const d = await api("/paypal/setup", { method: "POST",
        body: { key, prices: PLAN_PRICES } });
      announce(d.message || "PayPal is now live.", "ok");
      window.alert(d.message || "PayPal plans created — checkout is live.");
      await setupPayPal();   // re-render with live buttons
    } catch (e) { announce(e.message || "PayPal setup failed.", "error"); }
  }

  function loadSdk(clientId, currency) {
    if (window.paypal) return Promise.resolve();
    if (sdkLoading) return sdkLoading;
    sdkLoading = new Promise((res, rej) => {
      const s = document.createElement("script");
      s.src = "https://www.paypal.com/sdk/js?client-id=" + encodeURIComponent(clientId) +
        "&vault=true&intent=subscription&currency=" + encodeURIComponent(currency);
      s.onload = res; s.onerror = rej;
      document.head.appendChild(s);
    });
    return sdkLoading;
  }

  function renderButton(plan) {
    const planId = cfg.plans && cfg.plans[plan];
    const slot = document.getElementById("pp-" + plan);
    const placeholderBtn = document.querySelector(`.plan-upgrade[data-plan="${plan}"]`);
    if (!planId || !slot || !window.paypal) return;
    if (placeholderBtn) placeholderBtn.hidden = true;
    slot.hidden = false; slot.innerHTML = "";
    window.paypal.Buttons({
      style: { layout: "horizontal", label: "subscribe", height: 44 },
      createSubscription: (data, actions) => actions.subscription.create({ plan_id: planId }),
      onApprove: (data) => activate(data.subscriptionID, plan),
      onError: () => announce("PayPal could not start checkout. Please try again.", "error"),
    }).render("#pp-" + plan);
  }

  async function activate(subscriptionID, plan) {
    announce("Confirming your subscription…", "busy");
    try {
      const d = await api("/paypal/activate", { method: "POST",
        body: { subscription_id: subscriptionID, plan } });
      Billing.set(d.usage);
      announce(d.message || `You're now on the ${plan} plan. Thank you!`, "ok");
      window.alert(d.message || `You're now on the ${plan} plan. Thank you!`);
    } catch (e) {
      announce(e.message || "We couldn't confirm the payment. If you were charged, contact support.", "error");
    }
  }

  async function cancelSubscription() {
    if (!window.confirm("Cancel your subscription? You'll keep access until the period ends.")) return;
    try {
      const d = await api("/paypal/cancel", { method: "POST" });
      if (d.usage) Billing.set(d.usage);
      announce(d.message || "Your subscription will not renew.", "ok");
    } catch (e) { announce(e.message || "Could not cancel right now.", "error"); }
  }

  return { init };
})();

// Console helper for testing tiers before payments (needs DEV_PLAN_KEY on the server).
// Usage:  setPlan("monthly", "your-dev-key")
window.setPlan = (plan, key) =>
  api("/dev/plan", { method: "POST", body: { plan, key } })
    .then((d) => { Billing.set(d.usage); announce("Plan set to " + plan + ".", "ok"); return d; })
    .catch((e) => { announce(e.message || "Could not set plan.", "error"); });

// One-shot PayPal plan creation (needs DEV_PLAN_KEY + PayPal creds in env).
// Usage:  setupPayPal("your-dev-key")    → creates + saves plans, PayPal goes live.
window.setupPayPal = (key, prices) =>
  api("/paypal/setup", { method: "POST", body: { key, prices: prices || PLAN_PRICES } })
    .then((d) => { console.log(d); announce(d.message || "PayPal is live.", "ok"); return d; })
    .catch((e) => { announce(e.message || "PayPal setup failed.", "error"); });

/* ----------------- Passkeys: Face ID / Touch ID / fingerprint --------------- */
const Passkey = (() => {
  const supported = !!(window.PublicKeyCredential && navigator.credentials);

  function b64urlToBuf(s) {
    s = s.replace(/-/g, "+").replace(/_/g, "/");
    const pad = s.length % 4 ? "=".repeat(4 - (s.length % 4)) : "";
    const bin = atob(s + pad);
    const u = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) u[i] = bin.charCodeAt(i);
    return u.buffer;
  }
  function bufToB64url(buf) {
    const u = new Uint8Array(buf); let s = "";
    for (const b of u) s += String.fromCharCode(b);
    return btoa(s).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
  }

  // Enrol the current (signed-in) device.
  async function enroll() {
    if (!supported) { announce("This device doesn't support Face ID sign-in.", ""); return; }
    const st = document.getElementById("faceIdStatus");
    if (st) { st.className = "status busy"; st.textContent = "Follow your device's prompt…"; }
    try {
      const { options, token } = await api("/webauthn/register/options", { method: "POST" });
      options.challenge = b64urlToBuf(options.challenge);
      options.user.id = b64urlToBuf(options.user.id);
      if (options.excludeCredentials)
        options.excludeCredentials = options.excludeCredentials.map((c) => ({ ...c, id: b64urlToBuf(c.id) }));
      const cred = await navigator.credentials.create({ publicKey: options });
      const out = {
        id: cred.id, rawId: bufToB64url(cred.rawId), type: cred.type,
        authenticatorAttachment: cred.authenticatorAttachment || undefined,
        clientExtensionResults: cred.getClientExtensionResults ? cred.getClientExtensionResults() : {},
        response: {
          clientDataJSON: bufToB64url(cred.response.clientDataJSON),
          attestationObject: bufToB64url(cred.response.attestationObject),
        },
      };
      const d = await api("/webauthn/register/verify", { method: "POST", body: { credential: out, token } });
      if (st) { st.className = "status ok"; st.textContent = d.message || "Face ID enabled."; }
      announce(d.message || "Face ID sign-in is enabled on this device.", "ok");
    } catch (e) {
      const msg = (e && e.name === "NotAllowedError") ? "Cancelled or timed out." : (e.message || "Could not enable Face ID.");
      if (st) { st.className = "status error"; st.textContent = msg; }
      announce(msg, "error");
    }
  }

  // Sign in with a passkey (usernameless — the device offers the saved passkey).
  async function login() {
    if (!supported) { announce("This device doesn't support Face ID sign-in.", ""); return; }
    announce("Follow your device's Face ID prompt…", "busy");
    try {
      const email = ($("#loginEmail")?.value || "").trim();
      const { options, token } = await api("/webauthn/login/options", { method: "POST", auth: false, body: { email } });
      options.challenge = b64urlToBuf(options.challenge);
      if (options.allowCredentials)
        options.allowCredentials = options.allowCredentials.map((c) => ({ ...c, id: b64urlToBuf(c.id) }));
      const cred = await navigator.credentials.get({ publicKey: options });
      const out = {
        id: cred.id, rawId: bufToB64url(cred.rawId), type: cred.type,
        authenticatorAttachment: cred.authenticatorAttachment || undefined,
        clientExtensionResults: cred.getClientExtensionResults ? cred.getClientExtensionResults() : {},
        response: {
          clientDataJSON: bufToB64url(cred.response.clientDataJSON),
          authenticatorData: bufToB64url(cred.response.authenticatorData),
          signature: bufToB64url(cred.response.signature),
          userHandle: cred.response.userHandle ? bufToB64url(cred.response.userHandle) : null,
        },
      };
      const d = await api("/webauthn/login/verify", { method: "POST", auth: false, body: { credential: out, token } });
      setToken(d.token);
      announce("Signed in with Face ID. Welcome back" + (d.name ? ", " + d.name.split(" ")[0] : "") + ".", "ok");
      enterApp();
    } catch (e) {
      const msg = (e && e.name === "NotAllowedError") ? "Cancelled or timed out." : (e.message || "Face ID sign-in didn't work.");
      announce(msg, "error");
    }
  }

  function init() {
    if (!supported) return;
    const loginBtn = document.getElementById("faceIdLoginBtn");
    if (loginBtn) {
      loginBtn.hidden = false;
      if (!loginBtn.dataset.bound) { loginBtn.dataset.bound = "1"; loginBtn.addEventListener("click", login); }
    }
    const card = document.getElementById("faceIdCard");
    if (card) card.hidden = false;
    const enableBtn = document.getElementById("faceIdEnableBtn");
    if (enableBtn && !enableBtn.dataset.bound) { enableBtn.dataset.bound = "1"; enableBtn.addEventListener("click", enroll); }
  }

  return { init, login, enroll, supported };
})();
Passkey.init();

/* ------------------------------ My Day assistant ---------------------------- */
function greetingFor(d) {
  const h = d.getHours();
  return h < 12 ? "Good morning" : h < 17 ? "Good afternoon" : "Good evening";
}
function todayListText() {
  const day = new Date().getDay();           // 0 Sun … 6 Sat
  const weekend = day === 0 || day === 6;
  return ((weekend ? userProfile.todo_weekend : userProfile.todo_weekday) || "").trim();
}
function renderMyDay() {
  const name = (userProfile.name || "").split(" ")[0];
  if ($("#dayGreeting")) $("#dayGreeting").textContent = greetingFor(new Date()) + (name ? ", " + name : "") + "!";
  if ($("#dayDate")) $("#dayDate").textContent =
    new Date().toLocaleDateString(undefined, { weekday: "long", year: "numeric", month: "long", day: "numeric" });
  const list = todayListText();
  if ($("#dayList")) $("#dayList").textContent = list || "No list set for today — add one in Account.";
}
$("#startDayBtn")?.addEventListener("click", async () => {
  const st = $("#dayStatus"), btn = $("#startDayBtn");
  const name = (userProfile.name || "").split(" ")[0];
  const greeting = greetingFor(new Date()) + (name ? ", " + name : "") + ".";
  const dateStr = "Today is " + new Date().toLocaleDateString(undefined, { weekday: "long", month: "long", day: "numeric" }) + ".";
  const list = todayListText();
  const listText = list
    ? "Here is your list for today. " + list.split(/\n+/).filter(Boolean).join(". ") + "."
    : "You have no list set for today.";
  const brief = `${greeting} ${dateStr} ${listText}`;
  btn.disabled = true; st.className = "status busy"; st.textContent = "Preparing your morning…";
  try {
    const tr = await api("/translate", { method: "POST", body: { text: brief, to: userPrefs.language } });
    const speech = tr.translated || brief;
    const sp = await api("/speak", { method: "POST", body: { text: speech, voiceName: userPrefs.voice, rate: userPrefs.rate } });
    const a = $("#dayAudio"); a.src = sp.audio_url; a.hidden = false;
    st.className = "status ok"; st.textContent = "Playing your morning brief.";
    a.play().catch(() => (st.textContent = "Ready — press play to listen."));
  } catch (err) {
    st.className = "status error"; st.textContent = err.message || "Could not start your day.";
  } finally { btn.disabled = false; }
});

/* ----------------------- Ask Eyewaz: voice assistant ------------------------ */
// Hands-free conversational AI. Speech in (Web Speech Recognition) → /api/assistant
// (Claude) → spoken reply (browser TTS, or Azure for languages the browser
// can't voice, like Urdu). Falls back to typed input where speech isn't available.
const Assistant = (() => {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  let history = [];            // [{role, content}] short rolling context
  let recog = null, listening = false, busy = false;

  const el = (id) => document.getElementById(id);
  function status(msg, kind = "") {
    const s = el("asstStatus");
    if (s) { s.textContent = msg || ""; s.className = "status" + (kind ? " " + kind : ""); }
  }
  function bubble(role, text) {
    const log = el("asstLog");
    if (!log) return;
    const div = document.createElement("div");
    div.className = "asst-bubble asst-" + role;
    div.textContent = (role === "user" ? "You: " : "Eyewaz: ") + text;
    applyLangDir(div, userPrefs.language);
    log.appendChild(div);
    log.scrollTop = log.scrollHeight;
  }

  // Speak the reply in the user's language. Prefer the browser voice; if none
  // exists (typical for Urdu), use Azure via /api/speak for a natural voice.
  async function speakReply(text) {
    const lang = userPrefs.language || "en";
    const stopBtn = el("asstStopBtn");
    if (TTS.supported && TTS.hasVoice(lang)) {
      stopBtn.hidden = false;
      TTS.speakLong(text, lang, { rate: userPrefs.rate, onend: () => (stopBtn.hidden = true) });
      return;
    }
    try {
      const sp = await api("/speak", { method: "POST",
        body: { text, voiceName: userPrefs.voice, rate: userPrefs.rate } });
      const a = el("dayAudio");
      a.src = sp.audio_url; a.hidden = false;
      a.play().catch(() => {});
    } catch (_) { /* speaking is best-effort; the text is already on screen */ }
  }

  async function send(message) {
    if (!message || busy) return;
    busy = true;
    bubble("user", message);
    history.push({ role: "user", content: message });
    status("Eyewaz is thinking…", "busy");
    try {
      const d = await api("/assistant", { method: "POST",
        body: { message, history: history.slice(-12) } });
      const reply = (d && d.reply) || "Sorry, I have nothing to say.";
      history.push({ role: "assistant", content: reply });
      if (history.length > 16) history = history.slice(-16);
      bubble("assistant", reply);
      status("");
      await speakReply(reply);
    } catch (err) {
      status(err.message || "The assistant is unavailable right now.", "error");
    } finally { busy = false; }
  }

  function startListening() {
    if (!SR) {
      status("Voice input isn't supported in this browser — type your message instead.", "");
      el("asstText")?.focus();
      return;
    }
    if (listening) { recog && recog.stop(); return; }
    TTS.stop();
    recog = new SR();
    recog.lang = userPrefs.language || "en-US";
    recog.interimResults = false;
    recog.maxAlternatives = 1;
    recog.onstart = () => { listening = true; setMic(true); status("Listening… speak now.", "busy"); };
    recog.onerror = (e) => {
      listening = false; setMic(false);
      status(e.error === "not-allowed"
        ? "Microphone permission is needed to talk to Eyewaz."
        : "I didn't hear anything. Tap the microphone to try again.", "");
    };
    recog.onend = () => { listening = false; setMic(false); };
    recog.onresult = (e) => {
      const said = e.results[0][0].transcript.trim();
      if (said) send(said);
    };
    try { recog.start(); } catch (_) { /* already started */ }
  }

  function setMic(on) {
    const btn = el("asstMicBtn");
    if (!btn) return;
    btn.innerHTML = '<svg class="ic" aria-hidden="true"><use href="#ic-mic"/></svg> ' + (on ? "Listening…" : "Talk to Eyewaz");
    btn.classList.toggle("is-listening", on);
    btn.setAttribute("aria-pressed", String(on));
  }

  function init() {
    const mic = el("asstMicBtn"), stop = el("asstStopBtn"), form = el("asstForm");
    if (mic && !mic.dataset.bound) {
      mic.dataset.bound = "1";
      mic.addEventListener("click", startListening);
    }
    if (stop && !stop.dataset.bound) {
      stop.dataset.bound = "1";
      stop.addEventListener("click", () => { TTS.stop(); const a = el("dayAudio"); if (a) a.pause(); stop.hidden = true; });
    }
    if (form && !form.dataset.bound) {
      form.dataset.bound = "1";
      form.addEventListener("submit", (e) => {
        e.preventDefault();
        const input = el("asstText");
        const msg = (input.value || "").trim();
        if (msg) { input.value = ""; send(msg); }
      });
    }
  }

  return { init };
})();

/* Speak text in the user's chosen language: browser voice if available,
   else Azure (e.g. Urdu). Shared by reminders and other spoken prompts. */
function speakInUserLang(text) {
  if (!text) return;
  const lang = userPrefs.language || "en";
  if (TTS.supported && TTS.hasVoice(lang)) {
    TTS.speakLong(text, lang, { rate: userPrefs.rate });
    return;
  }
  api("/speak", { method: "POST", body: { text, voiceName: userPrefs.voice, rate: userPrefs.rate } })
    .then((sp) => { const a = $("#dayAudio"); if (a) { a.src = sp.audio_url; a.hidden = false; a.play().catch(() => {}); } })
    .catch(() => {});
}

/* ----------------------- Reminders: spoken time-based nudges ---------------- */
const Reminders = (() => {
  function get() { try { return JSON.parse(localStorage.getItem("eyewaz_reminders") || "[]"); } catch (_) { return []; } }
  function set(list) { localStorage.setItem("eyewaz_reminders", JSON.stringify(list)); }

  const REPEAT_LABEL = { daily: "Every day", weekdays: "Weekdays", weekends: "Weekends", once: "Just once" };

  function appliesToday(r) {
    const d = new Date().getDay();           // 0 Sun … 6 Sat
    const weekday = d >= 1 && d <= 5;
    if (r.repeat === "weekdays") return weekday;
    if (r.repeat === "weekends") return !weekday;
    return true;                              // daily, once
  }
  function speak12h(t) {
    const [h, m] = t.split(":").map(Number);
    const ap = h < 12 ? "AM" : "PM"; const h12 = ((h + 11) % 12) + 1;
    return `${h12}:${String(m).padStart(2, "0")} ${ap}`;
  }

  function render() {
    const ul = $("#reminderList"); if (!ul) return;
    const list = get().sort((a, b) => a.time.localeCompare(b.time));
    ul.innerHTML = "";
    if (!list.length) {
      ul.innerHTML = '<li class="lede">No reminders yet. Add one above.</li>';
      return;
    }
    list.forEach((r) => {
      const li = document.createElement("li");
      li.className = "reminder-item";
      li.innerHTML =
        `<span class="reminder-when">${speak12h(r.time)}</span>` +
        `<span class="reminder-info"><strong>${escapeHtml(r.label)}</strong>` +
        `<span class="lib-snippet">${REPEAT_LABEL[r.repeat] || "Every day"}</span></span>` +
        `<button class="round-btn rem-del" aria-label="Delete reminder ${escapeHtml(r.label)}"><svg class="ic" aria-hidden="true"><use href="#ic-trash"/></svg></button>`;
      li.querySelector(".rem-del").addEventListener("click", () => {
        set(get().filter((x) => x.id !== r.id));
        announce("Reminder deleted.", "ok");
        render();
      });
      ul.appendChild(li);
    });
  }

  function fire(r) {
    const msg = "Reminder. " + r.label;
    announce("Reminder. " + r.label, "ok");
    speakInUserLang(msg);
    try {
      if ("Notification" in window && Notification.permission === "granted")
        new Notification("EYEWAZ reminder", { body: r.label });
    } catch (_) {}
  }

  function check() {
    const now = new Date();
    const hhmm = String(now.getHours()).padStart(2, "0") + ":" + String(now.getMinutes()).padStart(2, "0");
    const today = now.getFullYear() + "-" + (now.getMonth() + 1) + "-" + now.getDate();
    const list = get();
    let changed = false;
    for (const r of list) {
      if (r.time === hhmm && r.lastFired !== today && appliesToday(r)) {
        fire(r); r.lastFired = today; changed = true;
        if (r.repeat === "once") r._remove = true;
      }
    }
    if (changed) { set(list.filter((r) => !r._remove)); render(); }
  }

  let started = false;
  function init() {
    const form = $("#reminderForm");
    if (form && !form.dataset.bound) {
      form.dataset.bound = "1";
      form.addEventListener("submit", (e) => {
        e.preventDefault();
        const time = $("#reminderTime").value;
        const label = ($("#reminderLabel").value || "").trim();
        const repeat = $("#reminderRepeat").value || "daily";
        if (!time || !label) { announce("Please set a time and a reminder.", ""); return; }
        const list = get();
        const rlimit = Billing.remindersLimit();
        if (list.length >= rlimit) {
          announce(`Your plan allows ${rlimit} reminder${rlimit === 1 ? "" : "s"}. Upgrade to add more.`, "error");
          return;
        }
        list.push({ id: "rem_" + Date.now(), time, label: label.slice(0, 120), repeat, lastFired: "" });
        set(list);
        $("#reminderLabel").value = "";
        announce(`Reminder set for ${speak12h(time)}: ${label}.`, "ok");
        // Ask once for notification permission so nudges show if the tab is in the background.
        try { if ("Notification" in window && Notification.permission === "default") Notification.requestPermission(); } catch (_) {}
        render();
      });
    }
    render();
    if (!started) { started = true; setInterval(check, 20000); check(); }  // global ticker
  }

  return { init };
})();

function accStatus(msg, kind) {
  const s = $("#accountStatus");
  s.textContent = msg;
  s.className = "status" + (kind ? " " + kind : "");
  if (msg) announce(msg, kind);
}

function currentEngine() {
  return document.querySelector('input[name="engine"]:checked')?.value || "azure";
}

async function getAzureVoices() {
  if (azureVoices) return azureVoices;
  const d = await api("/voices", { method: "GET" });
  azureVoices = (d && d.voices) || [];
  return azureVoices;
}

function browserVoiceList() {
  const voices = window.speechSynthesis ? speechSynthesis.getVoices() : [];
  return voices.map((v) => ({
    shortName: v.name, locale: v.lang, localeName: v.lang, displayName: v.name, gender: "",
  }));
}

const SAMPLES = {
  ur: "السلام علیکم، یہ آپ کی منتخب کردہ آواز ہے۔",
  ar: "مرحبا، هذا هو الصوت الذي اخترته.",
  hi: "नमस्ते, यह आपकी चुनी हुई आवाज़ है।",
};
function sampleFor(locale) {
  return SAMPLES[(locale || "").slice(0, 2)] || "Hello, this is the voice you selected for EYEWAZ.";
}

async function populateVoiceControls() {
  const engine = currentEngine();
  const voices = engine === "azure" ? await getAzureVoices() : browserVoiceList();
  const byLocale = {};
  voices.forEach((v) => { (byLocale[v.locale] = byLocale[v.locale] || []).push(v); });
  const locales = Object.keys(byLocale).sort((a, b) =>
    (byLocale[a][0].localeName || a).localeCompare(byLocale[b][0].localeName || b));

  const langSel = $("#accLanguage");
  langSel.innerHTML = "";
  locales.forEach((loc) => {
    const opt = document.createElement("option");
    opt.value = loc;
    opt.textContent = `${byLocale[loc][0].localeName || loc} (${loc})`;
    langSel.appendChild(opt);
  });
  langSel.value = (userPrefs.language && byLocale[userPrefs.language]) ? userPrefs.language : (locales[0] || "");

  const fillVoices = () => {
    const lang = langSel.value;
    const voiceSel = $("#accVoice");
    voiceSel.innerHTML = "";
    (byLocale[lang] || []).forEach((v) => {
      const opt = document.createElement("option");
      opt.value = v.shortName;
      opt.textContent = v.displayName + (v.gender ? " — " + v.gender : "");
      voiceSel.appendChild(opt);
    });
    if ([...voiceSel.options].some((o) => o.value === userPrefs.voice)) voiceSel.value = userPrefs.voice;
  };
  fillVoices();
  langSel.onchange = fillVoices;
}

// Pakistani dialect / regional-voice picker (Account).
async function loadDialects() {
  const wrap = document.getElementById("dialectList"); if (!wrap) return;
  let data;
  try { data = await api("/dialects"); } catch (_) { return; }
  const cur = userPrefs.voice;
  wrap.innerHTML = "";
  (data.dialects || []).forEach((d) => {
    const live = d.status === "live";
    const voice = (live && d.voices[0]) ? d.voices[0].shortName : d.fallback_voice;
    const locale = live ? d.locale : d.fallback_locale;
    const active = d.voices.some((v) => v.shortName === cur);
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "dialect-item" + (active ? " is-active" : "");
    btn.setAttribute("role", "listitem");
    btn.innerHTML =
      `<span class="dialect-main"><span class="dialect-name">${escapeHtml(d.label)}</span>` +
      `<span class="dialect-region">${escapeHtml(d.region)}</span></span>` +
      (live ? `<span class="dialect-badge live">Live</span>` : `<span class="dialect-badge soon">Coming soon</span>`);
    btn.addEventListener("click", async () => {
      userPrefs.language = locale; userPrefs.voice = voice; userPrefs.engine = "azure";
      try { await api("/profile", { method: "PUT", body: { preferences: userPrefs } }); } catch (_) {}
      const s = document.getElementById("dialectStatus");
      const msg = live ? `Now reading in ${d.label}.` : `${d.label} is coming soon — using standard Urdu for now.`;
      if (s) { s.className = "status ok"; s.textContent = msg; }
      announce(msg, "ok");
      loadDialects();
    });
    wrap.appendChild(btn);
  });
  renderVoiceBank(data.dialects || []);
}

// ---- Voice bank (admin) ----
function vbStatus(msg, kind) {
  const s = document.getElementById("vbStatus");
  if (s) { s.textContent = msg || ""; s.className = "status" + (kind ? " " + kind : ""); }
}
function renderVoiceBank(dialects) {
  const card = document.getElementById("voiceBankCard"); if (!card) return;
  if (localStorage.getItem("eyewaz_admin") !== "1") { card.hidden = true; return; }
  card.hidden = false;
  const sel = document.getElementById("vbDialect");
  if (sel) sel.innerHTML = dialects.map((d) =>
    `<option value="${d.id}">${escapeHtml(d.label)} — ${escapeHtml(d.region)}${d.cloned ? " (cloned)" : ""}</option>`).join("");
  const list = document.getElementById("vbList");
  const cloned = dialects.filter((d) => d.cloned);
  list.innerHTML = cloned.length
    ? "<h4>Cloned voices</h4>" + cloned.map((d) =>
        `<div class="vb-row"><span>${escapeHtml(d.label)}</span>` +
        `<button type="button" class="round-btn vb-del" data-id="${d.id}" aria-label="Delete ${escapeHtml(d.label)} voice"><svg class="ic" aria-hidden="true"><use href="#ic-trash"/></svg></button></div>`).join("")
    : "<p class='hint'>No cloned voices yet.</p>";
  list.querySelectorAll(".vb-del").forEach((b) => b.addEventListener("click", async () => {
    const key = (document.getElementById("vbKey").value || "").trim();
    if (!key) { vbStatus("Enter your admin key first.", "error"); return; }
    if (!window.confirm("Delete this cloned voice?")) return;
    try { await api("/dialects/clone", { method: "DELETE", body: { key, dialect_id: b.dataset.id } }); vbStatus("Deleted.", "ok"); loadDialects(); }
    catch (e) { vbStatus(e.message || "Delete failed.", "error"); }
  }));
}
let vbRecBlob = null, vbRec = null;
function bindVoiceBank() {
  const btn = document.getElementById("vbCreateBtn");
  if (!btn || btn.dataset.bound) return;
  btn.dataset.bound = "1";

  // In-browser recording
  const recBtn = document.getElementById("vbRecBtn"), recStop = document.getElementById("vbRecStop");
  if (recBtn) recBtn.addEventListener("click", async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const chunks = [];
      vbRec = new MediaRecorder(stream);
      vbRec.ondataavailable = (e) => { if (e.data.size) chunks.push(e.data); };
      vbRec.onstop = () => {
        stream.getTracks().forEach((t) => t.stop());
        vbRecBlob = new Blob(chunks, { type: vbRec.mimeType || "audio/webm" });
        const a = document.getElementById("vbRecAudio");
        a.src = URL.createObjectURL(vbRecBlob); a.hidden = false;
        recBtn.hidden = false; recStop.hidden = true;
        vbStatus("Recording captured — ready to create.", "ok");
      };
      vbRec.start();
      recBtn.hidden = true; recStop.hidden = false;
      vbStatus("Recording… read the script, then press stop.", "busy");
    } catch (_) { vbStatus("Microphone permission is needed to record.", "error"); }
  });
  if (recStop) recStop.addEventListener("click", () => { if (vbRec && vbRec.state !== "inactive") vbRec.stop(); });

  btn.addEventListener("click", async () => {
    const dialect = document.getElementById("vbDialect").value;
    const speaker = document.getElementById("vbSpeaker").value.trim();
    const key = document.getElementById("vbKey").value.trim();
    const consent = document.getElementById("vbConsent").checked;
    const file = document.getElementById("vbAudio").files[0];
    const sample = vbRecBlob || file;   // recorded takes precedence
    if (!key) { vbStatus("Enter your admin key.", "error"); return; }
    if (!consent) { vbStatus("Confirm the speaker consented.", "error"); return; }
    if (!sample) { vbStatus("Record or attach an audio sample.", "error"); return; }
    const fd = new FormData();
    fd.append("key", key); fd.append("dialect_id", dialect);
    fd.append("speaker", speaker); fd.append("consent", "true");
    fd.append("audio", sample, file ? file.name : "recording.webm");
    btn.disabled = true; vbStatus("Creating voice… this can take a minute.", "busy");
    try {
      const d = await api("/dialects/clone", { method: "POST", body: fd, isForm: true });
      vbStatus(d.message || "Voice created.", "ok");
      document.getElementById("vbAudio").value = "";
      vbRecBlob = null;
      const ra = document.getElementById("vbRecAudio"); if (ra) ra.hidden = true;
      loadDialects();
    } catch (e) { vbStatus(e.message || "Cloning failed.", "error"); }
    finally { btn.disabled = false; }
  });
}

async function openAccount() {
  showView("account");
  accStatus("Loading your settings…", "busy");
  Plan.init();
  bindVoiceBank();
  loadDialects();
  const profile = await loadPrefs();   // also refreshes the plan card via Billing.set
  if (profile) {
    $("#accName").value = profile.name || "";
    $("#accEmail").value = profile.email || "";
    $("#accTodoWeekday").value = profile.todo_weekday || "";
    $("#accTodoWeekend").value = profile.todo_weekend || "";
  }
  const engineRadio = document.querySelector(`input[name="engine"][value="${userPrefs.engine}"]`)
    || document.querySelector('input[name="engine"][value="azure"]');
  engineRadio.checked = true;
  try {
    await populateVoiceControls();
  } catch (e) {
    accStatus("Could not load the voice list: " + (e.message || e), "error");
  }
  $("#accRate").value = userPrefs.rate;
  $("#rateVal").textContent = Number(userPrefs.rate).toFixed(2) + "×";
  accStatus("", "");
}

$("#accountBtn").addEventListener("click", openAccount);
$("#accountBackBtn").addEventListener("click", () => showView("capture"));
document.querySelectorAll('input[name="engine"]').forEach((r) =>
  r.addEventListener("change", () => populateVoiceControls().catch(() => {})));
$("#accRate").addEventListener("input", () => {
  $("#rateVal").textContent = Number($("#accRate").value).toFixed(2) + "×";
});

$("#testVoiceBtn").addEventListener("click", async () => {
  const engine = currentEngine();
  const lang = $("#accLanguage").value;
  const voice = $("#accVoice").value;
  const rate = Number($("#accRate").value);
  const sample = sampleFor(lang);
  if (engine === "browser") {
    if (!TTS.supported) return accStatus("Your browser doesn't support speech.", "error");
    TTS.speak(sample, lang, { rate });
    accStatus("Playing a sample with your device voice.", "ok");
    return;
  }
  accStatus("Generating a sample…", "busy");
  try {
    const d = await api("/speak", { method: "POST", body: { text: sample, voiceName: voice, rate } });
    new Audio(d.audio_url).play();
    accStatus("Playing a sample.", "ok");
  } catch (e) {
    accStatus(e.message || "Could not play a sample.", "error");
  }
});

$("#accountForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const prefs = {
    engine: currentEngine(),
    language: $("#accLanguage").value,
    voice: $("#accVoice").value,
    rate: Number($("#accRate").value),
  };
  accStatus("Saving…", "busy");
  try {
    const d = await api("/profile", { method: "PUT", body: {
      name: $("#accName").value.trim(), preferences: prefs,
      todo_weekday: $("#accTodoWeekday").value, todo_weekend: $("#accTodoWeekend").value,
    } });
    userPrefs = d.preferences || prefs;
    userProfile.todo_weekday = $("#accTodoWeekday").value;
    userProfile.todo_weekend = $("#accTodoWeekend").value;
    renderMyDay();
    accStatus("Your settings have been saved.", "ok");
  } catch (err) {
    accStatus(err.message || "Could not save your settings.", "error");
  }
});

/* ----------------------------- Reader (tabs + text) ------------------------- */

// Dark mode
const themeToggle = $("#themeToggle");
function applyTheme(dark) {
  document.body.classList.toggle("dark", dark);
  if (themeToggle) {
    const use = themeToggle.querySelector("use");
    if (use) use.setAttribute("href", dark ? "#ic-sun" : "#ic-theme");
    themeToggle.setAttribute("aria-pressed", String(dark));
    themeToggle.setAttribute("aria-label", dark ? "Switch to light mode" : "Switch to dark mode");
  }
}
applyTheme(localStorage.getItem("eyewaz_theme") === "dark");
themeToggle?.addEventListener("click", () => {
  const dark = !document.body.classList.contains("dark");
  localStorage.setItem("eyewaz_theme", dark ? "dark" : "light");
  applyTheme(dark);
});

// Tab switching
function showTab(panelId) {
  document.querySelectorAll(".mode-panel").forEach((p) => (p.hidden = p.id !== panelId));
  let label = "";
  document.querySelectorAll(".tab").forEach((t) => {
    const on = t.dataset.panel === panelId;
    t.classList.toggle("is-active", on);
    t.setAttribute("aria-selected", String(on));
    if (on) label = t.textContent.trim();
  });
  if (panelId === "booksPanel") loadRecordings();   // refresh saved recordings
  if (panelId === "dayPanel") { renderMyDay(); Assistant.init(); Reminders.init(); Billing.refresh(); }  // greeting + assistant + reminders + plan
  if (label) announce(label + " selected", "ok");     // speaks when voice guidance is on
}
document.querySelectorAll(".tab").forEach((t) =>
  t.addEventListener("click", () => showTab(t.dataset.panel)));

// Inline reader controls (language / voice / speed), kept in sync with prefs.
let readerControlsReady = false;
async function initReaderControls() {
  if (readerControlsReady || !$("#rcLanguage")) return;
  let voices;
  try { voices = userPrefs.engine === "browser" ? browserVoiceList() : await getAzureVoices(); }
  catch (_) { return; }
  const byLocale = {};
  voices.forEach((v) => (byLocale[v.locale] = byLocale[v.locale] || []).push(v));
  const locales = Object.keys(byLocale).sort((a, b) =>
    (byLocale[a][0].localeName || a).localeCompare(byLocale[b][0].localeName || b));
  const langSel = $("#rcLanguage");
  langSel.innerHTML = "";
  locales.forEach((loc) => {
    const o = document.createElement("option");
    o.value = loc; o.textContent = `${byLocale[loc][0].localeName || loc} (${loc})`;
    langSel.appendChild(o);
  });
  langSel.value = byLocale[userPrefs.language] ? userPrefs.language : (locales[0] || "");
  const fillVoices = () => {
    const vs = $("#rcVoice"); vs.innerHTML = "";
    (byLocale[langSel.value] || []).forEach((v) => {
      const o = document.createElement("option");
      o.value = v.shortName; o.textContent = v.displayName + (v.gender ? " — " + v.gender : "");
      vs.appendChild(o);
    });
    if ([...vs.options].some((o) => o.value === userPrefs.voice)) vs.value = userPrefs.voice;
  };
  fillVoices();
  langSel.onchange = () => { fillVoices(); saveReaderPrefs(); };
  $("#rcVoice").onchange = saveReaderPrefs;
  $("#rcRate").value = userPrefs.rate;
  $("#rcRateVal").textContent = Number(userPrefs.rate).toFixed(2) + "×";
  $("#rcRate").oninput = () => ($("#rcRateVal").textContent = Number($("#rcRate").value).toFixed(2) + "×");
  $("#rcRate").onchange = saveReaderPrefs;
  readerControlsReady = true;
}
// On-the-go change: applies to this session only — does NOT change the saved
// account default (set that in Account). Keeps Urdu as the default on next login.
function saveReaderPrefs() {
  userPrefs = {
    engine: userPrefs.engine || "azure",
    language: $("#rcLanguage").value, voice: $("#rcVoice").value, rate: Number($("#rcRate").value),
  };
  syncDialectChips();
}

// Quick dialect switcher on the reading screen (session-only).
let _rcDialects = null;
async function initReaderDialects() {
  const wrap = $("#rcDialects"); if (!wrap) return;
  if (!_rcDialects) {
    try { _rcDialects = (await api("/dialects")).dialects || []; } catch (_) { _rcDialects = []; }
  }
  wrap.innerHTML = "";
  _rcDialects.forEach((d) => {
    const voice = (d.voices[0] && d.voices[0].shortName) || d.fallback_voice;
    const locale = d.status === "live" ? d.locale : d.fallback_locale;
    const chip = document.createElement("button");
    chip.type = "button";
    chip.className = "rc-dialect-chip";
    chip.dataset.voice = voice; chip.dataset.locale = locale;
    chip.textContent = d.label + (d.status === "live" ? "" : " ·…");
    chip.title = d.status === "live" ? d.region : d.region + " — coming soon (Urdu for now)";
    chip.addEventListener("click", () => {
      userPrefs.language = locale; userPrefs.voice = voice; userPrefs.engine = "azure";
      // reflect in the rc selects if the option exists
      const ls = $("#rcLanguage"); if (ls && [...ls.options].some((o) => o.value === locale)) { ls.value = locale; ls.onchange && ls.onchange(); }
      const vs = $("#rcVoice"); if (vs && [...vs.options].some((o) => o.value === voice)) vs.value = voice;
      announce("Reading in " + d.label + " for now.", "ok");
      syncDialectChips();
    });
    wrap.appendChild(chip);
  });
  syncDialectChips();
}
function syncDialectChips() {
  document.querySelectorAll("#rcDialects .rc-dialect-chip").forEach((c) =>
    c.classList.toggle("is-active", c.dataset.voice === userPrefs.voice));
}

// Text reader: translate to the reading language, synthesize, play + offer download.
$("#textPlayBtn")?.addEventListener("click", async () => {
  const text = $("#textInput").value.trim();
  const ts = $("#textStatus");
  if (!text) { ts.className = "status error"; ts.textContent = "Type or paste some text first."; return; }
  const btn = $("#textPlayBtn");
  btn.disabled = true; ts.className = "status busy"; ts.textContent = "Preparing your audio…";
  try {
    // Reading typed text counts as one command (it has no heavy server endpoint).
    if (!(await Billing.consumeOne())) {
      ts.className = "status error"; ts.textContent = "Monthly command limit reached — upgrade for more.";
      return;
    }
    const lang = $("#rcLanguage").value, voice = $("#rcVoice").value, rate = Number($("#rcRate").value);
    const tr = await api("/translate", { method: "POST", body: { text, to: lang } });
    const toRead = tr.translated || text;
    $("#textTrans").textContent = toRead; applyLangDir($("#textTrans"), lang); $("#textTransWrap").hidden = false;
    const sp = await api("/speak", { method: "POST", body: { text: toRead, voiceName: voice, rate } });
    const audio = $("#textAudio");
    audio.src = sp.audio_url; audio.hidden = false;
    $("#textDownload").href = sp.audio_url; $("#textDownload").hidden = false;
    $("#textSaveBtn").hidden = false;
    ts.className = "status ok"; ts.textContent = "Playing.";
    audio.play().catch(() => (ts.textContent = "Ready — press the player to listen."));
  } catch (err) {
    ts.className = "status error"; ts.textContent = err.message || "Could not read the text.";
  } finally { btn.disabled = false; }
});
$("#textStopBtn")?.addEventListener("click", () => {
  const a = $("#textAudio"); if (a) { a.pause(); a.currentTime = 0; }
});
$("#textSaveBtn")?.addEventListener("click", async () => {
  const ts = $("#textStatus");
  try {
    await saveRecording($("#textAudio").src, $("#textInput").value || "Text", $("#rcLanguage").value);
    ts.className = "status ok"; ts.textContent = "Saved on your device — find it in My Books.";
  } catch (e) { ts.className = "status error"; ts.textContent = "Could not save: " + (e.message || e); }
});

// Document reader: upload PDF / Word / EPUB / TXT -> extract -> translate -> read.
let docFile = null;
$("#docInput")?.addEventListener("change", (e) => {
  docFile = e.target.files && e.target.files[0];
  if (!docFile) return;
  $("#docName").textContent = "Selected: " + docFile.name;
  $("#docPreview").hidden = false;
  $("#docResult").hidden = true;
  $("#docStatus").textContent = "";
  $("#docReadBtn").focus();
});
$("#docSaveBtn")?.addEventListener("click", async () => {
  const st = $("#docStatus");
  try {
    await saveRecording($("#docAudio").src, docFile ? docFile.name : "Document", $("#docSaveBtn").dataset.lang || "");
    st.className = "status ok"; st.textContent = "Saved on your device — find it in My Books.";
  } catch (e) { st.className = "status error"; st.textContent = "Could not save: " + (e.message || e); }
});
$("#docReadBtn")?.addEventListener("click", async () => {
  if (!docFile) return;
  const st = $("#docStatus"), btn = $("#docReadBtn");
  btn.disabled = true; st.className = "status busy";
  st.textContent = "Extracting text, translating, and creating audio… larger files take longer.";
  try {
    const form = new FormData();
    form.append("file", docFile);
    const doc = await api("/document-translation-and-speech", { method: "POST", isForm: true, body: form });
    $("#docTrans").textContent = doc.trans_text || "";
    applyLangDir($("#docTrans"), doc.trans_lang);
    const a = $("#docAudio");
    a.src = doc.female_audio_url;
    $("#docDownload").href = doc.female_audio_url;
    $("#docDownload").hidden = false;
    $("#docSaveBtn").hidden = false;
    $("#docSaveBtn").dataset.lang = doc.trans_lang || "";
    $("#docResult").hidden = false;
    st.className = "status ok"; st.textContent = "Done.";
    a.play().catch(() => {});
    loadLibrary();
  } catch (err) {
    st.className = "status error";
    st.textContent = err.message || "Could not read that file.";
  } finally {
    btn.disabled = false;
  }
});

/* --------------------------------- Boot ------------------------------------- */

function enterApp() {
  showView("capture");
  loadLibrary();
  loadPrefs().then(() => { initReaderControls(); initReaderDialects(); renderMyDay(); Assistant.init(); Reminders.init(); checkoutReturn(); });
}

// React to a return from Stripe Checkout (?checkout=success|cancel).
function checkoutReturn() {
  const params = new URLSearchParams(window.location.search);
  const c = params.get("checkout");
  if (!c) return;
  history.replaceState({}, "", "/app");
  if (c === "success") {
    announce("Thank you! Your payment is being confirmed. Your plan will update shortly.", "ok");
    setTimeout(() => Billing.refresh(), 4000);   // give the webhook a moment
  } else {
    announce("Checkout was cancelled. You can upgrade any time from Account.", "");
  }
}

// Handle the return from a social sign-in redirect (/app#token=... or #auth_error=...).
function handleAuthRedirect() {
  const hash = window.location.hash.slice(1);
  if (!hash) return false;
  const params = new URLSearchParams(hash);
  const token = params.get("token");
  const err = params.get("auth_error");
  // Clean the URL so the token/error isn't left in the address bar.
  history.replaceState(null, "", window.location.pathname);
  if (token) {
    setToken(token);
    return true;
  }
  if (err) {
    const msgs = {
      google_not_configured: "Google sign-in isn't set up yet. Use email, or add Google credentials.",
      facebook_not_configured: "Facebook sign-in isn't set up yet. Use email, or add Facebook credentials.",
      apple_not_configured: "Apple sign-in isn't set up yet. Use email for now.",
      cancelled: "Sign-in was cancelled.",
      no_email: "That account didn't share an email address.",
    };
    showView("auth");
    showAuthForm("login");
    showAuthError(msgs[err] || "Could not sign in with that provider.");
    return false;
  }
  return false;
}

// Grey out social buttons whose provider isn't configured on the server.
async function annotateProviders() {
  try {
    const cfg = await api("/auth/providers", { auth: false });
    document.querySelectorAll(".social-btn").forEach((btn) => {
      if (cfg && cfg[btn.dataset.provider] === false) {
        btn.title = "Not set up yet — uses email instead";
        btn.querySelector("span:last-child").textContent += " (setup needed)";
      }
    });
  } catch (_) { /* best effort */ }
}

if (handleAuthRedirect() || getToken()) {
  enterApp();
} else {
  showView("auth");
  annotateProviders();
}

/* PWA: register the service worker for install + offline app shell. */
if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/app/sw.js", { scope: "/app/" }).catch(() => {});
  });
}
