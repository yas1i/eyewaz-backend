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

## Notes
- RAM: keep ≥ 4 GB; torch + model peak ~2 GB.
- Licence: MMS is **CC-BY-NC** — fine for piloting; swap `TTS_MODEL` to a
  permissive voice (or your own from the voice bank) before commercial use.
