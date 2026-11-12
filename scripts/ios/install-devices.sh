#!/bin/bash
# MyGym: build the iPhone app (with its Apple Watch app and widgets inside) and install it on the
# paired iPhone, then the watch app on the Apple Watch (docs/dev/rep-counter.md, install rule).
# A free Apple ID signs for 7 days: run this again before the profiles expire.
#
#   scripts/ios/install-devices.sh                    build if needed, install both
#   scripts/ios/install-devices.sh --renew            new signing profiles first (7 more days)
#   scripts/ios/install-devices.sh --build-only       build and show the expiry, install nothing
#   scripts/ios/install-devices.sh --install-reminder daily check, a notification 2 days before expiry
#
# Needs: Xcode signed in to the Apple ID, the generated project (ci/add-watch-app.rb,
# ci/add-widgets.rb), and scripts/ios/local.env (not committed) with:
#   MYGYM_TEAM=<TEAM_ID>
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/../.." && pwd)
APP_DIR="$ROOT/frontend/ios/App"
PRODUCT="$APP_DIR/build/dd-device/Build/Products/Debug-iphoneos/App.app"
# Outside build/: cap sync cleans that folder.
LOGS="$HOME/Library/Logs/MyGym"
PROFILES="$HOME/Library/Developer/Xcode/UserData/Provisioning Profiles"
[ -f "$ROOT/scripts/ios/local.env" ] && . "$ROOT/scripts/ios/local.env"
BUNDLE=${MYGYM_BUNDLE:-com.rippuhonwan.mygym}

renew=0; build_only=0
for a in "$@"; do
  case "$a" in
    --renew) renew=1 ;;
    --build-only) build_only=1 ;;
    --install-reminder) exec "$ROOT/scripts/ios/profile-reminder.sh" --install ;;
    *) echo "unknown option: $a"; exit 2 ;;
  esac
done
: "${MYGYM_TEAM:?Put MYGYM_TEAM=<your Apple team id> in scripts/ios/local.env}"
mkdir -p "$LOGS"
say() { printf '\n== %s\n' "$*"; }

# Expiry of a signing profile file, as YYYY-MM-DD HH:MM (local time).
expiry() {
  local d
  d=$(security cms -D -i "$1" 2>/dev/null | plutil -extract ExpirationDate raw - 2>/dev/null) || return 1
  date -r "$(TZ=UTC date -j -f '%Y-%m-%dT%H:%M:%SZ' "$d" +%s)" '+%Y-%m-%d %H:%M'
}
# Days until a profile file expires (whole days, may be negative).
days_left() {
  local d
  d=$(security cms -D -i "$1" 2>/dev/null | plutil -extract ExpirationDate raw - 2>/dev/null) || { echo -99; return; }
  echo $(( ( $(TZ=UTC date -j -f '%Y-%m-%dT%H:%M:%SZ' "$d" +%s) - $(date +%s) ) / 86400 ))
}
# This app's cached profiles (main app, watch app, both widget extensions).
our_profiles() {
  local f id
  for f in "$PROFILES"/*.mobileprovision; do
    [ -f "$f" ] || continue
    id=$(security cms -D -i "$f" 2>/dev/null | plutil -extract Entitlements.application-identifier raw - 2>/dev/null) || continue
    case "$id" in *."$BUNDLE"|*."$BUNDLE".*) echo "$f" ;; esac
  done
}

# 1. Signing: renew when asked, or when a profile has less than 3 days left.
if [ $renew = 0 ]; then
  while IFS= read -r f; do
    [ -n "$f" ] && [ "$(days_left "$f")" -lt 3 ] && renew=1
  done < <(our_profiles)
fi
if [ $renew = 1 ]; then
  say "Renewing the signing profiles (Xcode makes new ones in the build)"
  # ponytail: relies on xcodebuild -allowProvisioningUpdates creating a fresh 7-day profile when
  # none is cached; if Apple ever refuses, open the project in Xcode once and build there.
  our_profiles | while IFS= read -r f; do rm -f "$f"; done
fi

# 2. The web app inside the iPhone app: rebuilt only when the frontend changed since.
if [ -n "$(find "$ROOT/frontend/src" "$ROOT/frontend/index.html" "$ROOT/frontend/public" -newer "$APP_DIR/App/public/index.html" -type f ! -name '*.test.*' -print -quit 2>/dev/null)" ] \
   || [ ! -f "$APP_DIR/App/public/index.html" ]; then
  say "Building the web app (frontend changed)"
  mkdir -p "$APP_DIR/build"
  # cap sync's xcodebuild clean refuses a build folder it did not make without this mark.
  xattr -w com.apple.xcode.CreatedByBuildSystem true "$APP_DIR/build"
  (cd "$ROOT/frontend" && LANG=en_US.UTF-8 LC_ALL=en_US.UTF-8 npm run build:mobile) > "$LOGS/build-mobile.log" 2>&1 || {
    # pod install sometimes fails after the web copy already happened; the check below decides.
    echo "build:mobile reported an error (see $LOGS/build-mobile.log)"
  }
  [ "$APP_DIR/App/public/index.html" -nt "$ROOT/frontend/index.html" ] || { echo "The web app was not copied into the iPhone app."; exit 1; }
else
  say "Web app unchanged"
fi

# 3. The iPhone app, with the watch app and the widgets inside.
say "Building the app (a few minutes)"
(cd "$APP_DIR" && xcodebuild -workspace App.xcworkspace -scheme App -destination 'generic/platform=iOS' \
  -derivedDataPath build/dd-device -allowProvisioningUpdates DEVELOPMENT_TEAM="$MYGYM_TEAM" build) > "$LOGS/xcodebuild.log" 2>&1 || {
  grep -E 'error:' "$LOGS/xcodebuild.log" | sort -u | head -8
  echo "Build failed. Full log: $LOGS/xcodebuild.log"
  exit 1
}
say "Signed until"
for p in "$PRODUCT" "$PRODUCT/Watch/OpenGymWatch.app" "$PRODUCT"/PlugIns/*.appex; do
  [ -f "$p/embedded.mobileprovision" ] && printf '  %-28s %s\n' "$(basename "$p")" "$(expiry "$p/embedded.mobileprovision")"
done
[ $build_only = 1 ] && exit 0

# 4. The devices: the paired iPhone and Apple Watch (the first of each).
devices=$(xcrun devicectl list devices --json-output /dev/stdout 2>/dev/null | python3 -c '
import json, sys
d = json.load(sys.stdin)["result"]["devices"]
real = [x for x in d if x["hardwareProperties"].get("reality") == "physical"]
for kind in ("iPhone", "appleWatch"):
    m = [x["hardwareProperties"]["udid"] for x in real if x["hardwareProperties"]["deviceType"] == kind]
    print(m[0] if m else "")')
PHONE=$(echo "$devices" | sed -n 1p); WATCH=$(echo "$devices" | sed -n 2p)
[ -n "$PHONE" ] || { echo "No paired iPhone found (same Wi-Fi as this Mac, or a cable)."; exit 1; }
[ -n "$WATCH" ] || { echo "No paired Apple Watch found."; exit 1; }

# The iPhone must be unlocked, or the developer disk image cannot mount.
for i in $(seq 1 30); do
  xcrun devicectl device info lockState --device "$PHONE" 2>/dev/null | grep -q 'passcodeRequired: false' && break
  [ $i = 1 ] && say "Unlock the iPhone and keep its screen on"
  sleep 2
done

install() { # device, app, name
  local out
  for i in 1 2 3 4 5; do
    if out=$(xcrun devicectl device install app --device "$1" "$2" 2>&1) && echo "$out" | grep -q 'App installed'; then
      echo "  $3: installed"; return 0
    fi
    echo "  $3: try $i failed ($(echo "$out" | grep -m1 -iE 'error|locked' | cut -c1-90)), retrying"
    sleep 6
  done
  echo "  $3: not installed. Keep the iPhone unlocked and the watch on its charger, then run this again."
  return 1
}
# Order matters: the watch app copy embedded in the iPhone app, after the iPhone app.
say "Installing"
install "$PHONE" "$PRODUCT" iPhone
install "$WATCH" "$PRODUCT/Watch/OpenGymWatch.app" "Apple Watch"
# What is now on the devices, for the reminder: the earliest expiry, seconds since 1970.
for p in "$PRODUCT" "$PRODUCT/Watch/OpenGymWatch.app" "$PRODUCT"/PlugIns/*.appex; do
  d=$(security cms -D -i "$p/embedded.mobileprovision" 2>/dev/null | plutil -extract ExpirationDate raw - 2>/dev/null) || continue
  TZ=UTC date -j -f '%Y-%m-%dT%H:%M:%SZ' "$d" +%s
done | sort -n | head -1 > "$LOGS/installed-until"
say "Done. Open MyGym on the watch by hand once, then on the iPhone."
