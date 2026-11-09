# Rep counter (Apple Watch) - progress

Fork of openGym that adds automatic rep counting on the Apple Watch (CoreMotion).
Read this file first at the start of every session; update it before the session ends.

## Current phase

**Phase 0: environment check** (in progress)

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
| CocoaPods | not installed | needed (`brew install cocoapods`) |
| Homebrew | 7.0.10 | - |

Notes from the upstream docs:
- The watch app target is added by `frontend/ios/ci/add-watch-app.rb` (xcodeproj gem), not
  committed in `App.xcodeproj`. Watch needs watchOS 10+.
- `WatchCore` (Swift package, `swift test`) holds the watch logic and tests.
- App Group `group.ch.opengym.app` and bundle ids `ch.opengym.app*` belong to upstream and must be
  renamed for our signing.

## Decisions

- 2026-11-09: bring openGym in by clone + push into the empty `mygym` repo (not a GitHub fork).

## Open questions

- Paid Apple Developer account or free Apple ID?
- Apple Watch / iPhone model and watchOS / iOS versions?
- OK to install CocoaPods with Homebrew?

## Upstream files changed

None yet.

## How to test

Nothing to test yet.
