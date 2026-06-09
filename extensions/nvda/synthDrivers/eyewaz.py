# -*- coding: utf-8 -*-
# EYEWAZ Urdu synthesizer for NVDA.
#
# Routes NVDA's speech through the EYEWAZ self-hosted TTS service (POST /tts),
# so every spoken word on Windows — any app, any screen — comes out in Urdu.
# A background thread does the HTTP synthesis and streams the WAV to NVDA's
# audio player, so the UI never blocks.
#
# Config: edit eyewaz.json in this add-on's folder (TTS_URL + API_KEY), or the
# defaults below. URL points at your service, e.g. http://167.233.35.30:8090.

import os
import json
import threading
import queue
import wave
import io
import audioop
import urllib.request
import urllib.error

import config
import nvwave
from synthDriverHandler import SynthDriver, VoiceInfo, synthIndexReached, synthDoneSpeaking
from speech.commands import IndexCommand, CharacterModeCommand, BreakCommand
from logHandler import log

# ---- Configuration --------------------------------------------------------
_DEFAULTS = {"TTS_URL": "http://167.233.35.30:8090", "API_KEY": "", "TIMEOUT": 30}


def _load_config():
    cfg = dict(_DEFAULTS)
    here = os.path.dirname(__file__)
    for path in (
        os.path.join(here, "..", "eyewaz.json"),   # add-on root
        os.path.join(here, "eyewaz.json"),
    ):
        try:
            with open(os.path.abspath(path), "r", encoding="utf-8") as fh:
                cfg.update(json.load(fh))
                break
        except Exception:
            pass
    return cfg


CFG = _load_config()


def _rate_to_speed(rate):
    """NVDA rate 0..100 -> TTS speed 0.5..2.0 (50 == 1.0x)."""
    return round(0.5 + (rate / 100.0) * 1.5, 2)


# ---- A unit of work for the background synth thread -----------------------
class _Job(object):
    __slots__ = ("text", "index")

    def __init__(self, text, index):
        self.text = text
        self.index = index   # int index to report after this chunk, or None


class SynthDriver(SynthDriver):
    name = "eyewaz"
    description = _("EYEWAZ Urdu")

    supportedSettings = (
        SynthDriver.RateSetting(),
        SynthDriver.VolumeSetting(),
    )
    supportedCommands = {IndexCommand, CharacterModeCommand, BreakCommand}
    supportedNotifications = {synthIndexReached, synthDoneSpeaking}

    @classmethod
    def check(cls):
        # Always selectable; reachability is verified at speak time so a brief
        # network blip doesn't hide the synth.
        return True

    def __init__(self):
        super(SynthDriver, self).__init__()
        self._rate = 50
        self._volume = 100
        self._queue = queue.Queue()
        self._player = None
        self._stop = threading.Event()      # cancel current speech
        self._terminate = threading.Event()
        self._worker = threading.Thread(target=self._run, name="EYEWAZ TTS")
        self._worker.daemon = True
        self._worker.start()

    # ---- NVDA speech entry points ----
    def speak(self, speechSequence):
        pendingIndex = None
        for item in speechSequence:
            if isinstance(item, str):
                text = item.strip()
                if text:
                    self._queue.put(_Job(text, pendingIndex))
                    pendingIndex = None
            elif isinstance(item, IndexCommand):
                pendingIndex = item.index
            # CharacterModeCommand / BreakCommand: nothing special for MVP.
        # trailing index with no text after it
        if pendingIndex is not None:
            self._queue.put(_Job("", pendingIndex))
        # marker so the worker knows the utterance is finished
        self._queue.put(None)

    def cancel(self):
        # Drop everything queued and stop the current clip immediately.
        self._stop.set()
        try:
            while True:
                self._queue.get_nowait()
        except queue.Empty:
            pass
        if self._player:
            try:
                self._player.stop()
            except Exception:
                pass
        self._stop.clear()

    def pause(self, switch):
        if self._player:
            try:
                self._player.pause(switch)
            except Exception:
                pass

    def terminate(self):
        self._terminate.set()
        self._queue.put(None)
        try:
            self._worker.join(2)
        except Exception:
            pass
        if self._player:
            try:
                self._player.close()
            except Exception:
                pass

    # ---- Settings ----
    def _get_rate(self):
        return self._rate

    def _set_rate(self, value):
        self._rate = max(0, min(100, int(value)))

    def _get_volume(self):
        return self._volume

    def _set_volume(self, value):
        self._volume = max(0, min(100, int(value)))

    # ---- Background worker ----
    def _run(self):
        while not self._terminate.is_set():
            job = self._queue.get()
            if self._terminate.is_set():
                break
            if job is None:
                # end of an utterance
                synthDoneSpeaking.notify(synth=self)
                continue
            if self._stop.is_set():
                continue
            try:
                if job.text:
                    audio, params = self._synthesize(job.text)
                    if audio and not self._stop.is_set():
                        self._play(audio, params)
            except Exception as e:
                log.error("EYEWAZ TTS error: %s" % e)
            if job.index is not None and not self._stop.is_set():
                synthIndexReached.notify(synth=self, index=job.index)

    def _synthesize(self, text):
        body = json.dumps({"text": text, "speed": _rate_to_speed(self._rate)}).encode("utf-8")
        req = urllib.request.Request(
            CFG["TTS_URL"].rstrip("/") + "/tts",
            data=body,
            headers={"Content-Type": "application/json"},
        )
        if CFG.get("API_KEY"):
            req.add_header("X-API-Key", CFG["API_KEY"])
        with urllib.request.urlopen(req, timeout=CFG.get("TIMEOUT", 30)) as resp:
            raw = resp.read()
        wf = wave.open(io.BytesIO(raw), "rb")
        params = (wf.getnchannels(), wf.getframerate(), wf.getsampwidth())
        frames = wf.readframes(wf.getnframes())
        wf.close()
        if self._volume < 100 and params[2] == 2:
            frames = audioop.mul(frames, 2, self._volume / 100.0)
        return frames, params

    def _ensure_player(self, channels, rate, sampwidth):
        bits = sampwidth * 8
        if (self._player and getattr(self._player, "channels", None) == channels
                and getattr(self._player, "samplesPerSec", None) == rate):
            return
        if self._player:
            try:
                self._player.close()
            except Exception:
                pass
        try:
            self._player = nvwave.WavePlayer(
                channels=channels, samplesPerSec=rate, bitsPerSample=bits,
                outputDevice=config.conf["speech"]["outputDevice"],
            )
        except TypeError:
            # Older NVDA signature without keyword outputDevice.
            self._player = nvwave.WavePlayer(channels, rate, bits,
                                             config.conf["speech"]["outputDevice"])

    def _play(self, frames, params):
        channels, rate, sampwidth = params
        self._ensure_player(channels, rate, sampwidth)
        # Feed in small blocks so cancel() responds quickly.
        block = rate * channels * sampwidth // 4  # ~0.25s
        for i in range(0, len(frames), block):
            if self._stop.is_set():
                return
            self._player.feed(frames[i:i + block])
        try:
            self._player.idle()
        except Exception:
            pass
