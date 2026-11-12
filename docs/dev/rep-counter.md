# Rep counter (Apple Watch) - progress

Fork of openGym that adds automatic rep counting on the Apple Watch (CoreMotion).
Read this file first at the start of every session; update it before the session ends.

## Goal (the user, 2026-11-09)

1. iPhone and Apple Watch both record workouts (openGym already does this).
2. The watch counts reps automatically for chosen exercises from the motion data (new).
3. Data is stored as files on the user's Mac, which runs the openGym server (self-hosted `data/`).
4. An AI assistant on the Mac reads that data for analysis (openGym's `mcp/` server, or the files).

## Phases

1. Phase 1: build our app (MyGym) on the real iPhone and Watch.
2. Phase 1b: self-hosted server on the Mac (Colima + Docker, home Wi-Fi first, Tailscale later
   if needed), pair MyGym with it, register `mcp/` with the AI assistant.
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
4. Report back; the CSVs are then copied to the Mac:
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
- Strings: "Start set" in `ci/watch-strings.mjs` (translations for all 18 app languages,
  unchecked), regenerated .lproj files.
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

### Phase 2b status (2026-11-11)

Code committed ("feat: upload watch motion to server"). Checked: api 801 tests (incl.
`server-motion`, openapi route check), frontend 7836 (only the known local `app-icons` failure),
WatchCore 73. Server rebuilt from our code (`docker compose up -d --build api`): health OK,
`PUT /api/motion` answers 401 unsigned. iPhone + embedded watch app installed. `build:mobile`
failed at `pod install` (the `build/` folder lost its xattr after `xcodebuild clean` recreated it;
re-marked), but the new JS was copied before that and is inside the installed app.

VERIFIED 2026-11-11 05:27 JST: the iPhone sent 5 `PUT /api/motion` (all 200), the files were in
`data/motion/<uid>/`, the iPhone's `Documents/motion` is empty. The 5 test CSVs were then deleted
from the server (the user approved). The user imported the Hevy history and the new plan at 12:03 (15
workouts, week = the 4 new routines; the 4 old routines are still there, harmless) and deleted
the 2 test workouts.

Before-gym check 2026-11-11 12:20: iPhone app and watch app both 1.4.4 (54), same build as
`build/dd-device` (embedded watch copy); profiles valid to 2026-11-16. Nothing gets installed
before a gym day: the only known trigger of the sync loss is a reinstall. The iPhone had not
contacted the server since 05:28, so the user must open MyGym on the iPhone at home to get the new
schedule before leaving.

Old note: the real upload was not verified at first. Next time: the user opens MyGym on the watch (once, after the
reinstall), then on the iPhone at home; check that `data/motion/<uid>/` got the 5 test CSVs
and the iPhone's `Documents/motion` is empty, then deletes those 5 test files. The user still has to
delete the 2 test workouts of 2026-11-11 in MyGym.

## Training data and schedule (2026-11-11)

- Hevy history `~/Downloads/workout_data 3.csv` (the user's export): dry run with the app's own
  `parseImportFile`: 15 workouts, 280 sets, 2026-10-13 .. 2026-11-10; all exercises matched
  except "Seated Chest Flys (Cable)" (becomes a custom exercise); 36 sets of 13-14 Oct have 0
  reps (not logged in Hevy). The user imports it in the app (Settings > Data & backup > Import from
  another app), so it syncs like any change.
- New 4-day schedule from 2026-11-11 as a plan file `~/Downloads/mygym-new-plan.json`
  (validated with `parsePlan`: 4 routines, 29 exercises, 0 dropped): Tue Torso A, Wed Limbs A,
  Fri Torso B, Sat Limbs B (the user named them in Chinese in the app); Mon/Thu/Sun rest. Exercise ids reuse the ids the Hevy history maps to
  where one exists (last time / progression connect). Rep ranges as `repsMin`/`repsMax`,
  "alternate 6 and 7" as supersets (`sg`), "try this weight", "seat higher", "low to high" as notes. Imported with "Use this weekly
  schedule" (replaces the Mon-Sun plan); the user then deletes the old Upper A/B, Lower A/B routines.

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

AI assistant: MCP server `opengym` registered with local scope for `~/dev/mygym` only (reads
`data/` directly). Start the assistant in `~/dev/mygym` to use it.

### The user's steps

1. Mac browser: `http://localhost:8080` > create your profile (passkey / Touch ID). The first
   profile becomes admin.
2. Settings > Account > Pair the mobile app > confirm > note the 5-minute code.
3. (After Phase 1 is on the iPhone) MyGym > Settings > Account > Connect to my server >
   `http://<mac-name>.local:8080` + the code. Allow "Local Network" when iOS asks.
   If macOS asks whether to accept incoming connections, allow.
4. Report back when done; then check `data/db.json` and call the MCP tools.

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
   Note any red error text and report it.
6. Scheme `App`, destination your iPhone, press Run. On the iPhone: Settings > General >
   VPN & Device Management > trust your developer app.
7. Scheme `OpenGymWatch`, destination your watch, press Run.
8. Check: the iPhone app opens; start a workout with one exercise; the watch shows it;
   tick one set on the watch and see it on the phone.

Report back: which steps worked, the exact error text and a screenshot for any that did not.

## First gym session (2026-11-11, Upper A, workout `mwbntd487xjt8`)

Phone and watch stayed in sync at the gym (every CSV carries the phone's workout id). At home the
iPhone uploaded 19 CSVs in one go (17:20 JST); they are in `data/motion/<uid>/`, 8 exercises.
Ground truth = `r` of the set on the server (the user corrected some after Done: the CSV's `reps` is
only the value at the moment of Done, e.g. chest press s2 10 -> 11, s3 10 -> 7).

Data problems found:
- Gaps inside 5 sets, all between 14:14 and 14:47: chest press s2 9.3 s, incline bench s1 3.8 s +
  4.5 s, incline s2 2.8 s, chest press s3 and lateral raise s1 0.1-0.4 s. The other 14 sets have
  none (max 0.03 s). Cause NOT known yet. A 9 s gap loses about 3 reps, so this must be understood
  before the live count. To check: is the app throttled in the background, and would
  `CMBatchedSensorManager` (made for workouts) be the sturdier source.
- Long windows: bench s3 193 s, curl s3 126 s, lat pulldown s1 104 s. In curl s3 the 6 reps are
  clear in the first 25 s, the rest is noise: Done was pressed late.
- Curl s2 is 0.5 s long (Start and Done right after each other). Bench s1 has no file (ticked on
  the phone). Incline s2 does not join: the server's `at` is 37 s later than the CSV's `end`
  (integer `at` = re-ticked on the phone).

Naive count (`docs/dev/tools/first_look.py`: band-pass 0.15-1.5 Hz, peaks on wrist tilt): exact in
2 of 18 sets, within 1 in 4 of 18. Not usable, as expected. What the plot shows:
- The reps are clearly visible in lateral raise, curl, chest press, triceps extension, row s1.
- The naive count is too high mostly because of the moves before the first and after the last rep
  (lifting off, racking) and the long idle tails.
- Seated row s2/s3: the wrist hardly tilts; the reps show in acceleration, not in tilt. So the
  signal has to be chosen per set, not fixed.

Idea for Phase 4: lock onto the rhythm (count only once 2-3 similar cycles follow each other,
then count those too), pick the stronger of tilt/acceleration per set, ignore lone big moves.

## First real gym session (2026-11-11, Upper A, 14:09-15:34)

Data: 19 motion CSVs reached the server by themselves (2b works end to end), 23 sets ticked, heart
rate on every set (the workout session ran). Usable for Phase 4: 18 files. Not usable:
`145828_0031_s2` (0.5 s: the app had crashed during the set, the user pressed Start then Done after
reopening); `0025` set 1 has no file. Gaps of 3-9 s inside `141458_0577_s2`, `143627_0047_s1`,
`144103_0047_s2` (app not running for a moment; re-check after the crash fix).

### Problem: the watch app closed again and again (ROOT CAUSE FOUND)

20 crash reports of 14:14-15:26 on the iPhone (`devicectl device info files --domain-type
systemCrashLogs`, folder `ProxiedDevice-*/OpenGymWatch-*.ips`), all the same: EXC_BREAKPOINT on
the main thread at `OpenGymWatchApp.swift:1012`, RestView:
`Text(timerInterval: Date()...end, countsDown: true)`. A range whose end lies in the past traps.
It happens when the view is drawn again after the rest ran out and before the rest timer cleared
`restEndsAt` (the timer is late when the wrist was down); each crash is 3-21 s after a rest's end
(set time + 90 s). Upstream code, not ours. The same pattern is at line 1071 (hold countdown).
Symbolicated with `atos -o .../OpenGymWatch.app/OpenGymWatch.debug.dylib -arch arm64 -l <base>`.

The user's requests after the session: (1) app must stay open until Finish, (2) no rest after the
last set of an exercise, straight to the next one, (3) crown: weight in 0.5 kg steps (his cable
stacks are 3.5 / 6.5 / 8.5 / 13.5 / 47.5, not on the 2.5 grid the editor snaps to), smoother.
The user approved. Done 2026-11-11 (commit "fix: watch crash at rest end, no rest after last set,
0.5 kg crown"):
- Crash: the range is `min(Date(), end)...end` in RestView and the hold countdown.
- Rest: only between the sets of one exercise. Phone `restAfterSet` (`lib/supersetFlow.js`) is
  `!unitDone`, and no rest after a superset's last round (`views/Workout.jsx`); watch
  `SessionCore.next` returns `rest: false` when it moves to another exercise. The phone rule
  matters for watch ticks too: a watch tick runs the phone's action, and the phone's rest comes
  back in the snapshot. 14 upstream phone tests changed to the new rule; one skipped
  (`Workout.auto-holds`: moving on to the next TIMED exercise rode on that rest ending; the user has
  no timed exercise, rebuild it if he adds one).
- Crown (weight editor): 0.5 kg per step (1 lb), sensitivity `.high` for weight and `.medium`
  for reps (was medium / low): a first guess, tune by the user's feel. The + and - buttons keep the
  exercise's step (2.5 kg) and no longer snap to its grid (8.5 + 2.5 = 11).
Checked: WatchCore 74 tests, frontend 7835 (1 skipped, only the known local `app-icons`
failure). Built and installed 17:41: iPhone app, then the embedded watch app.
NOT yet verified on the devices: sync after this reinstall, a rest running out with the wrist
down, no rest after a last set, the crown's feel.

### The user's test of the fixes (2026-11-11 evening)

Confirmed by the user on the devices: no crash any more, no rest after a last set, sync works after
the reinstall. New findings:
- Crown too sensitive for weight and reps, and the number shows decimals while turning (5.1,
  5.2). Cause: `digitalCrownRotation` moves the bound value continuously and only settles on the
  step; sensitivity is per value unit, not per step. Fix idea: bind the crown to a step index
  (`by: 1`) and show `index * step`. The + and - buttons should be 0.5 kg too.
- The user wants a new watch layout (like Hevy's): a list of the workout's exercises, a tap opens the
  exercise page; on that page the crown turns the weight directly (no editor sheet), a tap on the
  reps tile hands the crown to reps. The crown must not flip to the next exercise.
- iPhone Dynamic Island shows nothing. Cause: the iOS widget extension (`OpenGymWidgets`, draws
  the Live Activity) was never added to the local project: only `ci/add-watch-app.rb` was run,
  not `ci/add-widgets.rb` (`App.app/PlugIns` does not exist). Its `BUNDLE_ID` is still
  `ch.opengym.app.widgets`.

## Phase 4 + 5: live rep count (2026-11-11, first version)

The user asked for it right after the first session: Start set, then a tap on the wrist per rep and
the reps counting up from 0 with the planned reps shown as the goal.

Algorithm (`WatchCore/RepCounter.swift`, 78 tests; the tuning twin is
`docs/dev/rep-counter-tools/counter.py`, the two must stay the same counter): the smoothed
GRAVITY vector (the wrist's orientation) zigzags between two directions. A reversal (the vector
has moved back from its farthest point by 1.2 x the recent spread) is a turning point; one that
lands where the one before last was proves half a rep; two halves are a rep. No acceleration yet.

Result on the 2026-11-11 workout against the reps the user logged (not all of them certainly true
counts: several equal the plan): of 12 sets with whole data, 10 within 1 rep.
  chest press +0, (-5: 7 logged, 4-5 slow humps in the signal), bench +(-1), lateral raise +1 +1,
  curl +0, seated row -1 +0 +0, overhead triceps +2 -1 +3.
Not counted in that: 3 sets with a data gap (the app was suspended: -6, -2, +2) and 3 "sets" of
100-190 s that were mostly not lifting (+16, +18, +6).

Known limits, all told to the user:
- A movement that does not turn the wrist (barbell bench, maybe pulldown / shoulder press) is
  seen badly. Needs vertical acceleration as a second signal.
- Moves made while getting into position can count (+1..+3 at the start of a set).
- A rep is counted a moment into the next one (the reversal shows late), the last rep when the
  wrist moves again (to the rack, to tap Done). If that last move carries on in the same
  direction, the last rep is missed.
- Tried and dropped: a "still for 0.7 s" rule and counting at the top of a rep (both counted too
  much), dropping short runs (lost real reps after a wobble).

On the watch: `MotionRecorder` feeds every sample to the counter and calls `onRep` on the main
queue; `SessionStore.startSet` keeps the planned reps as `repGoal` and sets reps to 0;
`countRep` adds one and taps the wrist (`.directionUp`, `.success` at the goal); the reps tile
shows "Goal 8" under the count; the crown still corrects it. Done with 0 counted logs the goal,
not 0. The CSV's metadata now carries `auto` (what the counter said) and `goal`, next to `reps`
(what was logged): every set from now on measures the counter.
NOT yet tried on the watch.

New file in the generated Xcode project: `WatchCore/Sources/WatchCore/RepCounter.swift` was added
by hand (xcodeproj one-liner); a fresh `ci/add-watch-app.rb` run picks it up by itself.
Dynamic Island: `ci/add-widgets.rb` ran (bundle id `com.rippuhonwan.mygym.widgets`); the build
stops at signing until the user ticks the App Group for target OpenGymWidgets in Xcode.

### Installed 2026-11-11 22:27

The user ticked the App Group for OpenGymWidgets in Xcode; the build went through
(`App.app/PlugIns/OpenGymWidgets.appex`, its profile lists `group.com.rippuhonwan.mygym`).
Installed the iPhone app, then the embedded watch app, both at the first try. On the devices
now: crown by steps, exercise list + in-place editing, live rep count, Dynamic Island extension.
NOT yet verified by the user: all four, and sync after this reinstall (he has to open the watch app
by hand once).

### The user's test of the live count build (2026-11-11 22:30) and the fixes installed 22:45

Works: Dynamic Island, the taps on the wrist are felt, sync after the reinstall.
Counter: "sometimes 1-2 too many, sometimes 4 too few". The 5 test sets (bench / incline, at
home) logged exactly what the counter said (`auto` == `reps`: goal 8 -> 12, 11, 12; goal 10 ->
11, 6), so there is NO true count in the data to tune against. Replay matches the watch. Not
changed blind: the user has to put the real number in before Done.
Fixed and installed (commit "fix: watch list taps, rolling digits, rest overtime, no lock button"):
- List taps took 2-3 s and Finish did nothing: SwiftUI List rows under RootView's tap gesture.
  Now plain buttons in a ScrollView. (Cause is my best reading; not proven on the device.)
- Digits roll (`contentTransition(.numericText)`); Start set moves the crown to the reps.
- Rest over: 4 x `.notification` (about 1.5 s; no single long vibration exists for an app),
  then `restOverSince` shows "-0:07" in red on the exercise page until Start set / Done.
- Water lock button removed from rest, hold and finish pages.
NOT yet verified by the user.

### Counter v1 undercounts; velocity is the better signal (2026-11-11 23:00)

The user's second home test, 10 real reps each (told in chat; the logged reps are the counter's):
bench 5, 7, 6 (one more set not found on the server), curl 9, 9. "The first reps are not
counted, sometimes it only starts at the 4th."
Cause seen in the data (files `2248*`/`2249*`): the user starts lifting about 1 s after Start set.
The gravity zigzag measures distance from its last turning point, which at first is the pose he
tapped Start in; small-tilt reps (bench: 0.2-0.4) far from that pose never look like a reversal,
so several reps melt into one 4-6 s "segment". In a curl the first up-stroke is merged with the
move from that pose, and the last down-stroke has no reversal after it: 9 of 10.
Better signal: velocity along the movement, from band-passed acceleration (vertical component
= userAcceleration . gravity). In all four files it is a clean sine with exactly 10 swings, also
for the bench press where the wrist hardly tilts, and its zero crossings ARE the highest and
lowest points (what the user asked for: the tap can come at the bottom, not into the next rep).
Prototype `docs/dev/rep-counter-tools/vel_prototype.py` (causal, Schmitt trigger at 1.0 x recent
RMS, crude size gate): tonight's four sets 10, 10, 11, 10 (v1: 5, 7, 6, 9).
NOT ready: on the gym sets it counts too much (+1..+8 on whole sets, far more on the long junk
ones): every move while getting into position swings the velocity too. Needs a regularity gate
(period and size like the reps before), a decision between vertical and principal axis (machine
chest press and rows move sideways: the principal-axis variant did better there), and sets with
true counts. Proposed to the user as v2; not built.

### Counter v2: velocity (2026-11-11 23:40, built and installed)

`WatchCore/RepCounter.swift` rewritten; twin `docs/dev/rep-counter-tools/counter2.py`
(`python3 counter2.py` scores every recorded set; v1's `counter.py` is gone). userAcceleration,
high-passed (1.0 s), leaky-integrated (0.8 s), smoothed -> velocity vector; projected on its
main axis (running covariance, 3 s); a swing = above +th after below -th (th = 1.0 x recent RMS,
floor 0.05 m/s); a swing counts when its size is 0.5-2.2x and its period 0.5-2.0x the median of
the last 5; a lone first swing that the next one does not match is replaced by it.
Scores: home (10 real reps each) 10, 10, 10, 9. Gym, 12 whole sets vs logged: 0 -3 +1 0 +2 0 +1
0 +4 0 +1 +1 (the -3 is the doubtful 7; +4 is the 16-rep row). Sets with gaps / junk: still far
off (+18, +21 on the 100-190 s ones).
Tried and dropped: vertical-only velocity (worse on machine press and rows), counting a rep when
its second lobe dies down with a "leading direction" (curl 8 of 10), "still for 0.5 s ends the
last rep" (gym +9 in total). So the known limits stay: the LAST rep of a set that ends dead still
is not counted (curl: 9 of 10), moves while getting into position can count, and a rep is
counted about a quarter of a rep into the next one.
Fixtures (acceleration only): `reps-bench-10`, `reps-curl-10`, `reps-row-16`; WatchCore 77 tests.
NOT yet tried on the watch.

### v2 on the watch: better, slow reps missed (2026-11-11 23:15)

The user: "much better, usually 1-2 short; fast reps are counted, slow ones may not be."
Sets `2305*`/`2306*` (bench at home; `auto` == `reps` again, so no true counts in the files).
Cause: a slow rep hardly accelerates the wrist (acceleration goes with 1/period squared), the
velocity swing stays near the threshold (`230658_0025_s3`: peaks 0.3-0.4 m/s against 0.8-1.0
in the fast sets). Slower filters (high-pass 1.5-2 s, leak 1.2-1.6 s) do NOT fix it: no gain on
the slow set and the curls get worse (the watch turns, drift comes through).
The wrist's tilt does not care about speed: v1 (gravity zigzag) counts 10 on that slow set where
v2 counts 7. The two counters fail in opposite cases (v1: fast reps with little tilt, first
reps; v2: slow reps). Taking the larger of the two on every scored set: home 10 10 10 9 (same as
v2), gym a little more overcount (+1 +2 +1 +4 +2 +1 +3 where v1 or v2 alone overcounts).
Not built: without slow sets of a known count a fusion rule cannot be chosen or checked.
Asked the user for 2-3 slow sets (about 4 s per rep), the real count put in with the crown before Done.

### Combined count, installed 2026-11-13 (the user chose the two-step plan)

Step 1 (done): the watch counts `max(RepCounter.reps, TiltCounter.reps)` (`MotionRecorder`).
`TiltCounter.swift` is v1 back under a new name (twin `tilt.py`); `counter2.py` now scores the
combination (`fused`): home 10 10 10 9, gym 12 whole sets abs 18 (v2 alone 13: max adds both
overcounts). WatchCore 81 tests. Installed on both devices.
Step 2 (next, needs the user's sets with true counts, fast AND slow, crown before Done): one fused
signal (velocity along the axis + attitude change, incl. rotation about the vertical from
CMAttitude, which gravity cannot see) and counting by periodicity (autocorrelation over the last
few seconds: the period first, then only swings that keep it). Expected: slow reps by shape not
size, setup moves dropped as not periodic; cost: reps 1-2 confirmed together at rep 2-3.
Replay all three on the Mac, keep the best.

Analysis ideas for later (the user asked 2026-11-13; none built). Per rep from the CSV:
- tempo: up / down / pause times (eccentric vs concentric), time under tension per set
- velocity loss within a set (mean concentric speed of the last reps vs the first): a standard
  fatigue / "reps in reserve" marker in velocity-based training; the user's "stops and shakes" = a
  stall plus tremor (power in ~8-12 Hz of userAcceleration)
- range of motion per rep (velocity integrated over one rep; tilt range) and its shrinking
- wrist tilt / roll during a rep where it should stay still (the user's grip/form idea)
- left-right / path consistency rep to rep, a jerky vs smooth movement (jerk)
- rest length vs reps of the next set, heart rate recovery between sets (HR is already logged)
- per exercise over weeks: speed at the same weight rising = getting stronger (load-velocity profile)
Caveat for all of it: one watch on one wrist, no position, so these are relative within the user's
own data, not absolute numbers.

## Next features: research (2026-11-13, nothing built)

The user asked for six. Grouped by what they depend on.

Can start now:
1. One-click install (`scripts/ios/install-devices.sh`): build:mobile only when `frontend/src`
   changed since the last build, xcodebuild with `-allowProvisioningUpdates` (renews the free
   7-day profiles), print each embedded profile's expiry, devicectl install iPhone then the
   embedded watch app with retries, then ask to open the watch app by hand. Plus a launchd job
   that posts a macOS notification two days before the earliest expiry.
2. Post-workout report: a Python script (same signal code as `counter2.py`) builds one HTML file
   per workout in `data/reports/` from `state-<uid>.json` + the set CSVs: sets, volume, change vs
   last time, counter vs logged reps, per rep: speed, tempo, velocity loss per set; heart rate per
   set and rest, real rest length (the 2026-11-11 sets were 150-360 s apart with a 90 s timer).
   Trigger: launchd `WatchPaths` on `data/motion/<uid>`; an AI written summary can be added later
   (MCP server already reads `data/`).
3. Heart-rate rest: the watch has the live readings (`WorkoutManager.samples`). Rest is "ready"
   when HR has fallen a set number of bpm below the set's peak, bounded by a min and a max rest.
   2026-11-11: set peaks 109-149, rest averages 105-131, so only a relative rule can work; only
   avg/max are stored now, so first record the rest's HR curve (seconds, bpm) in the next set's
   CSV metadata to tune the drop. Setting on the phone (WatchSettings), off by default.

Need the counter to be right first (Phase 3 data):
4. Velocity per set: `RepCounter` keeps each counted swing's size (peak-to-peak velocity). At Done
   the watch adds `vel: {first, last, loss}` to the tick event (like `hr`); the phone stores extra
   set fields as they come (`watch-sync.js` write). Only valid when the velocity counter counted.
5. Fatigue alert: live, a distinct haptic when a rep's swing is a set % below the best of the
   first two reps (setting, e.g. 30%); also a rep taking > 2x the median time (a grind).
6. Auto-end a set: after >= 1 rep, the wrist still (acceleration RMS low) for ~4 s -> "Done in
   3 s" with a tap to cancel, then Done with the counted reps. Risk: a pause at lockout
   (rest-pause); hence the cancel window and a setting.
7. Weight suggestion (last, needs weeks of `vel` history): in `progression.js nextPrescription`,
   for reps policies: target reps hit and velocity loss below a threshold -> raise as now; loss
   high -> hold. Thresholds are a setting; the published VBT ranges are a starting point only.

### Built 2026-11-13: one-click install and the post-workout report

- `scripts/ios/install-devices.sh` (+ `--renew`, `--build-only`, `--install-reminder`): tested
  build-only and renew. Renewing works with a free Apple ID: deleting the app's cached profiles
  (Xcode UserData) and building with `-allowProvisioningUpdates` gave new 7-day profiles
  (now to 2026-11-20). NOT yet installed with it (needs the iPhone unlocked at home).
  Logs in `~/Library/Logs/MyGym/` (cap sync deletes `build/`). Team id in the ignored
  `scripts/ios/local.env`. `installed-until` there records the expiry of what is on the devices.
- `scripts/ios/profile-reminder.sh`: notification within 48 h of that expiry. The daily
  LaunchAgent (`--install`) must be turned on by the user; the assistant's tool blocked it.
- `docs/dev/rep-counter-tools/workout_report.py`: HTML per workout in `data/reports/` (+ index),
  16 written. Per set: weight, reps, the watch's count (same rule as the watch: max of speed and
  tilt counter) and its difference, rep speed bars, velocity loss (last 2 vs best of first 3),
  tempo, HR set and rest, real rest (Done to the next Start set). Auto run: `--install-watch`
  (LaunchAgent on `data/motion` and the state file), also to be turned on by the user.
