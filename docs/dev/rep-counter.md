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

## Open questions

- First exercise to count (needed before Phase 2 starts).

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
