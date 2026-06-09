# EYEWAZ — go-live runbook (domain + TLS, device QA, TWA)

Things only you can do are marked **[you]** (they need your registrar / Render /
Play / devices). I've automated everything else.

---

## A. Domain + TLS — eyewaz.com → Render

**1. Render [you]:** Service → **Settings → Custom Domains → Add**:
   - `eyewaz.com` and `www.eyewaz.com`. Render shows the exact DNS target(s).

**2. DNS at your registrar [you]:**
   | Host | Type | Value |
   |---|---|---|
   | `www` | CNAME | `eyewaz-backend-latest.onrender.com` |
   | `@` (apex `eyewaz.com`) | ALIAS / ANAME | `eyewaz-backend-latest.onrender.com` |
   | `@` (only if no ALIAS support) | A | the IP Render shows for the apex |
   - Most registrars (Cloudflare, Namecheap, Google Domains) support ALIAS/ANAME at
     the apex — prefer that. If yours doesn't, use the A record Render gives.
   - Optional: redirect `www` → apex (or vice-versa) in Render.

**3. TLS:** Render auto-issues a Let's Encrypt certificate once DNS resolves
   (minutes to a few hours). Wait for **"Certificate Issued"**; HTTPS is forced.

**4. After it resolves [you, then I verify]:**
   - Point **PayPal & Stripe webhooks** at `https://eyewaz.com/api/paypal/webhook`
     and `…/api/stripe/webhook`.
   - Re-run the live checks (below) against `https://eyewaz.com`.
   - `start_url` is relative, so the PWA/TWA pick up the new domain automatically.

---

## B. Device QA pass

### Already verified automatically (green on production)
- `/app`, `/privacy`, `/app/manifest.webmanifest`, `/app/sw.js`,
  `/.well-known/assetlinks.json`, app icons, `/api/*/config` → all **200**.
- Manifest valid: standalone, start_url `/app`, 192/512 + maskable icons.
- `index.html` accessibility audit: every control has an accessible name.
- `app.js` loads with no errors; backend routes import clean.

### Run on real devices [you] — full list in `docs/QA-REGRESSION.md`
Priority order:
1. **Install the PWA**
   - Android Chrome: ⋮ → **Install app** (or the in-app *Install* button in Account).
   - iPhone Safari: Share → **Add to Home Screen**.
   - Confirm: own icon, standalone window, splash, launches offline (airplane mode → app shell loads).
2. **Accessibility (release blocker)** — turn on **TalkBack** (Android) / **VoiceOver** (iOS):
   - Swipe through every screen: each control announces a clear name.
   - Turn EYEWAZ "Voice on" → focusing icons speaks them.
   - Do a full task **eyes closed**: sign in → photo of text → hear it read → save → replay.
3. **Core flows:** photo / document / text / web read-aloud; My Day; Ask Eyewaz; reminders (incl. fires when app closed on the native build); library folders/sort/resume; dialect chips (session) vs Account default (Urdu).
4. **Dark mode:** every text field readable; time picker usable.
5. **Membership:** free cap at 3/month; upgrade link; (sandbox) PayPal + (test) Stripe/Klarna.
6. **Devices:** new + older Android & iOS; small screen; slow network (cold-start hint).

Record results in the QA sign-off block.

---

## C. Google Play — TWA setup

**0. Do the domain first** (TWA verifies via `eyewaz.com/.well-known/assetlinks.json`).

**1. Generate the TWA [you]:**
```bash
npm i -g @bubblewrap/cli
bubblewrap init --manifest https://eyewaz.com/app/manifest.webmanifest
# package id: com.canvassolutions.eyewaz  (must match assetlinks.json)
bubblewrap build      # creates a signing key + a signed .aab
```

**2. Get the SHA-256 fingerprint(s) [you]:**
```bash
bubblewrap fingerprint        # prints your upload key's SHA-256
```
Put it in `webapp/.well-known/assetlinks.json` (replace the placeholder), commit,
and redeploy. The file's `sha256_cert_fingerprints` is an **array** — add BOTH:
   - your **upload key** SHA-256 (above), and
   - the **Play App Signing** SHA-256 (Play Console → Setup → **App integrity**),
     because Play re-signs the app for store installs.

**3. Verify:** open `https://eyewaz.com/.well-known/assetlinks.json` — it must list
   the real fingerprint(s), no placeholder. (Google's Statement List Tester helps.)

**4. Publish [you]:** Play Console → create app → upload the `.aab` → Internal
   testing → Production. Once assetlinks verifies, the TWA runs full-screen (no
   address bar) and auto-updates with each web release.

**iOS:** Apple has no TWA — use Capacitor (`docs/MOBILE-APP.md`), loading the same
PWA. One codebase, both stores.

---

## Re-run live checks (after domain or any deploy)
```bash
for p in /app /privacy /app/manifest.webmanifest /app/sw.js /.well-known/assetlinks.json; do
  echo "$p -> $(curl -s -o /dev/null -w '%{http_code}' https://eyewaz.com$p)"
done
```
All should be `200` with a valid certificate.
