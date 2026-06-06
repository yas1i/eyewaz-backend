# EYEWAZ — release validation & regression checklist

Run this before every publish to **eyewaz.com** and before each **app-store** build.
EYEWAZ is for blind and low-vision users, so **accessibility is a release blocker**,
not a nice-to-have. ✅ = pass, ❌ = blocker, ⚠️ = ship-with-note.

## 0. Pre-flight (automated, do first)
- [ ] `node webapp/... ` load-harness reports **no load-time errors** (`node /tmp/load_harness.js` from `webapp/`).
- [ ] Backend imports clean: `python -c "import routes; ..."` (no ImportError).
- [ ] App serves: `/app`, `/app/manifest.webmanifest`, `/app/sw.js`, `/app/assets/icon-*.png` all **200**.
- [ ] `/api/paypal/config` and `/api/stripe/config` return **200** with `enabled` flags.
- [ ] Git clean, image built + pushed, **Render shows the new digest**.

## 1. Auth & accounts
- [ ] Sign up → email OTP arrives → verify → lands in app.
- [ ] Log in / log out; wrong password rejected.
- [ ] Forgot password → reset works.
- [ ] **Face ID / passkey**: enable, log out, sign in with biometric.
- [ ] Social buttons (Google/Apple/Facebook) — present; if OAuth keys unset, fail gracefully.

## 2. Core read-aloud pipeline (the heart of the app)
- [ ] **Photo**: take/upload a photo of text → OCR → translate → audio plays.
- [ ] **Document**: upload PDF / DOCX / TXT / EPUB → reads aloud.
- [ ] **Text**: type/paste → reads aloud; translation shown.
- [ ] **Web page**: paste URL → extracts → reads aloud.
- [ ] Urdu audio plays (Azure ur-PK); non-Urdu uses browser voice where available.
- [ ] Errors are friendly (bad file, empty OCR, network).

## 3. My Day, assistant, reminders
- [ ] Greeting + date + today's to-do read aloud ("Start my day").
- [ ] **Ask Eyewaz** (Claude): mic → spoken reply (needs `ANTHROPIC_API_KEY`); typed fallback.
- [ ] **Reminders**: add (daily/weekday/weekend/once) → fires aloud at the set time while app open.

## 4. My Library (recordings + folders)
- [ ] Save offline → appears as a card with cover, progress, date.
- [ ] Play → resumes from last position; finishing moves it to **Completed**.
- [ ] Search filters; To-do/Completed toggle; **Sort** cycles.
- [ ] ⋮ menu: favourite, **Move to folder** (tap list, ＋ New folder), delete.
- [ ] Folder create/delete; counts correct.

## 5. Dialects & voice
- [ ] Account → **Pakistani dialect & voice**: pick a dialect → saved as default.
- [ ] Reading screen **dialect chips**: switch → applies **this session only**; next login back to saved default (Urdu).
- [ ] Changing language/voice/speed on a reading page does **not** overwrite the account default.
- [ ] (If `ELEVENLABS_API_KEY` set) Admin voice bank: record/upload + consent → Create → dialect goes Live → reads in cloned voice.

## 6. Membership & payments
- [ ] Plan line shows "N of N commands left this month"; **Upgrade** link opens plan section.
- [ ] Free tier blocks the 4th command this month with a spoken upgrade prompt; 1 reminder / 3 recordings caps enforced.
- [ ] `setPlan("monthly", DEV_PLAN_KEY)` raises the cap (test only).
- [ ] **PayPal** (sandbox): button → approve → plan flips → quota rises. (needs creds + `/setup`)
- [ ] **Stripe/Klarna** (test): "Card or Klarna" → checkout → return → plan flips. (needs keys + prices)

## 7. PWA / installable
- [ ] Chrome/Android: "Install app" prompt appears; installs; launches standalone with EYEWAZ icon + splash.
- [ ] iOS Safari: Add to Home Screen → opens full-screen.
- [ ] Offline: open installed app with no network → app shell loads (cached); clear message on actions needing network.
- [ ] Service worker updates on new release (bump `CACHE` in `sw.js`).

## 8. Accessibility (BLOCKER — test on a real device)
- [ ] **TalkBack (Android)** and **VoiceOver (iOS)**: every control has a spoken label; nothing reads "button, button".
- [ ] **Voice guidance on**: focusing icons/tabs/bottom-bar speaks their name.
- [ ] All tap targets ≥ 44px; text scales with OS large-font setting.
- [ ] Colour contrast AA (already tuned); test dark mode too.
- [ ] Full task by ear only: sign in → photo → hear it read → save → replay — with the screen off / eyes closed.

## 9. Cross-device matrix (minimum)
- [ ] Android phone (Chrome) — latest + one older (Android 10).
- [ ] iPhone (Safari) — latest iOS + one older.
- [ ] Small screen (≤360px) and large/tablet.
- [ ] Slow network / Render cold start (~1 min) shows the "waking up" hint.

## 10. Security & privacy
- [ ] No secrets in the client bundle or git; `.env` excluded from the Docker image.
- [ ] `DEV_PLAN_KEY` **unset in production** once payments + voice bank are configured (disables admin/test endpoints).
- [ ] HTTPS only; cookies/tokens in localStorage only over TLS.
- [ ] Delete-my-data path works (account + cloned voice).
- [ ] Privacy policy reachable from the app and store listing.

## Sign-off
Tester: __________  Date: ______  Build/digest: ______  Result: ☐ Ship ☐ Hold
