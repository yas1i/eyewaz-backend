# EYEWAZ — Google Play release, testing & approval runbook

You ship **two** apps to Play:
1. **EYEWAZ** — the PWA wrapped as a **TWA** (`com.canvassolutions.eyewaz`).
2. **EYEWAZ Urdu Voice** — the **TTS engine** (`com.canvassolutions.eyewaztts`,
   in `android-tts/`). Separate listing, normal AAB (not a TWA).

Do app #1 first; #2 is an easier repeat.

---

## ⚠️ Two things that cause rejection — decide BEFORE you submit

### A. Reviewers must be able to log in (OTP problem)
The app requires email-OTP sign-in. A Google reviewer **cannot receive your OTP
email**, so they can't get past login → automatic rejection under "App access".
Fix one of these before submitting:
- Create a **demo account** whose OTP is fixed/known (e.g. a test email where the
  code is always `000000`, gated to that one address), **or**
- A reviewer bypass: a hard-coded test email + password path that skips OTP.
Then enter those credentials in **Play Console → App access**. Without this, you
will be rejected.

### B. Payments — Play Billing vs PayPal/Stripe
Google requires **Play Billing** for in-app purchases of **digital** goods
(your Monthly/SuperMax tiers). Selling those via PayPal/Stripe *inside the
Android app* violates Play policy → rejection or later removal. Pick one:
- **Recommended for v1:** **hide the upgrade/purchase UI in the Android (TWA)
  build** — keep paid tiers purchasable only on the website in a normal browser.
  The app stays free-to-use; no in-app digital sale, no policy breach.
- Or integrate **Google Play Billing** (bigger work; 15–30% fee).
The TWA loads your site, so gate the upgrade buttons behind "is this running
inside the TWA?" and hide them if so. **Confirm this is done before submission.**

---

## 0. Prerequisites
- **Play Developer account** — one-time $25, ID verification (a few days). Choose
  **Organisation** if you can (see step 6 — personal accounts have an extra
  12-tester / 14-day hurdle).
- Privacy policy live at **https://eyewaz.com/privacy** (ships with the next
  backend deploy).
- A **public account-deletion page/URL** (Play requires a way to request deletion
  without installing — your in-app delete alone isn't enough).
- JDK 17 + Android SDK (Bubblewrap installs what it needs).

---

## 1. Build the TWA (AAB) with Bubblewrap
```bash
npm i -g @bubblewrap/cli
mkdir -p twa && cd twa
bubblewrap init --manifest https://eyewaz.com/app/manifest.webmanifest
# answers: package = com.canvassolutions.eyewaz ; host = eyewaz.com ;
#          start url = /app ; name = EYEWAZ ; display = standalone
bubblewrap build      # creates app-release-bundle.aab + signs with an upload key
```
- On first build Bubblewrap **creates an upload keystore** — back it up
  (`android.keystore` + the passwords). Losing it = can't update the app.
- Output to upload: **`app-release-bundle.aab`**.

## 2. Create the app in Play Console
**Play Console → Create app**: name `EYEWAZ`, default language English, type
**App**, **Free**, accept declarations.

## 3. Turn on Play App Signing & fix assetlinks (makes the URL bar disappear)
1. Upload the AAB once (step 5) so Play enables **App signing**.
2. **Test and release → Setup → App integrity → App signing** → copy the
   **SHA-256 of the "App signing key certificate"** (NOT the upload key).
3. Put that fingerprint into `webapp/.well-known/assetlinks.json` (replace
   `REPLACE_WITH_YOUR_PLAY_APP_SIGNING_SHA256_FINGERPRINT`), commit, redeploy the
   backend. Verify: `https://eyewaz.com/.well-known/assetlinks.json` returns it.
   If this is wrong, the TWA shows an ugly browser address bar.

## 4. Complete every "Set up your app" task (Dashboard)
- **App access** → provide the demo login from risk A.
- **Ads** → No ads.
- **Content rating** → fill IARC questionnaire (it's a utility → low rating).
- **Target audience** → 18+ (or 13+); **not** "designed for children" (avoids
  Families policy).
- **Data safety** → use the table in `STORE-SUBMISSION.md` (collects name/email/
  phone, audio/photos/files to provide the feature, usage; shared only with
  processors Azure/Anthropic/SendGrid/PayPal/Stripe; encrypted in transit;
  deletion offered). Declare the **account-deletion URL**.
- **Privacy policy** → https://eyewaz.com/privacy.
- **Government / financial features** → No (subscriptions ≠ regulated financial
  features).

## 5. Store listing assets
- **App icon** 512×512 PNG; **Feature graphic** 1024×500; **Phone screenshots**
  ≥ 2 (use the 6 from `STORE-SUBMISSION.md`: My Day, Photo→reading, My Library,
  Ask Eyewaz, Dialect picker, Reminders). Short + full description from that file.

## 6. Testing tracks (this is "the test process")
Tracks, fastest → slowest: **Internal → Closed → Open → Production.**
1. **Internal testing** (instant, up to 100 testers, no review wait): create a
   release, upload the AAB, add tester emails, share the opt-in link, install on a
   real device, run `docs/QA-REGRESSION.md`. Use this for your own QA loop.
2. **Personal-account rule:** if your developer account is **personal/individual**
   (created after Nov 2023), Google requires a **Closed test with ≥12 testers who
   stay opted-in for ≥14 days** before you can apply for **Production**. Plan for
   this: recruit 12 people (a Google Group is easiest), run a closed test for two
   weeks, then "Apply for production access". **Organisation** accounts are
   exempt. This is the most common surprise — start the 14-day clock early.
3. **Open testing** (optional public beta) — anyone with the link, still subject
   to review.

## 7. Production release
**Production → Create new release** → upload the AAB (or promote from a test
track) → release notes → **staged rollout** (start 10–20%). **Send for review.**
- First review for a new app: typically **a few days to ~7 days** (longer for new
  accounts). Subsequent updates are faster.
- Watch **Policy status** and your email for any rejection reasons; fix and resubmit.

---

## 8. The TTS engine app (second submission)
- Build a normal release AAB from `android-tts/` (Android Studio → Build →
  Generate Signed Bundle, or `./gradlew bundleRelease` with a keystore).
- New Play listing, package `com.canvassolutions.eyewaztts`.
- It declares `BIND_TEXT_TO_SPEECH_SERVICE` / acts as a system TTS engine — that's
  allowed. In the listing, explain it's an **accessibility TTS voice** that powers
  TalkBack and other apps in Urdu.
- Same Data safety / content rating / privacy steps. No payments, so risk B
  doesn't apply. Reviewers can test it via Settings → Accessibility →
  Text-to-speech → choose EYEWAZ, then "Listen to an example" — note this in
  **App access / review notes** (it needs your TTS server reachable, so keep the
  Hetzner service up during review).

---

## Pre-submit checklist (app #1)
- [ ] Risk A handled — demo login works without a real OTP inbox.
- [ ] Risk B handled — no in-app digital purchase UI in the TWA build.
- [ ] `assetlinks.json` has the **Play app-signing** SHA-256 and is live.
- [ ] Privacy policy + public deletion URL live.
- [ ] Data safety, content rating, target audience, app access all green.
- [ ] `DEV_PLAN_KEY` unset in production.
- [ ] `docs/QA-REGRESSION.md` green on a real device via Internal testing.
- [ ] Upload keystore backed up somewhere safe.
