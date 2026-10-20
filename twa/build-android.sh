#!/bin/bash
# Build the EYEWAZ TWA bundle for Google Play.
#
# There are two traps here, and both fail silently. The build succeeds either way,
# the AAB looks fine, and you only find out at upload or from a crash report.
#
# TRAP 1, the target SDK. Bubblewrap 1.24.1 writes "targetSdkVersion 35" into the
# generated app/build.gradle. Play has refused anything below 36 since 31 August
# 2026, so the floor is enforced below and then read back out of the artefact that
# actually ships rather than out of gradle.
#
# TRAP 2, the generated project is hand-edited. app/src/main/java holds real fixes
# that Bubblewrap did not write and will happily destroy: the launch crash fallback
# in LauncherActivity, the edge to edge inset handling in Application, the proguard
# rules, shrinkResources and androidbrowserhelper 2.7.4. "bubblewrap update" reverts
# the lot. So does "bubblewrap build" on its own, because it compares twa-manifest.json
# against manifest-checksum.txt and regenerates the project when they differ, which it
# offers to do with the default answer set to yes. This script refreshes that checksum
# first so the build never asks, and checks the edits are still there before building.
#
# Usage:
#   ./build-android.sh           build, with both guards
#   ./build-android.sh --update  re-run bubblewrap update first. This WILL revert the
#                                hand edits; restore them with "git restore twa/app/"
#                                and re-apply whatever the manifest change needed.
set -euo pipefail

REQUIRED_TARGET_SDK=36

cd "$(dirname "$0")"

# ---- preconditions -------------------------------------------------------
[ -f twa-manifest.json ]     || { echo "FAIL: no twa-manifest.json here"; exit 1; }
[ -f android.keystore ]      || { echo "FAIL: twa/android.keystore is missing (gitignored, restore it from your backup)"; exit 1; }
[ -f keystore-password.txt ] || { echo "FAIL: twa/keystore-password.txt is missing (gitignored, restore it from your backup)"; exit 1; }

# bubblewrap build reads both of these rather than prompting.
BUBBLEWRAP_KEYSTORE_PASSWORD="$(head -n1 keystore-password.txt)"
BUBBLEWRAP_KEY_PASSWORD="$BUBBLEWRAP_KEYSTORE_PASSWORD"
export BUBBLEWRAP_KEYSTORE_PASSWORD BUBBLEWRAP_KEY_PASSWORD

PKG=$(python3 -c 'import json;print(json.load(open("twa-manifest.json"))["packageId"])')
VC=$(python3 -c 'import json;print(json.load(open("twa-manifest.json"))["appVersionCode"])')
VN=$(python3 -c 'import json;print(json.load(open("twa-manifest.json"))["appVersion"])')
echo "Building $PKG  version $VN  code $VC"

if [ "${1:-}" = "--update" ]; then
  echo "WARNING: bubblewrap update reverts the hand edits in app/src and app/build.gradle."
  echo "         Check 'git diff twa/app' afterwards and restore what you still need."
  bubblewrap update --skipVersionUpgrade < /dev/null
fi

# ---- guard 1: the hand edits are still in place --------------------------
# If these have gone, someone ran an update and did not put them back. Building now
# would quietly ship an app without the launch crash fix.
fail_reverted() {
  echo "FAIL: $1"
  echo "      The generated project has been reverted to Bubblewrap's template."
  echo "      Restore it with:  git restore twa/app/"
  exit 1
}
grep -q 'shrinkResources true' app/build.gradle \
  || fail_reverted "shrinkResources is missing from app/build.gradle"
grep -q 'androidbrowserhelper:2.7.4' app/build.gradle \
  || fail_reverted "androidbrowserhelper is not pinned to 2.7.4 in app/build.gradle"
[ -f app/proguard-rules.pro ] \
  || fail_reverted "app/proguard-rules.pro has gone"
grep -q 'give up politely instead of crashing' app/src/main/java/ai/wajd/eyewaz/LauncherActivity.java \
  || fail_reverted "the launch crash fallback has gone from LauncherActivity.java"
grep -q 'setOnApplyWindowInsetsListener' app/src/main/java/ai/wajd/eyewaz/Application.java \
  || fail_reverted "the edge to edge inset handling has gone from Application.java"
echo "Hand edits present: launch crash fallback, inset handling, proguard, browserhelper 2.7.4"

# Keep this in step with twa-manifest.json so the build does not offer to regenerate
# the project, which is how the edits above get lost in the first place.
shasum -a 1 twa-manifest.json | cut -d' ' -f1 | tr -d '\n' > manifest-checksum.txt

# ---- guard 2: the target SDK floor ---------------------------------------
# Fail loudly if the line is not where we expect it: that means Bubblewrap changed its
# output and this guard has quietly stopped guarding anything.
GRADLE=app/build.gradle
grep -qE '^[[:space:]]*targetSdkVersion [0-9]+' "$GRADLE" || {
  echo "FAIL: no targetSdkVersion line in $GRADLE. Bubblewrap's output has changed; fix this script before shipping."
  exit 1
}
CURRENT=$(grep -oE '^[[:space:]]*targetSdkVersion [0-9]+' "$GRADLE" | grep -oE '[0-9]+')
if [ "$CURRENT" -lt "$REQUIRED_TARGET_SDK" ]; then
  echo "Raising targetSdkVersion $CURRENT -> $REQUIRED_TARGET_SDK (Bubblewrap wrote $CURRENT, Play requires $REQUIRED_TARGET_SDK)"
  sed -i '' -E "s/^([[:space:]]*)targetSdkVersion [0-9]+/\1targetSdkVersion $REQUIRED_TARGET_SDK/" "$GRADLE"
  sed -i '' -E "s/^([[:space:]]*)compileSdkVersion [0-9]+/\1compileSdkVersion $REQUIRED_TARGET_SDK/" "$GRADLE"
else
  echo "targetSdkVersion is $CURRENT, at or above the required $REQUIRED_TARGET_SDK"
fi

# ---- build ---------------------------------------------------------------
# No stdin on purpose: if this ever stops to ask something it should fail here rather
# than hang, and rather than quietly regenerate the project we just checked.
bubblewrap build < /dev/null

# ---- verify the artefacts, not the gradle file ---------------------------
AAPT2=$(ls -d "$HOME"/Library/Android/sdk/build-tools/*/aapt2 2>/dev/null | sort -V | tail -n1)
if [ -n "$AAPT2" ] && [ -f app-release-signed.apk ]; then
  APK_TARGET=$("$AAPT2" dump badging app-release-signed.apk | grep -oE "targetSdkVersion:'[0-9]+'" | grep -oE '[0-9]+')
  echo "APK targetSdkVersion: $APK_TARGET"
  [ "$APK_TARGET" -ge "$REQUIRED_TARGET_SDK" ] || { echo "FAIL: the built APK targets $APK_TARGET, Play requires $REQUIRED_TARGET_SDK"; exit 1; }
  # A location permission would make location hardware required and silently drop
  # every device without it, so nothing beyond faketouch should be required here.
  REQUIRED_FEATURES=$("$AAPT2" dump badging app-release-signed.apk | grep -c "^uses-feature:" || true)
  [ "$REQUIRED_FEATURES" -le 1 ] || { echo "FAIL: the APK requires hardware features beyond faketouch, which costs you devices:"; "$AAPT2" dump badging app-release-signed.apk | grep "^uses-feature:"; exit 1; }
fi

# The AAB keeps its manifest as protobuf, so aapt2 cannot read it. Pull the values
# straight out of the bundle, because this file is the one Play actually receives.
python3 - <<'PY'
import re, sys, zipfile

REQUIRED = 36
raw = zipfile.ZipFile('app-release-bundle.aab').read('base/manifest/AndroidManifest.xml')
text = raw.decode('latin-1')


def value_after(name):
    # In the proto manifest each attribute is stored as its name followed by the
    # string form of its value, so read the first short token after the name.
    m = re.search(re.escape(name) + r'.{0,4}?([0-9][0-9.]{0,9})', text, re.S)
    return m.group(1) if m else None


target = value_after('targetSdkVersion')
print('AAB targetSdkVersion:', target)
print('AAB versionCode:', value_after('versionCode'), ' versionName:', value_after('versionName'))
if target is None or int(target) < REQUIRED:
    sys.exit(f'FAIL: the bundle targets {target}, Play requires {REQUIRED}')
PY

echo
echo "Built: $(pwd)/app-release-bundle.aab"
ls -la app-release-bundle.aab
echo "Upload this to Play Console, and promote it to EVERY track that still holds an older release."
