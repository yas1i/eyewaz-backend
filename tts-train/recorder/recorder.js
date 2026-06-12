/* EYEWAZ voice recorder — records each script line to <folder>/NNNN.wav and
   writes metadata.csv (NNNN|sentence), the exact input prepare_dataset.py wants.
   Chrome/Edge only (uses the File System Access API). Pure client-side. */
(() => {
  let S = (window.EYEWAZ_SENTENCES || []).slice();
  const $ = (id) => document.getElementById(id);
  const pad = (n) => String(n).padStart(4, "0");
  const isRTL = (t) => /[؀-ۿݐ-ݿ]/.test(t);
  const slug = (s) => (s || "").trim().toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");

  let meta = { dialect: "urdu", gender: "male", speaker: "" };
  let uploadCfg = { url: "", key: "", contributor: "" };
  let dirHandle = null;
  let idx = 0;
  const done = new Set();

  // audio capture state
  let audioCtx = null, stream = null, source = null, processor = null;
  let chunks = [], recRate = 44100, recording = false;
  let lastFloat = null, lastBlob = null, lastUrl = null;

  const fsaOK = !!window.showDirectoryPicker;
  if (!fsaOK) {
    $("folderHint").innerHTML =
      "This browser can't save to a folder — no problem: fill in the Server URL above and use " +
      "<b>Record online only</b>. Every clip goes straight to the voice bank.";
  }

  // ---------- setup: dialect / speaker / consent / custom script ----------
  function suggestedName() {
    const sp = slug($("speakerName").value) || "speaker";
    return `dataset-${meta.dialect}-${meta.gender}-${sp}`;
  }
  function refreshSetup() {
    meta.dialect = $("dialect").value;
    meta.gender = $("gender").value;
    meta.speaker = $("speakerName").value.trim();
    if ($("srvUrl")) {
      uploadCfg.url = $("srvUrl").value.trim();
      uploadCfg.contributor = $("contrib") ? $("contrib").value.trim() : "";
      uploadCfg.key = $("srvKey") ? $("srvKey").value.trim() : "";
    }
    $("suggestName").textContent = "Suggested folder: " + suggestedName();
    const ready = $("consent").checked && meta.speaker.length > 0;
    $("pickBtn").disabled = !(fsaOK && ready);
    if ($("onlineBtn")) $("onlineBtn").disabled = !(ready && uploadCfg.url);
  }
  ["dialect", "gender", "speakerName", "consent", "srvUrl", "contrib", "srvKey"].forEach((id) =>
    $(id) && $(id).addEventListener("input", refreshSetup));

  $("scriptFile").addEventListener("change", async (e) => {
    const f = e.target.files[0]; if (!f) return;
    const txt = await f.text();
    const lines = txt.split(/\r?\n/).map((l) => l.trim()).filter((l) => l && !l.startsWith("#"));
    if (lines.length) {
      S = lines;
      $("scriptInfo").textContent = `Loaded ${lines.length} lines from ${f.name}.`;
    }
  });
  refreshSetup();

  // ---------- folder ----------
  $("pickBtn").addEventListener("click", async () => {
    try {
      dirHandle = await window.showDirectoryPicker({ mode: "readwrite" });
    } catch (_) { return; }
    if ((await dirHandle.requestPermission({ mode: "readwrite" })) !== "granted") {
      alert("Folder write permission is needed."); return;
    }
    await writeSpeakerInfo();
    await ensureMetadata();
    await scanExisting();
    $("setup").hidden = true;
    $("rec").hidden = false;
    $("folderName").textContent = `Folder: ${dirHandle.name} · ${meta.dialect}/${meta.gender} · ${meta.speaker}`;
    idx = firstUnrecorded();
    render();
  });

  // ---------- online-only mode (phones / any browser; no local folder) ----------
  $("onlineBtn") && $("onlineBtn").addEventListener("click", async () => {
    refreshSetup();
    if (!uploadCfg.url) { alert("Enter the Server URL under 'Upload to EYEWAZ server' first."); return; }
    dirHandle = null;
    done.clear();
    // Resume: ask the server which lines this speaker already uploaded.
    try {
      const u = new URL(uploadCfg.url.replace(/\/+$/, "") + "/api/voicebank/done");
      u.searchParams.set("lang", meta.dialect);
      u.searchParams.set("speaker", slug(meta.speaker));
      if (uploadCfg.key) u.searchParams.set("key", uploadCfg.key);
      const r = await fetch(u);
      if (r.ok) {
        const d = await r.json();
        (d.ids || []).forEach((sid) => {
          const i = parseInt(sid, 10) - 1;
          if (i >= 0 && i < S.length) done.add(i);
        });
      }
    } catch (_) { /* offline check failed — start from the top, uploads still dedupe */ }
    $("setup").hidden = true;
    $("rec").hidden = false;
    $("folderName").textContent = `Online: ${meta.dialect}/${meta.gender} · ${meta.speaker}`;
    idx = firstUnrecorded();
    render();
  });

  async function writeSpeakerInfo() {
    // Record who/what this dataset is, for the voice bank (consent is required
    // to reach here). prepare_dataset.py ignores this file.
    const info = {
      dialect: meta.dialect, gender: meta.gender, speaker: meta.speaker,
      consent: true, lines: S.length, created: new Date().toISOString(),
    };
    try {
      const fh = await dirHandle.getFileHandle("speaker.json", { create: true });
      const w = await fh.createWritable();
      await w.write(JSON.stringify(info, null, 2)); await w.close();
    } catch (_) {}
  }

  async function ensureMetadata() {
    // Write metadata.csv with ALL lines once (prepare_dataset skips missing wavs).
    try { await dirHandle.getFileHandle("metadata.csv"); return; } catch (_) {}
    const body = S.map((t, i) => `${pad(i + 1)}|${t}`).join("\n") + "\n";
    const fh = await dirHandle.getFileHandle("metadata.csv", { create: true });
    const w = await fh.createWritable(); await w.write(body); await w.close();
  }

  async function scanExisting() {
    done.clear();
    for await (const [name] of dirHandle.entries()) {
      const m = name.match(/^(\d{4})\.wav$/);
      if (m) { const i = parseInt(m[1], 10) - 1; if (i >= 0 && i < S.length) done.add(i); }
    }
  }

  const firstUnrecorded = () => { for (let i = 0; i < S.length; i++) if (!done.has(i)) return i; return 0; };

  // ---------- recording ----------
  async function startRec() {
    if (recording) return;
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        audio: { channelCount: 1, echoCancellation: false, noiseSuppression: false, autoGainControl: false },
      });
    } catch (e) { setStatus("Microphone blocked. Allow mic access and retry.", "err"); return; }
    audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    recRate = audioCtx.sampleRate;
    source = audioCtx.createMediaStreamSource(stream);
    processor = audioCtx.createScriptProcessor(4096, 1, 1);
    chunks = [];
    processor.onaudioprocess = (e) => {
      const ch = e.inputBuffer.getChannelData(0);
      chunks.push(new Float32Array(ch));
      let peak = 0; for (let i = 0; i < ch.length; i += 32) peak = Math.max(peak, Math.abs(ch[i]));
      $("meterBar").style.width = Math.min(100, peak * 140) + "%";
    };
    source.connect(processor); processor.connect(audioCtx.destination);
    recording = true;
    const b = $("recBtn"); b.textContent = "■ Stop"; b.classList.add("is-rec");
    setStatus("Recording… read the line, then Stop.", "warn");
  }

  async function stopRec() {
    if (!recording) return;
    recording = false;
    try { processor.disconnect(); source.disconnect(); } catch (_) {}
    if (stream) stream.getTracks().forEach((t) => t.stop());
    if (audioCtx) await audioCtx.close();
    $("meterBar").style.width = "0%";
    const b = $("recBtn"); b.textContent = "● Record"; b.classList.remove("is-rec");

    let len = 0; chunks.forEach((c) => (len += c.length));
    const flat = new Float32Array(len); let o = 0;
    chunks.forEach((c) => { flat.set(c, o); o += c.length; });
    lastFloat = flat;
    lastBlob = new Blob([encodeWAV(flat, recRate)], { type: "audio/wav" });
    if (lastUrl) URL.revokeObjectURL(lastUrl);
    lastUrl = URL.createObjectURL(lastBlob);
    const a = $("audio"); a.src = lastUrl; a.hidden = false;
    $("playBtn").disabled = false; $("saveBtn").disabled = false; $("reRecBtn").disabled = false;
    const secs = (len / recRate).toFixed(1);
    setStatus(`Recorded ${secs}s. Play to check, then Save & next.` +
      (secs < 0.6 ? "  (a bit short)" : secs > 13 ? "  (a bit long)" : ""),
      (secs < 0.6 || secs > 13) ? "warn" : "ok");
  }

  function encodeWAV(float32, rate) {
    const n = float32.length;
    const buf = new ArrayBuffer(44 + n * 2);
    const v = new DataView(buf);
    const ws = (off, s) => { for (let i = 0; i < s.length; i++) v.setUint8(off + i, s.charCodeAt(i)); };
    ws(0, "RIFF"); v.setUint32(4, 36 + n * 2, true); ws(8, "WAVE");
    ws(12, "fmt "); v.setUint32(16, 16, true); v.setUint16(20, 1, true); v.setUint16(22, 1, true);
    v.setUint32(24, rate, true); v.setUint32(28, rate * 2, true); v.setUint16(32, 2, true); v.setUint16(34, 16, true);
    ws(36, "data"); v.setUint32(40, n * 2, true);
    let off = 44;
    for (let i = 0; i < n; i++) { let s = Math.max(-1, Math.min(1, float32[i])); v.setInt16(off, s * 0x7fff, true); off += 2; }
    return buf;
  }

  async function save() {
    if (!lastBlob) return;
    const curIdx = idx, id = pad(curIdx + 1), text = S[curIdx], blob = lastBlob;

    // Online-only mode: the upload IS the save — only advance once it lands.
    if (!dirHandle) {
      setStatus("Uploading " + id + "...", "warn");
      try { await uploadClip(id, text, blob); }
      catch (e) { setStatus("Upload failed: " + e.message + " — check your connection and press Save again.", "err"); return; }
      done.add(curIdx);
      clearTake();
      setStatus("Uploaded " + id + " to the voice bank", "ok");
      idx = (curIdx + 1 < S.length) ? curIdx + 1 : curIdx;
      render();
      return;
    }

    // Folder mode: save locally first, then best-effort upload.
    try {
      const fh = await dirHandle.getFileHandle(id + ".wav", { create: true });
      const w = await fh.createWritable(); await w.write(blob); await w.close();
    } catch (e) { setStatus("Could not write file: " + e.message, "err"); return; }
    done.add(curIdx);
    clearTake();
    setStatus("Saved " + id + ".wav", "ok");
    idx = (curIdx + 1 < S.length) ? curIdx + 1 : curIdx;
    render();
    if (uploadCfg.url) {
      try { await uploadClip(id, text, blob); setStatus(`Saved ${id}.wav — saved and uploaded`, "ok"); }
      catch (e) { setStatus(`Saved ${id}.wav (upload failed: ${e.message})`, "warn"); }
    }
  }

  async function uploadClip(id, text, blob) {
    const fd = new FormData();
    fd.append("audio", blob, id + ".wav");
    fd.append("lang", meta.dialect);
    fd.append("speaker", meta.speaker);
    fd.append("gender", meta.gender);
    fd.append("sentence_id", id);
    fd.append("transcript", text);
    fd.append("consent", "true");
    if (uploadCfg.contributor) fd.append("contributor", uploadCfg.contributor);
    if (uploadCfg.key) fd.append("key", uploadCfg.key);
    const r = await fetch(uploadCfg.url.replace(/\/+$/, "") + "/api/voicebank/clip",
      { method: "POST", body: fd });
    if (!r.ok) throw new Error("HTTP " + r.status);
  }

  function clearTake() {
    lastFloat = lastBlob = null;
    if (lastUrl) { URL.revokeObjectURL(lastUrl); lastUrl = null; }
    $("audio").hidden = true; $("audio").src = "";
    $("playBtn").disabled = true; $("saveBtn").disabled = true; $("reRecBtn").disabled = true;
  }

  // ---------- navigation / render ----------
  function go(i) { if (recording) return; idx = Math.max(0, Math.min(S.length - 1, i)); clearTake(); render(); }

  function render() {
    const t = S[idx];
    const el = $("sentence");
    el.textContent = t; el.dir = isRTL(t) ? "rtl" : "ltr";
    $("counter").textContent = `Line ${idx + 1} of ${S.length}` + (done.has(idx) ? "  · recorded ✓" : "");
    const c = done.size;
    $("hdrProgress").textContent = `${c} / ${S.length} recorded`;
    if (!lastBlob) setStatus(done.has(idx) ? "Already recorded — re-record to replace, or skip." : "Press Record (or Space).",
      done.has(idx) ? "done" : "");
    renderList();
  }

  function renderList() {
    const box = $("list"); box.innerHTML = "";
    S.forEach((t, i) => {
      const d = document.createElement("div");
      if (i === idx) d.className = "cur";
      d.innerHTML = `<span class="id">${pad(i + 1)}</span>` +
        `<span style="flex:1">${(done.has(i) ? "✓ " : "")}${escapeHtml(t)}</span>`;
      d.addEventListener("click", () => go(i));
      box.appendChild(d);
    });
    const cur = box.querySelector(".cur"); if (cur) cur.scrollIntoView({ block: "nearest" });
  }

  const escapeHtml = (s) => s.replace(/[&<>]/g, (m) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[m]));
  function setStatus(msg, kind) { const s = $("status"); s.textContent = msg || ""; s.className = "status " + (kind || ""); }

  // ---------- buttons ----------
  $("recBtn").addEventListener("click", () => (recording ? stopRec() : startRec()));
  $("playBtn").addEventListener("click", () => $("audio").play());
  $("saveBtn").addEventListener("click", save);
  $("reRecBtn").addEventListener("click", () => { clearTake(); startRec(); });
  $("prevBtn").addEventListener("click", () => go(idx - 1));
  $("nextBtn").addEventListener("click", () => go(idx + 1));

  // ---------- keyboard ----------
  document.addEventListener("keydown", (e) => {
    if ($("rec").hidden) return;
    if (["INPUT", "SELECT", "TEXTAREA"].includes(document.activeElement.tagName)) return;
    if (e.code === "Space") { e.preventDefault(); recording ? stopRec() : startRec(); }
    else if (e.key === "p" || e.key === "P") { if (!$("playBtn").disabled) $("audio").play(); }
    else if (e.key === "Enter") { if (!$("saveBtn").disabled) save(); }
    else if (e.key === "r" || e.key === "R") { if (!$("reRecBtn").disabled) { clearTake(); startRec(); } }
    else if (e.key === "ArrowRight") go(idx + 1);
    else if (e.key === "ArrowLeft") go(idx - 1);
  });

  if (!S.length) $("folderHint").textContent = "No sentences loaded (sentences.js missing).";
})();
