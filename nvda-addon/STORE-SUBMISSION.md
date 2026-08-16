# Submitting EYEWAZ Urdu to the NVDA Add-on Store

The NVDA Add-on Store is how NVDA users worldwide discover add-ons (Tools →
Add-on Store). Listing is free and needs no code-signing certificate — you submit
a small JSON metadata file by pull request and NV Access reviews it.

## 1. Host the built add-on at a stable URL
Build it (`python build.py`) and upload `EyewazUrdu-<version>.nvda-addon` as a
GitHub Release asset on `yas1i/eyewaz-backend` (or eyewaz.com). The URL must be
permanent — the store points users straight at it.

Get its SHA-256 (the store requires it):
```bash
shasum -a 256 EyewazUrdu-1.0.0.nvda-addon      # macOS/Linux
# certUtil -hashfile EyewazUrdu-1.0.0.nvda-addon SHA256   (Windows)
```

## 2. Confirm the manifest is store-ready
`addon/manifest.ini` already has the required fields. Two to double-check before
submitting:
- `minimumNVDAVersion` / `lastTestedNVDAVersion` — bump `lastTested` to the NVDA
  version you actually tested on.
- A stable `name` (addonId) — ours is `eyewazUrdu`; never change it once listed.

## 3. Pick a licence
NVDA add-ons are almost always **GPL v2** (NVDA itself is GPL). The bundled
espeak-ng is GPL v3 and piper.exe is MIT, so GPL v2-or-later for the add-on is the
clean choice. Add a `LICENSE` file and state it in the submission.

## 4. Submit the metadata PR
Fork **`nvaccess/addon-datastore`** and add one file:
`addons/eyewazUrdu/<versionNumber>.json`, e.g. `addons/eyewazUrdu/1.0.0.json`:

```json
{
  "addonId": "eyewazUrdu",
  "displayName": "EYEWAZ Urdu Voice",
  "publisher": "WAJD AI",
  "description": "Natural, fully offline Urdu text-to-speech for NVDA. Female and male voices trained on real WAJD voices; no internet, no per-character cost.",
  "homepage": "https://www.eyewaz.com",
  "addonVersionName": "1.0.0",
  "addonVersionNumber": { "major": 1, "minor": 0, "patch": 0 },
  "minNVDAVersion": { "major": 2021, "minor": 1, "patch": 0 },
  "lastTestedVersion": { "major": 2026, "minor": 1, "patch": 0 },
  "channel": "stable",
  "URL": "https://github.com/yas1i/eyewaz-backend/releases/download/v1.0.0/EyewazUrdu-1.0.0.nvda-addon",
  "sha256": "<paste the SHA-256 from step 1>",
  "sourceURL": "https://github.com/yas1i/eyewaz-backend",
  "license": "GPL v2",
  "licenseURL": "https://www.gnu.org/licenses/old-licenses/gpl-2.0.html"
}
```

Open the PR against `nvaccess/addon-datastore`. Their validation bot checks the
JSON and the download hash; a reviewer then approves. Once merged, the add-on
appears in every NVDA user's Add-on Store within a day.

## 5. Updates later
Each new version is just another `addons/eyewazUrdu/<newversion>.json` PR pointing
at the new release asset. Users get an "update available" prompt automatically.

## Notes
- Keep `addonId` = `eyewazUrdu` forever; it's the identity the store tracks.
- The store distributes the add-on as-is (no Authenticode). Signing only matters
  for the separate SAPI installer (JAWS), not for NVDA.
