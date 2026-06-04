# Deploying EYEWAZ to www.eyewaz.com

The backend serves both the API (`/api/*`) and the web client (`/app`) from one
origin, so you deploy **one** service.

## Decisions to make first

1. **Host.** Recommended: **Azure App Service (Linux)** — you're already on Azure
   (AI services), so networking/secrets/billing live in one place and it gives a
   free managed TLS cert + custom domains. Easy alternatives: **Render**,
   **Railway**, **Fly.io** (all support the included `Dockerfile`).
2. **Database.** Create a **MongoDB Atlas** cluster (free M0 works to start) and
   use its SRV connection string as `MONGO_URI`.
3. **File storage.** `uploads/` (generated audio + uploads) is on local disk.
   - Single instance on **Azure App Service**: the `/home` dir persists across
     restarts — fine for an MVP (set the app to 1 instance, store under /home).
   - For scale-out / durability: switch storage to **Azure Blob** (a small change
     in `storage.py` — ask and we'll add an env toggle) and create an Azure
     Storage account.
4. **Domain.** You need to own **eyewaz.com** and be able to edit its DNS.

## Environment variables (set on the host, never in git)

Copy from `.env.example`. For production set:

```
MONGO_URI=<your Atlas SRV string>
JWT_SECRET_KEY=<new long random string>      # regenerate, don't reuse dev
FLASK_SECRET_KEY=<new long random string>
PUBLIC_BASE_URL=https://www.eyewaz.com
OAUTH_REDIRECT_BASE=https://www.eyewaz.com
STATIC_DIR=templates/

# Azure AI (same multi-service key)
REGION, VISION_KEY, VISION_ENDPOINT, TRANSLATION_KEY,
TEXT_TRANSLATION_ENDPOINT, SPEECH_KEY

# Email
SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM

# Optional social login (set redirect URIs to https://www.eyewaz.com/api/auth/<p>/callback)
GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, FACEBOOK_APP_ID, FACEBOOK_APP_SECRET
```

## Deploy (Azure App Service via container)

```bash
# Build & push the image (Azure Container Registry or Docker Hub)
docker build -t eyewaz-backend .
# ... push to your registry ...

# In the Azure portal: App Service (Linux) -> Deployment Center -> point at the
# image. Set all env vars under Configuration > Application settings. The app
# listens on 8080 (Dockerfile EXPOSE/CMD).
```

Render/Railway/Fly: point them at this repo's `Dockerfile`; set the same env vars.

## Domain + HTTPS

1. In the host, add custom domain **www.eyewaz.com** (and apex `eyewaz.com`).
2. At your DNS provider: `CNAME www -> <host target>`; for the apex use the
   host's ALIAS/A record. Add the host's domain-verification TXT record.
3. Enable the host's **managed TLS certificate** (automatic on Azure/Render).
4. Optionally redirect `eyewaz.com` -> `www.eyewaz.com`.

## After deploy — checklist

- [ ] `https://www.eyewaz.com/app` loads the web client
- [ ] Sign up with a real email -> code arrives -> verified
- [ ] Photo -> Urdu audio plays; web-page reader + Urdu translate work
- [ ] Account page lists voices and saves settings
- [ ] If using social login: redirect URIs updated in Google/Facebook consoles
- [ ] Rotate any dev secrets (JWT/Flask keys; Azure key if it ever leaked)

## Production hardening (recommended, optional)

- Move file storage to Azure Blob for durability/scale.
- Tighten CORS in `server.py` from `*` to `https://www.eyewaz.com`.
- Add request logging/monitoring; set a real SMTP/transactional email sender.
- Add a healthcheck endpoint and autoscale rules.
