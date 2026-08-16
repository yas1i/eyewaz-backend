# Releasing the EYEWAZ Urdu voice (NVDA add-on + Windows/SAPI installer)

One-time setup, then every release is: push a tag, wait for CI, publish.

## One-time GitHub setup

1. **Upload the voices asset.** The trained voices are too big for the repo. Create
   a release (or any stable URL) holding `eyewaz-voices-v1.zip` (the zip of the two
   `.onnx` + `.onnx.json` files; a copy is in `~/Downloads` on the build Mac).
   Simplest: `gh release create voices-v1 ~/Downloads/eyewaz-voices-v1.zip
   --title "Voice models v1" --notes "Trained Urdu voices used by CI builds."`
2. **Repo secrets** (Settings > Secrets and variables > Actions):
   - `VOICES_URL` = the direct download URL of that zip, e.g.
     `https://github.com/yas1i/eyewaz-backend/releases/download/voices-v1/eyewaz-voices-v1.zip`
   - `SIGN_PFX_BASE64` + `SIGN_PASSWORD` = the Authenticode cert (base64 of the
     .pfx) and its password. Without these the build still runs but the installer
     is UNSIGNED - fine for internal testing, not for public release.

## Every release

1. Commit, then tag and push:
   ```bash
   cd "/Users/wajd/Documents/WAJD Projects/eyewaz-backend-main" && git tag v1.0.0 && git push origin main v1.0.0
   ```
   NOTE: pushing `main` also auto-deploys the WEB APP to Render (the /voice page
   ships with it). The tag additionally runs `.github/workflows/build-voice.yml`,
   which builds on an x64 runner and attaches to the GitHub release:
   - `EyewazUrduVoiceSetup.exe` (signed if secrets set)
   - `EyewazUrdu-<ver>.nvda-addon` and the fixed-name `EyewazUrdu.nvda-addon`
2. **Test before announcing** on real x64 Windows 10 and 11: install, pick the
   voice in NVDA + Narrator (and JAWS where available), listen, uninstall.
3. The eyewaz.com links need no change: `/download/nvda-voice` and
   `/download/windows-voice` redirect to `releases/latest/download/...`.
4. NVDA Add-on Store: follow `nvda-addon/STORE-SUBMISSION.md` (new version = one
   more small JSON PR pointing at the new release asset).

## Release notes template (paste into the GitHub release)

```
EYEWAZ Urdu Voice v1.0.0

A free, natural Urdu voice for Windows screen readers, trained on real WAJD
voices. Fully offline: nothing you read leaves your computer.

What is in this release
- NVDA add-on (EyewazUrdu.nvda-addon): female and male Urdu voices inside NVDA.
- Windows installer (EyewazUrduVoiceSetup.exe): adds "EYEWAZ Urdu (Female)" and
  "EYEWAZ Urdu (Male)" to Windows speech, for JAWS, Narrator, Word Read Aloud
  and any SAPI application. Includes word tracking and starts automatically at
  logon. 64 bit Windows 10 and 11.

Install guide: https://www.eyewaz.com/voice
Support: support@eyewaz.com
```

## Cert notes (for the SIGN_* secrets)
- Certum Open Source code signing (~£90/yr, USB token) or Azure Trusted Signing
  (~$10/mo, cloud; swap the signtool step for the azure/trusted-signing-action).
- Sign under WAJD AI Ltd. Both the setup.exe and EyewazTts.dll get signed by CI.
