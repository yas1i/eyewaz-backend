# EYEWAZ — App Store & Play Store submission kit

## Listing copy
**Name:** EYEWAZ — See better. Live better.
**Subtitle / short:** Hear any text read aloud, in Urdu & more.
**Full description:**
> EYEWAZ turns the written world into spoken words. Photograph printed text,
> upload a document or PDF, paste a web link, or type — EYEWAZ reads it aloud in
> Urdu and many languages, with regional Pakistani dialects. Built for blind and
> low-vision users: large controls, full screen-reader support, and a voice
> assistant that helps you start your day, set spoken medication reminders, and
> keep a personal library you can replay offline.
>
> • Read photos, documents, web pages and text aloud
> • Urdu plus regional dialects; many world languages
> • Ask EYEWAZ — a friendly voice assistant
> • Spoken reminders for medicine, prayers, appointments
> • Save recordings into folders and replay offline
> • Fast, accessible sign-in with Face ID / fingerprint

**Keywords:** text to speech, screen reader, blind, low vision, Urdu, OCR, read aloud, accessibility, dyslexia, audiobook.
**Category:** primary **Education** (or Productivity); secondary Utilities. Mark as Accessibility.
**Support URL:** https://eyewaz.com  · **Marketing URL:** https://eyewaz.com  · **Privacy policy URL:** https://eyewaz.com/privacy

## Screenshots (capture on device; both stores need them)
1. My Day (greeting + Start my day) 2. Photo → reading 3. My Library cards
4. Ask Eyewaz 5. Dialect picker 6. Reminders. Provide Android phone set and
iPhone 6.7"/6.5"/5.5" sets (App Store) + Play 1080×1920+ set. Use real,
high-contrast UI; add a one-line caption per shot.

## Permissions — declare AND justify (reviewers check)
| Permission | Why | Strings |
|---|---|---|
| Camera | Photograph printed text to read aloud (OCR) | iOS `NSCameraUsageDescription`: "EYEWAZ uses the camera to photograph text and read it aloud." |
| Microphone | Voice commands & Ask EYEWAZ | iOS `NSMicrophoneUsageDescription`: "EYEWAZ uses the microphone for voice commands." |
| Notifications | Spoken/medication reminders | Request at first reminder; explain in-app. |

## Google Play — Data safety form
- **Collected:** name, email, phone (account); audio (mic, for commands — processed, see policy); photos/files (to read — not stored beyond your library, on-device); usage counts. Payment handled by PayPal/Stripe (not collected by us).
- **Shared with:** processors only (Microsoft Azure, Anthropic, ElevenLabs, SendGrid, PayPal/Stripe) to provide the service. No data sold.
- **Security:** encrypted in transit (HTTPS); users can request deletion.
- **Account deletion URL** required: provide an in-app + web path.

## Apple — App Privacy ("nutrition label")
Declare data types: Contact Info (email/name/phone), User Content (photos/audio/text — used to provide the feature), Identifiers, Usage Data. Linked to identity for the account; not used for tracking. No third-party advertising/tracking SDKs.

## Apple review notes (avoid common rejections)
- **4.2 minimum functionality:** the app adds native value beyond a web view —
  local notifications (background reminders), biometric unlock, camera capture.
  State this in Review Notes.
- **Sign in with Apple:** if you offer Google/Facebook social login, Apple
  requires offering **Sign in with Apple** too. Either add it or disable third-
  party social login in the iOS build.
- **Account deletion** in-app is mandatory (Guideline 5.1.1(v)).
- **IAP vs external payments:** subscriptions for **digital** features normally
  must use Apple **In-App Purchase**, not PayPal/Stripe. Options: (a) add IAP for
  iOS, or (b) keep paid tiers web-only and ship the iOS app as free/no-upsell.
  **Decide before iOS submission** — this is the biggest risk. Android/Play allows
  more flexibility but also generally requires Play Billing for in-app digital goods.

## Pre-submission gate
- [ ] `docs/QA-REGRESSION.md` fully green (esp. accessibility).
- [ ] Privacy policy live at /privacy; deletion path works.
- [ ] Icons/splash/screenshots ready; version + build numbers set.
- [ ] `DEV_PLAN_KEY` unset in production.
- [ ] Decided the iOS payments approach (IAP vs web-only).
