# EYEWAZ — packaging for the App Store & Play Store (Capacitor)

The web app is the single source of truth. **Capacitor** wraps it in a native
iOS + Android shell so it can be published to both stores — no rewrite. The
admin/voice-bank stays web-only (use eyewaz.com in a browser); the store apps are
the user-facing reader.

> What only **you** can do: create the developer accounts, build/sign on a Mac
> (iOS), and submit. I can't enter credentials or publish. Everything else is
> scaffolded in `mobile/`.

## Prerequisites
- Node 18+, then `npm i -g @capacitor/cli`.
- **Android:** Android Studio + a Google **Play Console** account ($25 one-time).
- **iOS:** a **Mac with Xcode** + an **Apple Developer** account ($99/yr).
- The site live at **https://eyewaz.com** with valid HTTPS (see Domain below).

## v1 packaging — load the live site (fastest, robust)
`mobile/capacitor.config.json` uses `server.url = https://eyewaz.com/app`, so the
native app loads the live PWA (relative URLs + the service worker's offline cache
just work). Native value beyond a plain web view: **local notifications** for
reminders (fire even when the app is closed) and biometric unlock.

```bash
cd mobile
npm install
npx cap add ios
npx cap add android
npx cap sync
npx cap open android     # build & run in Android Studio
npx cap open ios         # build & run in Xcode (Mac)
```

### Make reminders native (fire when app closed)
Currently reminders fire while the app is open (browser timer). In the store app,
schedule them with `@capacitor/local-notifications` so they alert in the
background. Bridge: in the web app, when running inside Capacitor
(`window.Capacitor`), call `LocalNotifications.schedule(...)` instead of the JS
timer. (Small follow-up in `Reminders` — ask and I'll wire it.)

## v2 (optional later) — fully bundled offline app
Copy `webapp/` into `mobile/www`, drop `server.url`, and point API calls at the
absolute backend (`https://eyewaz.com/api`, CORS already open). Better offline,
but needs the relative `/api` + `/files` URLs made absolute. Defer unless a store
review asks for more offline capability.

## Store icons & splash
Generate native icon/splash sets from the brand mark:
```bash
npm i -g @capacitor/assets
# put a 1024x1024 icon at mobile/assets/icon.png and a 2732x2732 splash
npx capacitor-assets generate
```
Source art: `webapp/assets/icon-512.png` (scale to 1024) and `eyewaz-favicon.png`.

## Native permissions (Info.plist / AndroidManifest)
Declare and justify (see store kit): **Camera** (read printed text), **Microphone**
(voice commands / Ask Eyewaz), **Notifications** (reminders). iOS needs usage
strings: `NSCameraUsageDescription`, `NSMicrophoneUsageDescription`.

## Domain (eyewaz.com)
Point `eyewaz.com` (and `www`) DNS at the Render service (CNAME/ALIAS), add the
custom domain in Render, let it issue TLS. Update any absolute URLs to
`https://eyewaz.com`. The PayPal/Stripe webhooks and PWA `start_url` then use it.

## Release flow each version
1. Pass `docs/QA-REGRESSION.md` (all blockers green) on web.
2. Bump `CACHE` in `webapp/sw.js`; deploy web (Render).
3. `npx cap sync`; bump version/build numbers; build signed binaries.
4. Upload to Play Console (internal testing → production) and App Store Connect
   (TestFlight → review). Fill the listings from `docs/STORE-SUBMISSION.md`.
