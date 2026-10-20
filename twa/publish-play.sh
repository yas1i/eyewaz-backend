#!/bin/bash
# Upload the built EYEWAZ bundle to Google Play.
#
# Needs a Play service account JSON at twa/play-service-account.json. It is gitignored
# and twa/ is dockerignored, so it stays out of both git and the Render image. That file
# can create releases on the whole developer account, so treat it like the keystore.
# Creating it is a one off, see "Automated uploads" in docs/PLAY-RELEASE.md.
#
# Usage:
#   ./publish-play.sh              upload to the internal track, the default
#   ./publish-play.sh beta         upload to alpha, beta or internal
#   ./publish-play.sh production   upload to production, asks you to confirm first
set -euo pipefail

REQUIRED_TARGET_SDK=36
KEY_FILE="${EYEWAZ_PLAY_KEY:-play-service-account.json}"
TRACK="${1:-internal}"
BUNDLE="app-release-bundle.aab"

cd "$(dirname "$0")"

case "$TRACK" in
  alpha|beta|internal|production) ;;
  *) echo "FAIL: track must be one of alpha, beta, internal, production (got '$TRACK')"; exit 1 ;;
esac

if [ ! -f "$KEY_FILE" ]; then
  cat <<EOF
FAIL: no Play service account key at twa/$KEY_FILE

Create it once, in this order:
  1. Play Console, Setup, API access, and link or create a Google Cloud project.
  2. In that Cloud project: IAM and admin, Service accounts, Create service account,
     then Keys, Add key, Create new key, JSON. The file downloads once.
  3. Back in Play Console, Users and permissions, Invite user, paste the service
     account email, and give it Release permissions for Eyewaz. Without this step
     the key authenticates but every upload returns a permissions error.
  4. Move the downloaded file to:
     $(pwd)/$KEY_FILE
EOF
  exit 1
fi

[ -f "$BUNDLE" ] || { echo "FAIL: no $BUNDLE here. Build it first with ./build-android.sh"; exit 1; }

# Never upload a bundle Play is going to refuse. Read the bundle itself, not gradle.
python3 - "$REQUIRED_TARGET_SDK" <<'PY'
import re, sys, zipfile

required = int(sys.argv[1])
raw = zipfile.ZipFile('app-release-bundle.aab').read('base/manifest/AndroidManifest.xml')
text = raw.decode('latin-1')


def value_after(name):
    m = re.search(re.escape(name) + r'.{0,4}?([0-9][0-9.]{0,9})', text, re.S)
    return m.group(1) if m else None


target = value_after('targetSdkVersion')
print(f"Bundle: version {value_after('versionName')}, code {value_after('versionCode')}, targetSdk {target}")
if target is None or int(target) < required:
    sys.exit(f'FAIL: the bundle targets {target}, Play requires {required}. Rebuild with ./build-android.sh')
PY

# Record the key path in twa-manifest.json on first use only, so repeat runs leave that
# tracked file alone. Passing the flag always would rewrite it on every upload.
SA_ARGS=()
if ! python3 -c 'import json,sys; sys.exit(0 if json.load(open("twa-manifest.json")).get("serviceAccountJsonFile") else 1)'; then
  echo "Recording the key path in twa-manifest.json (one off, commit that one line change)"
  SA_ARGS=(--serviceAccountFile="./$KEY_FILE")
fi

# Catches the common failure before the upload: a version code Play has already seen.
echo "Checking the version against what is already on Play"
# The ${a[@]+"${a[@]}"} form is deliberate: macOS ships bash 3.2, where a plain
# "${a[@]}" on an empty array is an unbound variable error under set -u.
bubblewrap play versionCheck ${SA_ARGS[@]+"${SA_ARGS[@]}"} < /dev/null || {
  echo "FAIL: version check did not pass. If the code is already used, bump appVersionCode in"
  echo "      twa-manifest.json and rebuild with ./build-android.sh before trying again."
  exit 1
}

if [ "$TRACK" = "production" ]; then
  echo
  echo "This uploads to PRODUCTION and goes for review, so real users get it."
  printf "Type 'production' to confirm: "
  read -r CONFIRM < /dev/tty
  [ "$CONFIRM" = "production" ] || { echo "Stopped, nothing was uploaded."; exit 1; }
fi

echo "Uploading $BUNDLE to the $TRACK track"
bubblewrap play publish --track="$TRACK" < /dev/null

echo
echo "Uploaded to $TRACK. Play Console still decides when it goes live:"
echo "  internal, alpha, beta go to testers. production goes for review first."
echo "Remember the target API rule: every track holding an old bundle counts, not just production."
