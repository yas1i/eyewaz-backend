# EYEWAZ Urdu voice for NVDA
# A fully offline Urdu speech synthesizer driver. Synthesis runs on the user's
# own machine with a bundled Piper neural voice (piper.exe), so NVDA speaks Urdu
# with no internet connection and no per character cost.
#
# Author: Yasir Musawar (WAJD AI). https://www.eyewaz.com
#
# The trained voice models and the Piper runtime are not shipped in source
# control. The add-on package places them under:
#   synthDrivers/eyewaz/runtime/piper.exe   (+ its DLLs and espeak-ng-data)
#   synthDrivers/eyewaz/voices/*.onnx       (+ matching *.onnx.json)
# See the add-on readme for how to drop them in.

import os
import json
import threading
import subprocess
from collections import OrderedDict

try:
    import audioop  # standard library on NVDA's Python; used for volume scaling
except Exception:  # pragma: no cover - audioop removed in some future runtimes
    audioop = None

import config
import nvwave
import synthDriverHandler
from synthDriverHandler import (
    SynthDriver as _SynthDriverBase,
    VoiceInfo,
    synthIndexReached,
    synthDoneSpeaking,
)
from speech.commands import IndexCommand, BreakCommand
from logHandler import log

try:
    import queue
except ImportError:  # pragma: no cover
    import Queue as queue  # type: ignore

# Hide the piper console window on Windows.
_CREATE_NO_WINDOW = 0x08000000

_HERE = os.path.dirname(os.path.abspath(__file__))
_PKG = os.path.join(_HERE, "eyewaz")
_RUNTIME_DIR = os.path.join(_PKG, "runtime")
_VOICES_DIR = os.path.join(_PKG, "voices")

_SENTINEL = object()

# Voice file names look like eyewaz-<language>-<gender>. Map the language word to
# the BCP 47 code NVDA expects. Languages espeak-ng does not cover (Saraiki,
# Balochi, Kashmiri, Hindko) are trained via the close Urdu phonemizer, so they
# report "ur" here. Extend this as espeak-ng coverage grows.
_LANG_MAP = {
    "urdu": "ur", "punjabi": "pa", "sindhi": "sd", "pashto": "ps",
    "bengali": "bn", "english": "en",
    "saraiki": "ur", "balochi": "ur", "kashmiri": "ur", "hindko": "ur",
}


def _voice_language(voice_id):
    for token in voice_id.lower().replace("_", "-").split("-"):
        if token in _LANG_MAP:
            return _LANG_MAP[token]
    return "ur"


def _find_piper():
    """Return the path to the bundled piper executable, or None."""
    for name in ("piper.exe", "piper"):
        p = os.path.join(_RUNTIME_DIR, name)
        if os.path.isfile(p):
            return p
    return None


def _pretty_name(file_stem):
    """Turn a model file stem into a readable voice name.

    eyewaz-urdu-female -> EYEWAZ Urdu Female
    """
    parts = file_stem.replace("_", "-").split("-")
    words = []
    for part in parts:
        if not part:
            continue
        words.append("EYEWAZ" if part.lower() == "eyewaz" else part.capitalize())
    return " ".join(words) or file_stem


def _list_voices():
    """Discover installed Piper voices: {id: {name, model, config, rate}}."""
    voices = OrderedDict()
    if not os.path.isdir(_VOICES_DIR):
        return voices
    for fn in sorted(os.listdir(_VOICES_DIR)):
        if not fn.lower().endswith(".onnx"):
            continue
        model = os.path.join(_VOICES_DIR, fn)
        cfg = model + ".json"
        if not os.path.isfile(cfg):
            alt = os.path.splitext(model)[0] + ".json"
            cfg = alt if os.path.isfile(alt) else None
        rate = 22050
        if cfg:
            try:
                with open(cfg, encoding="utf-8") as fh:
                    data = json.load(fh)
                rate = int(data.get("audio", {}).get("sample_rate", rate))
            except Exception:
                pass
        vid = os.path.splitext(fn)[0]
        voices[vid] = {
            "name": _pretty_name(vid),
            "model": model,
            "config": cfg or "",
            "rate": rate,
            "lang": _voice_language(vid),
        }
    return voices


class SynthDriver(_SynthDriverBase):
    name = "eyewaz"
    description = "EYEWAZ Urdu"

    supportedSettings = (
        _SynthDriverBase.VoiceSetting(),
        _SynthDriverBase.RateSetting(),
        _SynthDriverBase.VolumeSetting(),
    )
    supportedCommands = {IndexCommand, BreakCommand}
    supportedNotifications = {synthIndexReached, synthDoneSpeaking}

    @classmethod
    def check(cls):
        # Only offer the driver once the runtime and at least one voice exist.
        return bool(_find_piper()) and bool(_list_voices())

    def __init__(self):
        super().__init__()
        self._piper = _find_piper()
        self._voices = _list_voices()
        if not self._piper or not self._voices:
            raise RuntimeError("EYEWAZ voice runtime or models not installed")

        self._rate = 50
        self._volume = 100
        # Prefer a female voice by default if one is present.
        self._voice = next(
            (v for v in self._voices if "female" in v.lower()),
            next(iter(self._voices)),
        )

        self._player = None
        self._playerRate = None
        self._proc = None
        self._token = 0  # bumped on cancel to abort in-flight speech
        self._lock = threading.Lock()
        self._queue = queue.Queue()
        self._thread = threading.Thread(
            target=self._bgLoop, name="EyewazSynth", daemon=True
        )
        self._thread.start()

    def terminate(self):
        self._queue.put(_SENTINEL)
        self._kill_proc()
        try:
            self._thread.join(2)
        except Exception:
            pass
        if self._player:
            try:
                self._player.close()
            except Exception:
                pass
            self._player = None

    # ----- speech -----------------------------------------------------------

    def speak(self, speechSequence):
        self._queue.put((self._token, list(speechSequence)))

    def cancel(self):
        with self._lock:
            self._token += 1
        # Drop anything still queued.
        try:
            while True:
                self._queue.get_nowait()
                self._queue.task_done()
        except queue.Empty:
            pass
        self._kill_proc()
        if self._player:
            try:
                self._player.stop()
            except Exception:
                pass

    def pause(self, switch):
        if self._player:
            try:
                self._player.pause(switch)
            except Exception:
                pass

    # ----- background worker ------------------------------------------------

    def _bgLoop(self):
        while True:
            item = self._queue.get()
            if item is _SENTINEL:
                break
            startToken, seq = item
            try:
                if startToken == self._token:
                    self._process(seq, startToken)
            except Exception:
                log.error("EYEWAZ synthesis failed", exc_info=True)
            finally:
                self._queue.task_done()
            if startToken == self._token:
                synthDoneSpeaking.notify(synth=self)

    def _process(self, seq, token):
        parts = []
        for item in seq:
            if token != self._token:
                return
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, IndexCommand):
                self._flush(parts, token)
                parts = []
                self._emitIndex(item.index, token)
            elif isinstance(item, BreakCommand):
                self._flush(parts, token)
                parts = []
                self._emitSilence(item.time, token)
            # Other commands (pitch, character mode, etc.) are ignored for now.
        self._flush(parts, token)
        if token == self._token and self._player:
            try:
                self._player.idle()
            except Exception:
                pass

    def _flush(self, parts, token):
        text = " ".join(p for p in parts if p).strip()
        if text and token == self._token:
            self._synthAndFeed(text, token)

    def _emitIndex(self, index, token):
        if token != self._token or not self._player:
            return
        try:
            self._player.feed(
                b"\0\0",
                onDone=lambda i=index: synthIndexReached.notify(synth=self, index=i),
            )
        except Exception:
            # Older WavePlayer without onDone: notify immediately as a fallback.
            synthIndexReached.notify(synth=self, index=index)

    def _emitSilence(self, ms, token):
        if token != self._token or not self._player or not ms:
            return
        frames = int(self._playerRate * ms / 1000)
        if frames > 0:
            try:
                self._player.feed(b"\0\0" * frames)
            except Exception:
                pass

    # ----- synthesis --------------------------------------------------------

    def _ensurePlayer(self, rate):
        if self._player is not None and self._playerRate == rate:
            return
        if self._player is not None:
            try:
                self._player.close()
            except Exception:
                pass
        kwargs = dict(channels=1, samplesPerSec=rate, bitsPerSample=16)
        dev = self._outputDevice()
        if dev is not None:
            kwargs["outputDevice"] = dev
        self._player = nvwave.WavePlayer(**kwargs)
        self._playerRate = rate

    @staticmethod
    def _outputDevice():
        for section in ("audio", "speech"):
            try:
                return config.conf[section]["outputDevice"]
            except Exception:
                continue
        return None

    def _lengthScale(self):
        # NVDA rate 0..100 -> Piper length scale 2.0 (slow) .. 0.5 (fast).
        return 2.0 - (max(0, min(100, self._rate)) / 100.0) * 1.5

    def _synthAndFeed(self, text, token):
        voice = self._voices[self._voice]
        self._ensurePlayer(voice["rate"])

        args = [
            self._piper,
            "--model", voice["model"],
            "--output_raw",
            "--length_scale", "%.3f" % self._lengthScale(),
        ]
        if voice["config"]:
            args += ["--config", voice["config"]]

        startupinfo = None
        creationflags = 0
        if os.name == "nt":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            creationflags = _CREATE_NO_WINDOW

        try:
            proc = subprocess.Popen(
                args,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                cwd=_RUNTIME_DIR,  # so piper finds its DLLs + espeak-ng-data
                startupinfo=startupinfo,
                creationflags=creationflags,
            )
        except Exception:
            log.error("EYEWAZ: could not start piper", exc_info=True)
            return
        self._proc = proc

        try:
            proc.stdin.write(text.encode("utf-8"))
            proc.stdin.close()
        except Exception:
            pass

        vol = max(0.0, min(1.0, self._volume / 100.0))
        try:
            while True:
                if token != self._token:
                    return
                data = proc.stdout.read(8192)
                if not data:
                    break
                if audioop is not None and vol < 1.0:
                    try:
                        data = audioop.mul(data, 2, vol)
                    except Exception:
                        pass
                if token != self._token:
                    return
                try:
                    self._player.feed(data)
                except Exception:
                    pass
        finally:
            if token != self._token:
                self._kill_proc(proc)
            else:
                try:
                    proc.wait(timeout=2)
                except Exception:
                    self._kill_proc(proc)

    def _kill_proc(self, proc=None):
        proc = proc or self._proc
        if proc is not None and proc.poll() is None:
            try:
                proc.kill()
            except Exception:
                pass

    # ----- settings ---------------------------------------------------------

    def _get_rate(self):
        return self._rate

    def _set_rate(self, value):
        self._rate = max(0, min(100, int(value)))

    def _get_volume(self):
        return self._volume

    def _set_volume(self, value):
        self._volume = max(0, min(100, int(value)))

    def _get_voice(self):
        return self._voice

    def _set_voice(self, value):
        if value in self._voices:
            self._voice = value

    def _getAvailableVoices(self):
        out = OrderedDict()
        for vid, info in self._voices.items():
            out[vid] = VoiceInfo(vid, info["name"], language=info.get("lang", "ur"))
        return out
