# Rep counter (Apple Watch) - progress

Fork of openGym that adds automatic rep counting on the Apple Watch (CoreMotion).
Read this file first at the start of every session; update it before the session ends.

## Current phase

**Phase 1: build unmodified openGym on iPhone + Watch** (simulator build OK 2026-11-09, waiting for the user's device test)

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
- Apple Watch Series 10, 45 mm (watchOS version not checked yet; openGym needs watchOS 10+).

## Open questions

- First exercise to count (needed in Phase 2).

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
