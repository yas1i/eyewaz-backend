# Why the speech container fills its memory limit, and what to do about it

Written 8 October 2026. Nothing here has been applied: the compose file, the
engine and the server are unchanged, and each step below needs the owner's say.

## Short answer
It is not a slow leak. The memory the engine needs is set by the **longest single
sentence** in a request, not by how much text is sent, and the runtime underneath
Piper (onnxruntime) keeps that memory afterwards instead of handing it back. One
long sentence with no full stop is enough to put the container at its limit, and
it then stays there while idle until it is restarted.

Recommendation, in order:
1. **Split long sentences inside the engine** before they reach the voice, at
   about 100 characters. This is the fix.
2. **Leave `mem_limit` at 1g.** Do not lower it.
3. **Do not rely on an allocator setting.** It does not lower the peak.
4. **Keep the nightly restart** as a safety net until step 1 has been live for a
   week and idle memory is seen to stay flat.

## What was measured
Measured on a Mac, not on the server: the same two voice files and `app.py`
code path, with piper-tts 1.6.0 and onnxruntime 1.28.0 on Python 3.14. The server
runs Linux with whatever versions the image was built with (they are not pinned
in `requirements.txt`), so treat the figures as close rather than exact. They do
line up with all three figures known from the server, shown in the last column.

One voice, one request, peak resident memory:

| Text sent | Longest sentence | Peak | Server figure it matches |
|---|---|---|---|
| 900 characters, a full stop every 12 words | about 55 characters | 320 MB | "normal load near 293 MB" |
| 1,200 characters, a full stop every 12 words | about 55 characters | 321 MB | |
| 100 characters, no full stop | 100 characters | 391 MB | |
| 200 characters, no full stop | 200 characters | 577 MB | |
| 400 characters, no full stop | 400 characters | 948 MB | |
| 600 characters, no full stop | 600 characters | 1,435 MB | 956 MB plus 525 MB swap on 8 October |
| 900 characters, no full stop | 900 characters | 1,909 MB | the 1.9 GB that woke the host OOM killer on 9 September |
| 1,200 characters, no full stop | 1,200 characters | 2,826 MB | |

That is roughly 1.5 to 2 MB for every character of the longest sentence.

The memory is kept afterwards. In every row, ten short requests sent after the
long one left the process at its peak. Piper builds its onnxruntime session with
default options (`piper/voice.py`, `onnxruntime.SessionOptions()`), and by default
onnxruntime holds freed memory in its own arena for reuse. That is why the
container was idle at 956 MB.

Each voice has its own session, so the two add up. Both voices loaded, each
having spoken one sentence of the given length:

| Longest sentence | Both voices, peak |
|---|---|
| 40 characters | 425 MB |
| 100 characters | 587 MB |
| 150 characters | 769 MB |
| 200 characters | 942 MB |
| 300 characters | 1,258 MB |

So one 200 character sentence in each voice is all it takes to sit at the 1 GB
limit. Nothing unusual has to happen.

## Where long sentences come from
Piper splits on full stops (Urdu or Latin), question marks and blank lines. It
does **not** split on commas, semicolons, colons or single line breaks (checked
against the installed voice). Lists, headings, tables, addresses, poetry and
scanned text without full stops therefore arrive as one very long sentence.
The backend (`selfhost_tts._chunks`) cuts text every 900 characters at a space,
with no regard for sentences, and the engine accepts up to 1,200 (`TTS_MAX_CHARS`),
so a 900 character sentence is a request the system will send today.

## The options that were asked about

**A lower `mem_limit`: no.** The limit is not what makes it grow, and lowering it
does not make a long sentence need less. It only moves the point at which the
container is killed in the middle of a request. With both voices in use, 1 GB is
already tight.

**An allocator setting: not as the fix.** Turning the onnxruntime arena off
(`enable_cpu_mem_arena = False`) did not lower the peak in testing; it raised it
(1,306 MB against 948 MB for a 400 character sentence, 2,930 MB against 1,909 MB
for 900). At best it would release memory after the request, which could not be
confirmed on a Mac because Linux hands memory back differently. Piper also offers
no way to pass the option in, so it would mean patching around the library.
`MALLOC_ARENA_MAX` and similar settings act on a different allocator and would
not touch the memory onnxruntime is holding. Worth a second look only if idle
memory is still a concern after step 1.

**Keeping the nightly restart: yes, for now.** It is cheap, it waits for a quiet
moment, and it clears whatever the day left behind. It does not stop a long
sentence from filling the container during the day, so it is not enough alone.

## The recommended fix
In `tts-service/app.py`, before `voice.synthesize(...)`, break any sentence
longer than about 100 characters at the nearest comma, semicolon or colon, and
failing that at a space. With that in place the worst case is the 587 MB row
above for both voices, about 57% of the limit, whatever is sent. A listener hears
a short pause where a very long sentence was split; sentences of ordinary length
are untouched.

The engine is the right place rather than the backend, because the Android,
NVDA and browser clients are built to call the engine directly and would
otherwise be able to send the same long sentences. It is a code change and a rebuild of the container,
not a change to the compose file.

Every new voice adds roughly 150 MB when first used plus its own kept memory.
Two voices fit in 1 GB with the fix; a third or fourth will need the limit
looked at again.

## One thing that changed on 8 October
Before that day's restart the kernel swap limit was not in force, so a long
sentence spilled into swap and the request survived, slowly. Now that
`memory.swap.max` is 0, a request that needs more than 1 GB gets the engine
killed instead. Docker restarts it (`restart: unless-stopped`) and the backend
falls back to Azure, so the listener still hears speech, but in an Azure voice.
From the table, that means a sentence over roughly 400 characters with one voice
warm, or over roughly 200 with both. Until the fix is in, expect this to show as:
- `[TTS-FALLBACK]` lines in the Render logs;
- a rising `docker inspect -f '{{.RestartCount}}' eyewaz-tts-piper`;
- "Memory cgroup out of memory" lines in `dmesg` on the server.

Why the swap limit was missing before the restart cannot be told from this
repository. After any future `docker compose up`, it is worth one check that
`memory.swap.max` in the container's cgroup reads 0.

## Confirming this on the server (optional, with the owner's say)
Right after a nightly restart, send one request holding a single 200 character
sentence with no full stop and watch `docker stats eyewaz-tts-piper`. If the
above is right it goes to about 580 MB and stays there after the request ends.
