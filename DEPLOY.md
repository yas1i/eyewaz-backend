# EYEWAZ Deploy & Troubleshooting Guide

Last updated: 26 June 2026

---

## Current live setup

| What | Where |
|------|-------|
| Backend | Render free tier, service `srv-d8gtdf3tqb8s73950ulg` |
| Image | Docker Hub `aluminur/eyewaz-backend:latest` |
| Domain | `www.eyewaz.com` |
| DNS | Cloudflare (nameservers: adaline + garrett.ns.cloudflare.com) |
| File storage | Backblaze B2, bucket `eyewaz-voicebank` (public), endpoint `https://s3.us-west-004.backblazeb2.com` |
| Database | MongoDB Atlas |

---

## Normal deploy (code change → live)

```bash
# 1. Make your changes in eyewaz-backend-main/

# 2. Commit and push to GitHub (triggers the Render webhook automatically)
git add .
git commit -m "your message"
git push origin main
```

That's it. The GitHub webhook fires → Render re-deploys from Docker Hub.

**BUT** — GitHub push does NOT rebuild the Docker image. If you changed Python files,
HTML, or anything in the repo, you must also rebuild and push the Docker image:

```bash
cd "/Users/wajd/Documents/Claude Projects/eyewaz-backend-main"
docker build --platform linux/amd64 -t aluminur/eyewaz-backend:latest .
docker push aluminur/eyewaz-backend:latest
```

Then trigger the deploy:
```bash
curl -X POST "https://api.render.com/deploy/srv-d8gtdf3tqb8s73950ulg?key=M9wZPZFt8sc"
```

Or just `git push` after the Docker push — the webhook fires the same deploy.

---

## Quick deploy reference

| Action | Command |
|--------|---------|
| Build image | `docker build --platform linux/amd64 -t aluminur/eyewaz-backend:latest .` |
| Push image | `docker push aluminur/eyewaz-backend:latest` |
| Trigger deploy | `curl -X POST "https://api.render.com/deploy/srv-d8gtdf3tqb8s73950ulg?key=M9wZPZFt8sc"` |
| Check if live | `curl -s https://www.eyewaz.com/privacy \| grep "Last updated"` |
| Check Render logs | Render dashboard → eyewaz service → Logs |
| Check deploy status | Render dashboard → eyewaz service → Events |

---

## Troubleshooting: site not updating after deploy

### Step 1: Check Render Events tab (not Logs)
- Logs shows gunicorn start/stop (sleep cycles) — that is NOT a deploy
- Events tab shows actual deploys: "Deploy started", "Deploy live", "Deploy failed"
- If last deploy is old, the new image was never pulled

### Step 2: Check Docker Hub has the new image
The deploy hook tells Render to pull `aluminur/eyewaz-backend:latest` from Docker Hub.
If you haven't pushed a new image, Render just re-pulls the old one.
Always rebuild + push before triggering a deploy.

### Step 3: Check if Render is serving the right thing
```bash
curl -s https://www.eyewaz.com/privacy | grep "Last updated"
```
If this returns old content but deploy shows "Live", it's a Cloudflare cache issue.
Go to Cloudflare → eyewaz.com → Caching → Purge Everything.

### Step 4: Wrong field in Render Settings
If you ever see the Docker Command field in Render → Settings → Deploy containing
a URL or GitHub link, clear it immediately. That field should be empty (the
Dockerfile CMD handles startup). A URL there causes the container to fail to start.

---

## Troubleshooting: site completely down (NXDOMAIN / nothing loads)

This means a DNS problem. Work through these in order:

### Check 1: DNS resolves at all
```bash
dig www.eyewaz.com @8.8.8.8 +short
```
Should return two Cloudflare IPs (like 104.21.x.x and 172.67.x.x).
If it returns nothing: the DNS record is missing in Cloudflare.

### Check 2: Root domain also resolves
```bash
dig eyewaz.com @8.8.8.8 +short
```
Should return Cloudflare IPs. If only NS records appear (no A/CNAME), the root
domain has no record. Add in Cloudflare DNS:
- Type: CNAME, Name: `@`, Target: `www.eyewaz.com`, Proxy: ON

### Check 3: Cloudflare has the www record
In Cloudflare → eyewaz.com → DNS, you need:
```
CNAME   www   eyewaz.onrender.com       (Proxy: ON)
CNAME   @     www.eyewaz.com            (Proxy: ON)
CNAME   files s3.us-west-004.backblazeb2.com  (Proxy: ON, for B2 CDN)
```
If www or @ is missing, add it. Changes take 1-5 minutes with Cloudflare.

### Check 4: Nameservers correctly set at registrar
Cloudflare nameservers for eyewaz.com are:
- `adaline.ns.cloudflare.com`
- `garrett.ns.cloudflare.com`

If you ever change registrar or accidentally revert nameservers, all DNS breaks.
Check at: `dig eyewaz.com NS @8.8.8.8 +short`

### Check 5: Local DNS cache (your machine shows NXDOMAIN but others don't)
```bash
sudo dscacheutil -flushcache; sudo killall -HUP mDNSResponder
```
Or in Chrome: `chrome://net-internals/#dns` → Clear host cache.
Note: your ISP/carrier DNS may take up to a few hours to see changes even after
Google DNS (8.8.8.8) resolves correctly. Use a VPN or mobile data from a different
carrier as a quick test.

### Check 6: Render service is healthy
If DNS resolves but the site returns 502/503:
- Render free tier takes ~50 seconds to wake from sleep. Wait and retry.
- Check Render Logs for Python errors or missing env vars.
- Check Events tab for a failed deploy.

---

## Cloudflare DNS records (full list — re-create if lost)

| Type | Name | Target | Proxy |
|------|------|--------|-------|
| CNAME | `www` | `eyewaz.onrender.com` | ON |
| CNAME | `@` | `www.eyewaz.com` | ON |
| CNAME | `files` | `s3.us-west-004.backblazeb2.com` | ON |

---

## Render environment variables

Set these in Render → eyewaz service → Environment:

```
MONGO_URI                    MongoDB Atlas SRV string
JWT_SECRET_KEY               Long random secret
FLASK_SECRET_KEY             Long random secret
PUBLIC_BASE_URL              https://www.eyewaz.com
STATIC_DIR                   templates/
WEBAUTHN_RP_ID               eyewaz.com
WEBAUTHN_ORIGIN              https://www.eyewaz.com

# Azure AI
REGION                       eastus
VISION_KEY
VISION_ENDPOINT
TRANSLATION_KEY
TEXT_TRANSLATION_ENDPOINT    https://api.cognitive.microsofttranslator.com/
SPEECH_KEY

# Email (Brevo/SMTP)
SMTP_HOST
SMTP_PORT
SMTP_USER
SMTP_PASSWORD
SMTP_FROM

# Anthropic (Ask EYEWAZ assistant)
ANTHROPIC_API_KEY

# Backblaze B2
S3_BUCKET                    eyewaz-voicebank
S3_ENDPOINT                  https://s3.us-west-004.backblazeb2.com
S3_REGION                    us-west-004
S3_ACCESS_KEY_ID
S3_SECRET_ACCESS_KEY
# S3_CDN_URL                 https://files.eyewaz.com  (enable once Cloudflare CDN confirmed)
```

---

## Known gotchas

1. **Render Logs vs Events**: Logs only shows gunicorn start/stop (sleep cycles).
   Deploy activity is in the Events tab. Many wasted hours confusing the two.

2. **Docker Hub image must be rebuilt**: git push alone does not update the Docker
   image. You must `docker build + docker push` first, then trigger the deploy.
   The GitHub webhook only triggers Render to pull whatever is currently on Docker Hub.

3. **Root domain CNAME**: Cloudflare supports CNAME on `@` (apex) via CNAME
   flattening. Other DNS providers do not. If you ever move DNS away from Cloudflare,
   use an A record pointing to Cloudflare/Render IPs instead.

4. **Cloudflare proxied (orange cloud ON)**: Keep it ON. This gives free CDN,
   DDoS protection, and the Bandwidth Alliance for B2 egress. Turning it off
   (grey cloud) exposes your Render IP directly and breaks B2 egress savings.

5. **Free tier cold start**: Render free tier spins down after 15 minutes of
   inactivity. First request after sleep takes ~50 seconds. This is normal.
   Users see a blank/slow load, then it works. Upgrade to paid to eliminate this.

6. **Docker Command field**: In Render → Settings → Deploy, the Docker Command
   field must be empty. Never paste a URL or GitHub link there. It overrides the
   Dockerfile CMD and will cause the container to fail to start silently.

7. **Missing env var = silent crash**: A missing required env var (MONGO_URI,
   JWT_SECRET_KEY, SPEECH_KEY etc.) causes the app to boot but fail on first use.
   Check Render Logs for ImportError or KeyError on startup.

---

## Lessons from 26 June 2026 outage

What went wrong and what fixed it:

1. **Render stuck on old image**: Manual Deploy button didn't work. Fix: use the
   deploy hook URL directly with curl. Also rebuild the Docker image first.

2. **Accidental GitHub URL in Docker Command field**: Pasted into the wrong field
   during attempted settings change. Caused deploy to silently use wrong CMD.
   Fix: clear the field in Render Settings → Deploy.

3. **DNS broke after Cloudflare nameserver migration**: Moving nameservers from
   IONOS to Cloudflare did not auto-import the existing DNS records. Result: both
   `www.eyewaz.com` and `eyewaz.com` returned NXDOMAIN. Fix: manually add CNAME
   records for `www` and `@` in Cloudflare DNS panel.

4. **NXDOMAIN on phone (3G)**: Even after fixing DNS, the user's carrier DNS
   hadn't propagated. Fix: wait, or test with `dig @8.8.8.8` to confirm global
   resolution before assuming it's still broken.

---

## Android TWA

- Package: `com.eyewaz.app`
- Target SDK: 35, Compile SDK: 36
- Theme: `#1f3d3a`
- Play Console pending: Data Safety form, assetlinks.json SHA-256 (get from Play Console → App integrity)

---

## Voice bank / Piper TTS

Recorder at `/record/` saves WAV files to B2: `voicebank/{lang}/{speaker}/{sentence_id}.wav`
Keep this endpoint live. When self-hosted Piper voice is ready:
1. Set `SELF_HOST_TTS_URL` on Render
2. Set `SELF_HOST_TTS_KEY` on Render
3. Remove `SPEECH_KEY` and `SPEECH_REGION` from Render
4. Restart service
5. Test voice output
