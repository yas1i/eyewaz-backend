# EYEWAZ local Piper voice — instant, offline, free

Runs your trained Piper voice on the user's **own machine** and serves the same
`/tts` HTTP contract as the cloud `tts-service`. Every EYEWAZ client then works
**offline with no network latency and no per-character cost** — just point its
URL at this local server.

This is the snappy path for *system-wide* screen reading (NVDA/JAWS), where a
network round-trip per utterance is too slow.

## Run it
```bash
pip install -r requirements.txt          # piper-tts (CPU, tiny)
python piper_server.py --model /path/eyewaz-urdu-female.onnx --port 59125
# or:  PIPER_MODEL=/path/eyewaz-urdu-female.onnx python piper_server.py
```
You need the trained `eyewaz-urdu-*.onnx` (+ its `.onnx.json`) from
`../tts-train/`. Until then, any Piper voice works for testing.

Quick check:
```bash
curl http://127.0.0.1:59125/healthz
curl -s "http://127.0.0.1:59125/tts?text=ٹیسٹ" -o test.wav && afplay test.wav 2>/dev/null || true
```

## Point the clients at it
| Client | Where to set the URL |
|---|---|
| **NVDA add-on** | `extensions/nvda/eyewaz.json` → `"TTS_URL": "http://127.0.0.1:59125"` |
| **Chrome extension** | popup → Voice service settings → URL `http://127.0.0.1:59125` |
| **Windows SAPI engine** | `windows-sapi/` posts to `http://127.0.0.1:59125/tts` by default |

No API key is needed for localhost (the `X-API-Key` check is off unless you pass
`--api-key`).

## Run it automatically on login
- **Windows:** Task Scheduler → "At log on" → `pythonw piper_server.py --model …`
  (or bundle it inside the SAPI installer so users never see it).
- **macOS:** a LaunchAgent plist running the same command.
- **Linux:** a `systemd --user` service.

## Female + male
Run two instances on different ports (e.g. 59125 female, 59126 male) and point
different clients at each — or we add a `?voice=` switch later when both models
exist.

## Why a separate tiny server (not the full tts-service)?
`tts-service` carries torch + the MMS model for the cloud. For on-device we only
need `piper-tts`, so this is a ~single-file, dependency-light server that starts
instantly and is easy to ship inside an installer.
