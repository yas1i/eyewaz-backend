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
STORAGE_DIR=/home/uploads          # persistent on Azure App Service

# Azure AI (same multi-service key)
REGION, VISION_KEY, VISION_ENDPOINT, TRANSLATION_KEY,
TEXT_TRANSLATION_ENDPOINT, SPEECH_KEY

# Email
SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM

# Optional social login (set redirect URIs to https://www.eyewaz.com/api/auth/<p>/callback)
GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, FACEBOOK_APP_ID, FACEBOOK_APP_SECRET
```

## Deploy to Azure App Service (container) — step by step

```bash
# 0. Login + pick your subscription
az login
az account set --subscription "<your subscription>"

# 1. Resource group + Azure Container Registry (ACR)
az group create -n eyewaz-rg -l eastus
az acr create -n eyewazacr -g eyewaz-rg --sku Basic --admin-enabled true

# 2. Build the image in ACR (no local Docker needed)
az acr build -r eyewazacr -t eyewaz-backend:latest .

# 3. App Service plan (Linux). B1 supports custom domains + /home persistence.
az appservice plan create -n eyewaz-plan -g eyewaz-rg --is-linux --sku B1

# 4. Web App from the image
az webapp create -g eyewaz-rg -p eyewaz-plan -n eyewaz \
  --deployment-container-image-name eyewazacr.azurecr.io/eyewaz-backend:latest

# 5. Tell App Service the port + keep /home persistent
az webapp config appsettings set -g eyewaz-rg -n eyewaz --settings \
  WEBSITES_PORT=8080 WEBSITES_ENABLE_APP_SERVICE_STORAGE=true

# 6. Set every app env var (from the list above) in one go
az webapp config appsettings set -g eyewaz-rg -n eyewaz --settings \
  MONGO_URI="..." JWT_SECRET_KEY="..." FLASK_SECRET_KEY="..." \
  PUBLIC_BASE_URL="https://www.eyewaz.com" OAUTH_REDIRECT_BASE="https://www.eyewaz.com" \
  STATIC_DIR="templates/" STORAGE_DIR="/home/uploads" \
  REGION="eastus" VISION_KEY="..." VISION_ENDPOINT="..." \
  TRANSLATION_KEY="..." TEXT_TRANSLATION_ENDPOINT="https://api.cognitive.microsofttranslator.com/" \
  SPEECH_KEY="..." \
  SMTP_HOST="smtp.gmail.com" SMTP_PORT="587" SMTP_USER="..." SMTP_PASSWORD="..." \
  SMTP_FROM="EYEWAZ <...>"
```

Keep the App Service at **1 instance** while using local (/home) storage.
Alternatives (Render/Railway/Fly): point them at this repo's `Dockerfile` and
set the same env vars.

## Domain + HTTPS (Azure)

```bash
# Show the values you need for DNS
az webapp show -g eyewaz-rg -n eyewaz --query defaultHostName -o tsv      # e.g. eyewaz.azurewebsites.net
az webapp deployment list-publishing-profiles ...   # not needed for domain
```

At your DNS provider for **eyewaz.com**, add:

| Type  | Host | Value                                  |
|-------|------|----------------------------------------|
| CNAME | www  | `eyewaz.azurewebsites.net`             |
| TXT   | asuid.www | (the verification ID from the next command) |

```bash
# Get the domain-verification ID
az webapp show -g eyewaz-rg -n eyewaz --query customDomainVerificationId -o tsv
# Add the custom domain, then a free managed certificate
az webapp config hostname add -g eyewaz-rg --webapp-name eyewaz --hostname www.eyewaz.com
az webapp config ssl create -g eyewaz-rg --name eyewaz --hostname www.eyewaz.com
az webapp config ssl bind -g eyewaz-rg --name eyewaz --hostname www.eyewaz.com --ssl-type SNI
```

For the apex `eyewaz.com`, add an ALIAS/A record per your DNS provider (or a
redirect to `www`). HTTPS certs are issued automatically once DNS resolves.

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

---

# Clean-deploy checklist (lessons learned)

Bugs that bit us once, and how to avoid them:

1. **Base image / deps** — Dockerfile must be Python 3.9+ (numpy 2 needs it) and
   `apt install libsndfile1`. Keep `requirements.txt` lines un-merged
   (a missing trailing newline once hid `beautifulsoup4` in a comment).
2. **Render can't pull Azure ACR** — push the image to **Docker Hub** (public)
   and deploy that, or build from a Git repo. ACR creds will always be "invalid".
3. **Bind to `$PORT`** — the Dockerfile CMD uses `0.0.0.0:${PORT:-8080}`.
4. **Every env var must be set** — a missing `STATIC_DIR` crashes boot. Do **not**
   set `PUBLIC_BASE_URL` (leave file links relative). Do **not** set `SMTP_*`.
5. **MongoDB Atlas → Network Access** — add `0.0.0.0/0` as **Permanent**
   (NOT the temporary "delete after N hours" option, which expires and silently
   re-blocks the host). App uses `serverSelectionTimeoutMS=5000` to fail fast.
6. **Email** — PaaS hosts block outbound SMTP. Use **SendGrid** (HTTP API):
   set `SENDGRID_API_KEY` + a verified `SENDGRID_FROM`. With neither SendGrid nor
   SMTP set, codes appear on-screen (dev mode) and the app still works.
7. **Free tier sleeps** (~1 min cold start) → feels broken. Upgrade to a paid
   always-on instance for demos/users.

Production env vars (Render): `MONGO_URI`, `JWT_SECRET_KEY`, `FLASK_SECRET_KEY`,
`STATIC_DIR=templates/`, `REGION`, `VISION_KEY`, `VISION_ENDPOINT`,
`TRANSLATION_KEY`, `TEXT_TRANSLATION_ENDPOINT`, `SPEECH_KEY`,
`SENDGRID_API_KEY`, `SENDGRID_FROM`, `ANTHROPIC_API_KEY`.

8. **Ask Eyewaz assistant** — `/api/assistant` calls Claude (`anthropic` SDK,
   model `claude-opus-4-8`). Set `ANTHROPIC_API_KEY`. Without it the endpoint
   returns a friendly 503 and the rest of the app keeps working.
9. **Membership quotas** — Free = 3 commands/day (1 reminder, 3 recordings),
   Monthly = 50/day, Super Max = 100/day. Enforced server-side in `usage.py`.
   Optional `DEV_PLAN_KEY` env enables `POST /api/dev/plan` to switch a user's
   plan for testing before PayPal is wired (leave unset in production once live).
10. **PayPal subscriptions** — dormant until configured (buttons fall back to a
   "coming soon" placeholder). To switch on:
   - Set `PAYPAL_CLIENT_ID`, `PAYPAL_SECRET`, `PAYPAL_ENV=sandbox` (then `live`),
     `PAYPAL_CURRENCY=GBP`.
   - Create the billing plans once: with `DEV_PLAN_KEY` set, `POST /api/paypal/setup`
     `{ "key": "...", "prices": {"monthly":"4.99","supermax":"9.99"} }` → it returns
     `PAYPAL_PLAN_MONTHLY` / `PAYPAL_PLAN_SUPERMAX`; put those in env + redeploy.
   - Register a webhook at developer.paypal.com → `https://<host>/api/paypal/webhook`
     for the BILLING.SUBSCRIPTION.* and PAYMENT.SALE.COMPLETED events; set its
     `PAYPAL_WEBHOOK_ID`. Card data never touches the app (hosted Smart Buttons).
11. **Stripe = card + Klarna** (one integration provides both). Dormant until set:
   - Create two recurring **Prices** in the Stripe Dashboard (Monthly, Super Max);
     set `STRIPE_SECRET_KEY`, `STRIPE_PRICE_MONTHLY`, `STRIPE_PRICE_SUPERMAX`.
   - In Stripe Dashboard → Settings → **Payment methods**, enable **Card** and
     **Klarna** (Klarna then appears automatically in Checkout). To force a set,
     optionally `STRIPE_PMT_METHODS=card,klarna`.
   - Add a webhook → `https://<host>/api/stripe/webhook` for
     `checkout.session.completed`, `invoice.paid`, `customer.subscription.deleted`;
     set its signing secret as `STRIPE_WEBHOOK_SECRET`.
   - Checkout is Stripe-hosted (redirect) — card/Klarna details never touch the app.
12. **Face ID / passkey sign-in** (WebAuthn) — works out of the box over HTTPS
   (Render provides it). Passkeys are bound to the **domain** (RP ID), so if you
   serve on both the onrender.com URL and `eyewaz.com`, set `WEBAUTHN_RP_ID`
   (e.g. `eyewaz.com`) and `WEBAUTHN_ORIGIN` (e.g. `https://eyewaz.com`) to the
   canonical domain so enrolled passkeys keep working. Otherwise they're derived
   from the request host automatically. Biometrics never leave the device — only
   a public key is stored (`webauthn` lib).
