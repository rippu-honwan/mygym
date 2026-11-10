# Rep counter (Apple Watch) - progress

Fork of openGym that adds automatic rep counting on the Apple Watch (CoreMotion).
Read this file first at the start of every session; update it before the session ends.

## Goal (the user, 2026-11-09)

1. iPhone and Apple Watch both record workouts (openGym already does this).
2. The watch counts reps automatically for chosen exercises from the motion data (new).
3. Data is stored as files on the user's Mac, which runs the openGym server (self-hosted `data/`).
4. Claude on the Mac reads that data for analysis (openGym's `mcp/` server, or the files).

## Phases

1. Phase 1: build our app (MyGym) on the real iPhone and Watch.
2. Phase 1b: self-hosted server on the Mac (Colima + Docker, home Wi-Fi first, Tailscale later
   if needed), pair MyGym with it, register `mcp/` with Claude Code.
3. Phase 2: the watch records motion data per set, sent via the iPhone to the server as files.
4. Phase 3: collect data for 2-3 weeks.
5. Phase 4: find the rep-counting algorithm in Python, port it to `WatchCore` with tests.
6. Phase 5: live rep count on the watch, auto-filled reps, synced as normal sets.

The user may keep the App Store openGym for daily logging while testing; one account should only be
paired with one app, so switch to MyGym once it is stable.

## Current phase

**Phase 1** done 2026-11-09: MyGym runs on the real iPhone and watch; routines show on the
watch and a set ticked on the watch shows on the iPhone (the user's check). **Phase 1b** done 2026-11-09: iPhone paired, routines synced to
`data/state-<uid>.json`, MCP `list_routines` returns them.

Phase 0 (environment check) done 2026-11-09.

## Repo setup

- Local clone: `~/dev/mygym` (no spaces in the path, and avoids the case-insensitive clash with
  the old `MyGym` folder, which is the unrelated `maxgym` project).
- `origin` = github.com/rippu-honwan/mygym (full openGym history pushed to `main`).
- `upstream` = github.com/DuarteSantos8/openGym. Push URL set to `DISABLED` so nothing is pushed
  there by mistake.
- Work happens on `feature/rep-counter`. License stays AGPL-3.0; `LICENSE` and `NOTICE.md` are kept.

## Environment (2026-11-09)

| Tool | Installed | openGym needs |
|---|---|---|
| Xcode | 27.1 | 26 (newer, not yet built) |
| Node | 22.18.0 | 22 |
| CocoaPods | 1.17.0 (Homebrew, 2026-11-09) | needed |
| Ruby | 4.0.9 (Homebrew, pulled in by CocoaPods) | - |
| Homebrew | 7.0.10 | - |

Notes from the upstream docs:
- The watch app target is added by `frontend/ios/ci/add-watch-app.rb` (xcodeproj gem), not
  committed in `App.xcodeproj`. Watch needs watchOS 10+.
- `WatchCore` (Swift package, `swift test`) holds the watch logic and tests.
- App Group `group.ch.opengym.app` and bundle ids `ch.opengym.app*` belong to upstream and must be
  renamed for our signing.
- `require 'xcodeproj'` fails with plain `ruby`: the gem lives inside the CocoaPods keg. Run the
  watch script with `GEM_HOME=/opt/homebrew/opt/cocoapods/libexec ruby frontend/ios/ci/add-watch-app.rb`.
- `pod` needs a UTF-8 locale; `~/.zshrc` already sets `LANG=en_US.UTF-8`, so this only matters in
  non-interactive shells.

## Decisions

- 2026-11-09: the deleted files in the old `MyGym` (maxgym) folder were deleted on purpose by the user.
- 2026-11-09: bring openGym in by clone + push into the empty `mygym` repo (not a GitHub fork).
- 2026-11-09: signing uses a **free Apple ID** (Xcode Personal Team). Consequences:
  - The provisioning profile expires after 7 days: re-run from Xcode at least weekly, especially
    during the 2-3 week data collection in Phase 3. Check that re-installing keeps recorded data.
  - Limited number of App IDs per week, so Phase 1 builds only the iPhone app and the Watch app.
    Planned for Phase 1 (local signing changes only): skip the iPhone widgets, the watch widgets
    and AnimationPacksDownloader; drop the Associated Domains and NFC entitlements; rename bundle
    ids and the App Group to our own. HealthKit and App Groups are expected to work on a free
    team but are not verified yet.

- 2026-11-09: GitHub Actions in the fork. Keep `test.yml` and `ios.yml` (ios.yml runs WatchCore
  `swift test` and builds the watch app). Disable in the GitHub UI (no file change):
  `docker-publish.yml`, `pages.yml`, `cla.yml`, `cla-issue.yml`, `audit.yml`. Ignore `mirror.yml`
  (guarded to upstream) and `release-check.yml` (only on `v*` tags). Turn off Dependabot, close
  its 10 PRs, and delete the `opengym-api` / `opengym-web` images that the first push to `main`
  published to ghcr.io.

## Devices

- iPhone 15 Pro, latest iOS (exact version not checked yet).
- Apple Watch: the user said Series 10 45 mm; Xcode reports Apple Watch Series 9 (Watch7,2).
  watchOS 27.0.1, Developer Mode on.

## Phase 2a plan (approved 2026-11-09)

Decisions: first exercise biceps curl (the user's routine: 0031 barbell curl, 0313 dumbbell hammer
curl). Record every exercise that moves the wrist: skip catalogue `bodyPart` "upper legs" /
"lower legs"; unknown (custom) exercises are recorded. 50 Hz. Phase 2 split into 2a (watch ->
iPhone, CSV visible in the Files app) and 2b (iPhone -> Mac server `data/motion/`).

- `WatchCore/MotionLog.swift`: record rule, slice of a time window, CSV encoder; `swift test`.
- `Watch/MotionRecorder.swift`: CMMotionManager deviceMotion at 50 Hz while a workout runs,
  last 5 minutes kept. `SessionStore.completeSet` slices set start -> tick, writes the CSV and
  sends it with `WCSession.transferFile`.
- `bodyPart` added to the watch entry (`Model.swift`, `frontend/src/lib/watch-sync.js`).
- iPhone: `WatchBridgePlugin` stores received files in `Documents/motion/`.
  Changed during build: NO Files app access. Capacitor's `Directory.Data` is the same
  `Documents` folder, so `UIFileSharingEnabled` would also show the app's own data file there
  (easy to delete by mistake). Instead the CSVs are copied to the Mac with devicectl (below);
  2b uploads them.
- Garmin snapshot strips `bodyPart` (memory budget); Wear OS fixture updated (Kotlin parser has
  `ignoreUnknownKeys`).
- CSV: line 1 `# {json metadata}`, then `t,ax,ay,az,rx,ry,rz,gx,gy,gz` (s, g, rad/s, g).

## Open questions

- None right now.

## Upstream files changed

Phase 1 (commit "build: use own bundle ids and app group"):
- Bundle ids `ch.opengym.app` -> `com.rippuhonwan.mygym` (`App.xcodeproj/project.pbxproj`,
  `ci/add-watch-app.rb`, `WKCompanionAppBundleIdentifier` in `Watch/Info.plist`,
  `.github/workflows/ios.yml`).
- App Group `group.ch.opengym.app` -> `group.com.rippuhonwan.mygym` in every entitlements file,
  `App/Info.plist`, `AnimationPacksDownloader/Info.plist`, `WorkoutActivity.swift`,
  `Watch/WidgetState.swift`.
- `App/App.entitlements`: removed Associated Domains and NFC (not available on a free team).
- Not changed: `scripts/ios/finish-ipa.sh` (release only), keychain fallback strings, URL names.

## How to build (every fresh clone or after `npm ci`)

The watch target is not committed in the Xcode project; the upstream script adds it.

```bash
cd ~/dev/mygym/frontend
npm ci
LANG=en_US.UTF-8 npm run build:mobile   # vite build + cap sync + pod install
cd ios
GEM_HOME=/opt/homebrew/opt/cocoapods/libexec ruby ci/add-watch-app.rb
open App/App.xcworkspace                # the .xcworkspace, not the .xcodeproj
```

- `pod install` may fail with `curl: (56) ... 504` on a GitHub release zip. That is GitHub,
  not us: wait a minute and run `pod install` in `frontend/ios/App` again.
- After these steps git shows changes in `project.pbxproj`, `Podfile`, two Android gradle files
  and some untracked files. They are generated: do not commit them.

## Phase 2a status (2026-11-09)

Code committed ("feat: record watch motion per set"); WatchCore 73 tests and frontend
watch-sync/garmin tests pass; signed builds installed on the iPhone and the watch. Not yet
verified on a real workout.

### The user's test

1. Watch: MyGym settings > Apple Health must be ON (the workout session keeps the app and the
   motion sensor running with the wrist down).
2. Start Upper A (has 0031 barbell curl) on the iPhone or the watch. Do 2 sets of barbell curl
   and 1 set of any leg exercise, ticking each set ON THE WATCH with the real rep count.
3. Finish the workout, open MyGym on the iPhone and keep it open for ~30 s.
4. Tell Claude. Claude copies the CSVs to the Mac:
   `xcrun devicectl device copy from --device <iPhone UDID> --domain-type appDataContainer
   --domain-identifier com.rippuhonwan.mygym --source Documents/motion --destination data/motion-phone`
   and checks: curl sets present, leg set absent, ~50 rows/s, reps visible in a plot.

### Problem found 2026-11-11: iPhone and watch stopped syncing

After the 2a reinstall (iPhone app by devicectl, then the watch app by devicectl straight onto
the watch) MyGym > Settings > Apple Watch said "openGym is not on your Apple Watch yet":
WatchConnectivity reports `isWatchAppInstalled = false`, so the phone sends nothing. The user deleted
the watch app and tapped Install in the iPhone Watch app: nothing happened. Checked: the embedded
and the standalone watch app are both signed with a profile that lists the watch UDID and the
App Group (valid to 2026-11-16), so signing is not the cause. Suspect the iPhone's companion
record got confused by two separate installs. Restarting both devices did not help.
RESOLVED 2026-11-11 at home: reinstalled the iPhone app (devicectl); the iPhone did NOT install
the watch app by itself within 90 s; then installed the watch app copy EMBEDDED in the iPhone app
(`App.app/Watch/OpenGymWatch.app`) straight onto the watch, the user opened it on the watch by hand
(remote launch is refused while the watch sits on the clock face), and the iPhone's Apple Watch
page says installed again; starting Upper A on the iPhone opens it on the watch (the user, 2026-11-11). Likely cause (not proven): in 2a the watch got the separately built
`build/dd-watch` copy, not the one inside the iPhone app.

Rule from now on: install the iPhone app, then the embedded watch app, then open MyGym on the
watch by hand:
`xcrun devicectl device install app --device <watch UDID>
build/dd-device/Build/Products/Debug-iphoneos/App.app/Watch/OpenGymWatch.app`.
Keep the iPhone unlocked (screen on) during installs, or the developer disk image cannot mount.

### First real data (2026-11-11)

Copied with devicectl to `data/motion-phone/` (git-ignored):
- `20261111-043812_0025_s1.csv` (bench press, the user's quick simulation, 8 reps logged): 2200 rows,
  44.2 s, 49.7 Hz, max gap 0.021 s, `bodyPart` chest. ~35 s idle (watch flat), then ~9 s of clear
  ~1 Hz up/down movement. A naive peak count on vertical acceleration (< 1.5 Hz low-pass) finds 6
  of 8: fine for a first look, the real counter is Phase 4.
- `20261110-192450_0047_s1.csv` (incline bench, the watch-started workout of 2026-11-10 while sync
  was broken): 146 s at 50 Hz, then a 2.5 h gap, then the last 5 s before the tick. The watch app
  was suspended, probably no workout session (Apple Health setting had not reached the watch).

To fix with 2b (not urgent): cap a set's window to the last `keepSec` (the buffer trims by count,
so old samples can survive a suspension). Still to verify in a real workout: samples continue for
minutes with the wrist down and Apple Health on.

Join check: the workout reached the server after the user opened MyGym (MCP `list_workouts`: Upper A
2026-11-11, id `mwb3ek2dw8jk1` = the CSV's `wid`). The state's set has `r: 8` and
`at: 1794339536329.6`; the CSV's `end` is 1794339536330. Labels for analysis: match CSV to the
state's set by `wid` + `exId` + `at` == `end` (within 1 ms); the state's set has no `id`.

Note: after a Mac restart the server is down until `colima start` + `docker compose up -d`; the
phone keeps its changes and uploads once it can reach the server again.

### Start set button (the user's request, 2026-11-11)

The user did not want rest time in the data. Now the sensor runs only from **Start set** to **Done**
(commit "feat: start set button for motion recording"):
- Watch set page: for reps exercises that move the wrist, the big button reads "Start set" (play)
  until pressed, then "Done" with a red dot. Leg exercises, holds and cardio unchanged.
- Start set ends a running rest, marks activity (keeps the Health workout session running),
  starts the sensor and plays a haptic. Done sends the CSV of exactly that window (capped at
  `keepSec`) and stops the sensor.
- No file when the recording ends without Done: set skipped, another set picked, the workout
  finished/discarded/started, a set ticked on the phone, or the workout ended or changed there.
- Forgot Start: press Start then Done -> a very short CSV; drop CSVs under ~2 s in analysis.
- `WorkoutManager` no longer starts the sensor with the workout; it still stops it on pause/end.
- Strings: "Start set" in `ci/watch-strings.mjs` (zh-Hant 開始; other languages are my own
  translations, unchecked), regenerated .lproj files.
- Checked: WatchCore 73 tests, frontend tests (only the known local `app-icons` failure);
  signed build installed on iPhone, then the embedded watch app on the watch.
- The user's test 2026-11-11 (bench press 0025, workout `mwb425oqogoei`, 3 sets): windows 8.5 s,
  15.4 s, 9.0 s; first sample within 0.04 s of Start; 49.7 Hz, max gap 0.021 s; rests between
  sets (8.4 s, 3.4 s) not recorded. CSV `end` == the server's set `at` to the ms.
- Label problem: all 3 sets logged 8 reps (the routine's target, unchanged), but the plots show
  about 6, 6 (+5 s of small fast shaking) and 7 big cycles. Ground truth must be the real count:
  The user sets reps with the crown before Done, or fixes them on the iPhone afterwards.

## Phase 2b plan (approved 2026-11-11)

iPhone uploads the CSVs to the Mac server when MyGym is open at home; each file is deleted on
the phone only after the server answered OK.
- Server: `PUT /api/motion` JSON `{name, csv}`, signed-in only (cookie or the phone's bearer),
  strict file name check, writes `DATA_DIR/motion/<uid>/<name>` (same name = overwrite).
  `openapi.yaml` entry, `api/test/server-motion.test.js`.
- Server now runs OUR build: `docker compose up -d --build api`. Never `docker compose pull`
  again (it would bring back the upstream image without this route).
- iPhone native (`WatchBridgePlugin`): `listMotion`, `readMotion`, `deleteMotion`; event
  `motionFile` when a CSV arrives.
- iPhone JS: `frontend/src/lib/motion-upload.js` (+ test), started from `store/useStore.js`;
  runs at launch, on `motionFile`, and when the app comes back to the front.
- The user's 2026-11-11 test CSVs still on the iPhone are deleted from `data/motion/` after the first
  upload (the user approved). The user deletes the 2 test workouts of 2026-11-11 in MyGym themselves.

## Server on the Mac (Phase 1b)

Set up 2026-11-09: Colima 0.10.3, Docker 29.9, docker compose 5.7 (Homebrew). Upstream images
`ghcr.io/duartesantos8/opengym-{api,web}:latest`, no server code changed yet.
`.env` = `.env.example` defaults (`localhost:8080`) + `FIRST_USER_ADMIN=1`. Data in
`~/dev/mygym/data/` (git-ignored). Colima does NOT start at login.

```bash
colima start                              # after a reboot
cd ~/dev/mygym && docker compose up -d    # start the server
docker compose ps                         # both containers "healthy"
docker compose down                       # stop the server (data stays)
colima stop                               # stop the VM
```

Addresses: Mac browser `http://localhost:8080`, iPhone `http://<mac-name>.local:8080`
(same Wi-Fi; plain http, home network only).

Claude: MCP server `opengym` registered with `claude mcp add --scope local` for
`~/dev/mygym` only (reads `data/` directly). Open Claude Code in `~/dev/mygym` to use it.

### The user's steps

1. Mac browser: `http://localhost:8080` > create your profile (passkey / Touch ID). The first
   profile becomes admin.
2. Settings > Account > Pair the mobile app > confirm > note the 5-minute code.
3. (After Phase 1 is on the iPhone) MyGym > Settings > Account > Connect to my server >
   `http://<mac-name>.local:8080` + the code. Allow "Local Network" when iOS asks.
   If macOS asks whether to accept incoming connections, allow.
4. Tell Claude when done: Claude checks `data/db.json` and calls the MCP tools.

Status 2026-11-09: step 1 done (profile `me`, admin; created with "Create new profile", not
"Sign in with passkey"). MCP serves that profile and lists 11 tools; they answer "no synced state
yet" until a device saves data (`data/state-<uid>.json` appears then).

2026-11-09: end-to-end check passed. Pairing at 23:07, but the first upload (`PUT /api/data` 200)
only came at 23:20 when MyGym was open in the foreground. Sync needs the app open on the phone
(and the Mac awake, same Wi-Fi).
- In-progress workouts never reach the server: `api/server.js` deletes `state.active` on every
  push. A workout shows up in `data/` and the MCP only after it is finished on the phone.
  Phase 2 motion data needs its own path to the Mac for the same reason.

## Real device notes (2026-11-09)

- iPhone 15 Pro: iOS 27.0.1, Developer Mode on, connected to Xcode over Wi-Fi.
- Watch UDID <watch UDID>, connects over Wi-Fi via the iPhone (drops sometimes:
  retry). Watch build + install:
  `xcodebuild -workspace App.xcworkspace -scheme OpenGymWatch -destination 'id=<watch UDID>'
  -derivedDataPath build/dd-watch -allowProvisioningUpdates -allowProvisioningDeviceRegistration
  DEVELOPMENT_TEAM=<TEAM_ID> build`, then `xcrun devicectl device install app --device
  <watch UDID> build/dd-watch/Build/Products/Debug-watchos/OpenGymWatch.app`.
- Team `<TEAM_ID>` (Personal Team). In Xcode the App Group had to be ticked once per
  target (Signing & Capabilities > App Groups); before that the profiles had an empty group list
  and the build failed with "doesn't match the entitlements file's value for
  com.apple.security.application-groups". HealthKit works on the free team.
- Free team limit: 3 apps signed by this team per iPhone. The user also sideloads apps with AltStore
  (same team), so MyGym only installed after the user removed one. AltStore refreshes use the same
  team's App ID quota (10 per 7 days).
- CLI build + install (Xcode Run works too):
  `xcodebuild -workspace App.xcworkspace -scheme App -destination 'id=<iPhone UDID>'
  -derivedDataPath build/dd-device -allowProvisioningUpdates DEVELOPMENT_TEAM=<TEAM_ID> build`, then
  `xcrun devicectl device install app --device <UDID> build/dd-device/Build/Products/Debug-iphoneos/App.app`.

## Simulator limits

- The iPhone app does not run on the iOS 27 simulator: the GoogleMLKit pod (barcode scanner)
  sets `EXCLUDED_ARCHS[sdk=iphonesimulator*] = arm64`, so the simulator build is x86_64 only,
  and the iOS 27 simulator does not run x86_64 apps. Test the iPhone app on the real iPhone.
- The watch app alone runs on the watch simulator, but it cannot sync without the iPhone app,
  and the simulator has no real motion sensor. Rep counting is tested on the real watch only.

## How to test (Phase 1, on the devices)

1. iPhone: Settings > Privacy & Security > Developer Mode > On (restarts the phone).
2. Connect the iPhone by cable, unlock it, tap Trust.
3. Watch: keep it paired and on the wrist, unlocked, iPhone and Mac on the same Wi-Fi.
   In Xcode open Window > Devices and Simulators and wait until the watch appears
   (can take several minutes the first time). Then on the watch: Settings > Privacy & Security >
   Developer Mode > On.
4. Xcode > Settings > Accounts: add your Apple ID.
5. In Xcode select the project `App`, then for each target `App`, `OpenGymWatch`,
   `OpenGymWatchWidgets`: Signing & Capabilities > Team = your Personal Team.
   Note any red error text and send it to Claude.
6. Scheme `App`, destination your iPhone, press Run. On the iPhone: Settings > General >
   VPN & Device Management > trust your developer app.
7. Scheme `OpenGymWatch`, destination your watch, press Run.
8. Check: the iPhone app opens; start a workout with one exercise; the watch shows it;
   tick one set on the watch and see it on the phone.

Report back: which steps worked, the exact error text and a screenshot for any that did not.
