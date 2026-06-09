/* Offscreen audio player. Owns the <audio> element the service worker can't. */
const player = document.getElementById("player");

chrome.runtime.onMessage.addListener((msg) => {
  if (!msg || msg.target !== "offscreen") return;
  if (msg.type === "PLAY") {
    try {
      player.pause();
      player.src = msg.dataUrl;
      player.play().catch(() => {});
    } catch (_) {}
  } else if (msg.type === "STOP") {
    try { player.pause(); player.currentTime = 0; } catch (_) {}
  }
});
