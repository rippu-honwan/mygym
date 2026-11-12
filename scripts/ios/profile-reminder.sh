#!/bin/bash
# MyGym: a macOS notification when the installed build's signing ends within 2 days (free Apple
# ID: 7 days). Reads what scripts/ios/install-devices.sh last installed.
#
#   scripts/ios/profile-reminder.sh            check now
#   scripts/ios/profile-reminder.sh --install  check every day at 10:00 (a LaunchAgent)
#   scripts/ios/profile-reminder.sh --remove   stop the daily check
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/../.." && pwd)
PRODUCT="$ROOT/frontend/ios/App/build/dd-device/Build/Products/Debug-iphoneos/App.app"
LABEL=com.rippuhonwan.mygym.profile-reminder
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"

case "${1:-}" in
  --install)
    mkdir -p "$HOME/Library/LaunchAgents"
    cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyLists-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key><array><string>$ROOT/scripts/ios/profile-reminder.sh</string></array>
  <key>StartCalendarInterval</key><dict><key>Hour</key><integer>10</integer><key>Minute</key><integer>0</integer></dict>
  <key>RunAtLoad</key><true/>
</dict>
</plist>
EOF
    launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
    launchctl bootstrap "gui/$(id -u)" "$PLIST"
    echo "Daily check installed ($PLIST)."
    exit 0 ;;
  --remove)
    launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
    rm -f "$PLIST"
    echo "Daily check removed."
    exit 0 ;;
esac

# What install-devices.sh last put on the devices; without that record, the last build.
first=$(cat "$HOME/Library/Logs/MyGym/installed-until" 2>/dev/null || true)
[ -n "$first" ] || for p in "$PRODUCT" "$PRODUCT/Watch/OpenGymWatch.app" "$PRODUCT"/PlugIns/*.appex; do
  f="$p/embedded.mobileprovision"
  [ -f "$f" ] || continue
  d=$(security cms -D -i "$f" 2>/dev/null | plutil -extract ExpirationDate raw - 2>/dev/null) || continue
  s=$(TZ=UTC date -j -f '%Y-%m-%dT%H:%M:%SZ' "$d" +%s)
  if [ -z "$first" ] || [ "$s" -lt "$first" ]; then first=$s; fi
done
[ -n "$first" ] || exit 0
hours=$(( (first - $(date +%s)) / 3600 ))
when=$(date -r "$first" '+%a %d %b %H:%M')
if [ $hours -le 48 ]; then
  msg="MyGym stops opening on $when. Run scripts/ios/install-devices.sh at home."
  [ $hours -le 0 ] && msg="MyGym signing expired on $when. Run scripts/ios/install-devices.sh at home."
  osascript -e "display notification \"$msg\" with title \"MyGym\" sound name \"Glass\""
  echo "$msg"
else
  echo "Signed until $when ($((hours / 24)) days left)."
fi
