const DEFAULTS = { ttsUrl: "http://167.233.35.30:8090", apiKey: "", speed: 1.0 };
const $ = (id) => document.getElementById(id);

function setStatus(msg, kind) {
  const s = $("status");
  s.textContent = msg || "";
  s.className = kind || "";
}

async function load() {
  const cfg = await chrome.storage.sync.get(DEFAULTS);
  $("ttsUrl").value = cfg.ttsUrl;
  $("apiKey").value = cfg.apiKey;
  $("speed").value = cfg.speed;
  $("speedVal").textContent = Number(cfg.speed).toFixed(1) + "×";
}

function save() {
  const cfg = {
    ttsUrl: $("ttsUrl").value.trim() || DEFAULTS.ttsUrl,
    apiKey: $("apiKey").value,
    speed: Number($("speed").value),
  };
  chrome.storage.sync.set(cfg);
  return cfg;
}

$("speed").addEventListener("input", () => {
  $("speedVal").textContent = Number($("speed").value).toFixed(1) + "×";
  save();
});
$("ttsUrl").addEventListener("change", save);
$("apiKey").addEventListener("change", save);

$("readBtn").addEventListener("click", () => {
  save();
  setStatus("Reading…", "ok");
  chrome.runtime.sendMessage({ type: "EYEWAZ_SPEAK_ACTIVE" }, (res) => {
    if (chrome.runtime.lastError) { setStatus("Could not reach the page.", "err"); return; }
    if (res && res.ok) setStatus("Playing.", "ok");
    else setStatus((res && res.error) || "Nothing to read.", "err");
  });
});

$("stopBtn").addEventListener("click", () => {
  chrome.runtime.sendMessage({ type: "EYEWAZ_STOP" });
  setStatus("Stopped.", "");
});

load();
