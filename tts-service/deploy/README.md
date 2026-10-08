# Deploy the EYEWAZ Urdu TTS engine on Hetzner (or any Docker host)

A Hetzner CPU VPS is the best value for an always-on TTS engine (~€4.50/mo vs
~$25/mo on Render). The prebuilt image is on Docker Hub: `aluminur/eyewaz-tts:latest`.

## 1. Create the server (Hetzner Cloud)
- **New Project → Add Server**
- Image: **Ubuntu 24.04**
- Type: **CX22** (2 vCPU / 4 GB RAM, x86) — enough for torch + the MMS model.
  ⚠️ **Use a CX (x86) type, not CAX (ARM)** — the image is amd64.
- Add your **SSH key**, create, and note the **public IP**.
- (Optional, for HTTPS) Add a DNS **A record** `tts.eyewaz.com → <server IP>`.

## 2. Install + run (one command)
SSH in and run the installer (it installs Docker and starts the engine):
```bash
ssh root@<server-ip>
git clone https://github.com/<you>/eyewaz-backend.git
cd eyewaz-backend/tts-service/deploy
bash setup.sh
```
(No git? `scp` this `deploy/` folder up, then `bash setup.sh`.)

First start downloads/loads the model (a few seconds). Verify:
```bash
curl http://localhost:8090/healthz
curl "http://localhost:8090/tts?text=السلام%20علیکم" --output hello.wav
```

## 3. Open the firewall
Hetzner Cloud → **Firewalls** → allow inbound **TCP 8090** (or **80/443** if using
TLS). Apply it to the server.

## 4. Plug it into EYEWAZ
On the EYEWAZ backend (Render) set:
```
SELF_HOST_TTS_URL = http://<server-ip>:8090
```
The backend calls the engine **server-to-server**, so plain HTTP is fine here.
Redeploy the backend, then in the app: **Account → Pakistani dialect & voice →
"Urdu — open-source (free)."**

## 5. (Optional) HTTPS for public/device use
Needed later when phones/extensions call the engine directly. Point
`tts.eyewaz.com` at the server, edit `Caddyfile`, then:
```bash
docker compose --profile tls up -d
```
Caddy auto-issues a Let's Encrypt cert. Use `SELF_HOST_TTS_URL=https://tts.eyewaz.com`.

## Updating
```bash
docker compose pull && docker compose up -d
```

## Nightly restart of the speech container
A systemd timer on the production server restarts `eyewaz-tts-piper` once a
night, at a quiet moment. It was installed by hand on 8 October 2026; the three
files in this folder are exact copies of what is live.

**Why.** The engine keeps the memory of the longest sentence it has ever spoken
and does not give it back, so it climbs to its 1 GB limit and sits there while
idle. After five days up it held 956 MB plus 525 MB of swap with no requests; a
restart took it to 73 MB. The cause, the measurements and the recommended fix
are in [MEMORY.md](MEMORY.md). The restart is a safety net, not the fix.

**What it does.** At 04:24 each night, after the server's backups (03:15 to
03:45 UTC), the script looks at the container:
- not running: it is left alone;
- no `POST /tts` in its log for the last five minutes: `docker restart`, then
  wait for `http://127.0.0.1:8090/voices` to answer 200 (the run is marked
  failed if it does not);
- busy: try again every ten minutes for an hour, then leave it until the next
  night.

The timer line carries no time zone, so 04:24 is in the server's own zone. That
is 04:24 UTC only while the server clock is set to UTC (`timedatectl` shows it).

**Where the files install to.**

| In this folder | On the server |
|---|---|
| `eyewaz-tts-nightly-restart` | `/usr/local/sbin/eyewaz-tts-nightly-restart` (root, mode 755) |
| `eyewaz-tts-nightly-restart.service` | `/etc/systemd/system/eyewaz-tts-nightly-restart.service` |
| `eyewaz-tts-nightly-restart.timer` | `/etc/systemd/system/eyewaz-tts-nightly-restart.timer` |

Nothing copies them across automatically: a change made here reaches the server
only when someone installs it. To install on a rebuilt server, as root from this
folder:
```bash
install -m 0755 eyewaz-tts-nightly-restart /usr/local/sbin/
install -m 0644 eyewaz-tts-nightly-restart.service eyewaz-tts-nightly-restart.timer /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now eyewaz-tts-nightly-restart.timer
```

**Dry run.** Says what it would do and changes nothing:
```bash
DRY=1 /usr/local/sbin/eyewaz-tts-nightly-restart
```

**Read its log.** One line per night, for example
`eyewaz-tts-piper restarted, answering again after about 4 s`:
```bash
journalctl -u eyewaz-tts-nightly-restart
```
`systemctl list-timers eyewaz-tts-nightly-restart.timer` shows the last and the
next run.

## Notes
- RAM: keep ≥ 4 GB; torch + model peak ~2 GB.
- Licence: MMS is **CC-BY-NC** — fine for piloting; swap `TTS_MODEL` to a
  permissive voice (or your own from the voice bank) before commercial use.
