#!/bin/bash
# MyGym: an encrypted copy of the server's data folder (workouts, motion files, heart rate,
# profiles and passkeys), kept for 30 days. The reports are left out: they are made again from the data.
#
#   scripts/backup-data.sh             one backup now
#   scripts/backup-data.sh --install   one every day at 03:00 (a LaunchAgent)
#   scripts/backup-data.sh --remove    stop the daily backup
#   scripts/backup-data.sh --restore <file.enc> <folder>   unpack a backup into an empty folder
#
# Where: MYGYM_BACKUP_DIR in scripts/ios/local.env (not committed); without it, iCloud Drive's
# MyGym-backup folder when iCloud Drive is on, else ~/MyGym-backup.
# The key: ~/.config/mygym/backup.key, made on the first run. Without it no backup can be opened:
# keep a copy somewhere else (a password manager).
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
[ -f "$ROOT/scripts/ios/local.env" ] && . "$ROOT/scripts/ios/local.env"
ICLOUD="$HOME/Library/Mobile Documents/com~apple~CloudDocs"
if [ -z "${MYGYM_BACKUP_DIR:-}" ]; then
  if [ -d "$ICLOUD" ]; then MYGYM_BACKUP_DIR="$ICLOUD/MyGym-backup"; else MYGYM_BACKUP_DIR="$HOME/MyGym-backup"; fi
fi
DATA=${MYGYM_DATA:-$ROOT/data}
KEY="$HOME/.config/mygym/backup.key"
LABEL=com.rippuhonwan.mygym.backup
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
KEEP_DAYS=30

case "${1:-}" in
  --install)
    mkdir -p "$HOME/Library/LaunchAgents" "$HOME/Library/Logs/MyGym"
    cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyLists-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key><array><string>$ROOT/scripts/backup-data.sh</string></array>
  <key>StartCalendarInterval</key><dict><key>Hour</key><integer>3</integer><key>Minute</key><integer>0</integer></dict>
  <key>StandardOutPath</key><string>$HOME/Library/Logs/MyGym/backup.log</string>
  <key>StandardErrorPath</key><string>$HOME/Library/Logs/MyGym/backup.log</string>
</dict></plist>
EOF
    launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
    launchctl bootstrap "gui/$(id -u)" "$PLIST"
    echo "Daily backup at 03:00 into $MYGYM_BACKUP_DIR."
    exit 0 ;;
  --remove)
    launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
    rm -f "$PLIST"
    echo "Daily backup stopped."
    exit 0 ;;
  --restore)
    file=${2:?the backup file}; dest=${3:?an empty folder to unpack into}
    mkdir -p "$dest"
    [ -z "$(ls -A "$dest")" ] || { echo "$dest is not empty."; exit 1; }
    openssl enc -d -aes-256-cbc -pbkdf2 -pass "file:$KEY" -in "$file" | tar xzf - -C "$dest"
    echo "Unpacked into $dest/data. Stop the server before you put it in place of $DATA."
    exit 0 ;;
esac

[ -d "$DATA" ] || { echo "No data folder at $DATA."; exit 1; }
if [ ! -f "$KEY" ]; then
  mkdir -p "$(dirname "$KEY")"
  (umask 077; openssl rand -base64 48 > "$KEY")
  echo "A new backup key is in $KEY. Keep a copy of it somewhere else: without it no backup opens."
fi
mkdir -p "$MYGYM_BACKUP_DIR"
out="$MYGYM_BACKUP_DIR/mygym-data-$(date +%Y%m%d-%H%M).tar.gz.enc"
# ponytail: a full copy each day (the data is a few MB); incremental only if it grows large.
tar czf - -C "$(dirname "$DATA")" --exclude "$(basename "$DATA")/reports" "$(basename "$DATA")" \
  | openssl enc -aes-256-cbc -pbkdf2 -salt -pass "file:$KEY" -out "$out.part"
mv "$out.part" "$out"
find "$MYGYM_BACKUP_DIR" -name 'mygym-data-*.tar.gz.enc' -mtime +$KEEP_DAYS -delete
echo "Backup: $out ($(du -h "$out" | cut -f1))"
