"""Post-workout report: one HTML page per workout in data/reports/, plus an index.

Reads the server's files on this Mac (state-<uid>.json, motion/<uid>/*.csv) and nothing else.
Per set: weight and reps, the watch's own count, heart rate in the set and the rest after it, how
long the rest really was, and from the motion file the speed of every rep, its tempo and how much
the speed fell from the first reps to the last (velocity loss, a fatigue sign).

    python3 docs/dev/rep-counter-tools/workout_report.py            new or changed workouts
    python3 docs/dev/rep-counter-tools/workout_report.py --all      every workout again
    python3 docs/dev/rep-counter-tools/workout_report.py --install-watch   run by itself when data arrives

Speeds are relative (the watch integrates its own acceleration on one wrist): compare them within
your own sets and over time, not with published numbers.
"""
import glob
import html
import json
import os
import sys
from datetime import datetime

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
DATA = os.environ.get("MYGYM_DATA", os.path.join(ROOT, "data"))
sys.path.insert(0, HERE)
from counter2 import RepCounter2  # noqa: E402
from tilt import run as tilt_run  # noqa: E402

NAMES = {}


def name_of(ex_id, fallback=""):
    if ex_id not in NAMES:
        try:
            NAMES[ex_id] = json.load(open(os.path.join(ROOT, "catalogue", "exercises", f"{ex_id}.json")))["name"]
        except (OSError, ValueError, KeyError):
            NAMES[ex_id] = fallback or ex_id
    n = NAMES[ex_id]
    return n[:1].upper() + n[1:]


def clock(ms):
    return datetime.fromtimestamp(ms / 1000).strftime("%H:%M")


def load_csv(path):
    with open(path, encoding="utf-8") as f:
        meta = json.loads(f.readline()[2:])
    a = np.genfromtxt(path, delimiter=",", skip_header=2)
    return meta, (a if a.ndim == 2 else None)


def motion_of(a):
    """What one set's motion file says: the count (the watch's rule: the larger of the speed and
    the tilt counter), each rep's speed, the tempo and the velocity loss."""
    if a is None or len(a) < 50:
        return None
    c = RepCounter2()
    for i in range(len(a)):
        c.push(a[i, 0], a[i, 1:4], a[i, 7:10])
    tilt = tilt_run(a[:, 0], a[:, 7:10]).reps
    out = {"count": max(c.reps, tilt), "speeds": list(c.rep_sizes), "events": list(c.events)}
    if len(c.events) >= 2:
        out["tempo"] = float(np.median(np.diff(c.events)))
    sp = c.rep_sizes
    if len(sp) >= 4:
        best = max(sp[:3])
        out["loss"] = max(0.0, 1 - float(np.mean(sp[-2:])) / best)
    return out


def bars(speeds):
    """The reps' speeds as small bars, the first ones' best as the full height."""
    if not speeds:
        return ""
    top = max(speeds)
    w = 7
    rects = "".join(
        f'<rect x="{i * (w + 2)}" y="{24 - 24 * v / top:.1f}" width="{w}" height="{24 * v / top:.1f}" rx="1"/>'
        for i, v in enumerate(speeds))
    return f'<svg class="bars" width="{len(speeds) * (w + 2)}" height="24" aria-hidden="true">{rects}</svg>'


def recovery(curve):
    """The rest before a set, from its file's heart rate curve ([seconds from Start set, bpm]; the
    rest is before 0): the highest reading in its first 30 s, the last one before the set, and how
    long it took to fall 20 bpm from that high."""
    rest = [(t, b) for t, b in (curve or []) if t < 0]
    if len(rest) < 3:
        return None
    t0 = rest[0][0]
    hi_t, hi = max([x for x in rest if x[0] <= t0 + 30], key=lambda x: x[1])
    end = rest[-1][1]
    down = next((t - hi_t for t, b in rest if t > hi_t and b <= hi - 20), None)
    return {"high": hi, "end": end, "down20": down}


def hr_text(h):
    return f'{h["avg"]:.0f} / {h["max"]:.0f}' if h else "–"


def report(w, workouts, motions):
    """One workout's page."""
    sets = []  # every done set in time order, for the real rest lengths
    for ei, e in enumerate(w["entries"]):
        for si, s in enumerate(e["sets"]):
            if s.get("done") and s.get("at"):
                sets.append((s["at"], ei, si))
    sets.sort()
    nxt = {}
    for (at, ei, si), (nat, nei, nsi) in zip(sets, sets[1:]):
        start = motions.get((w["id"], w["entries"][nei]["id"], round(nat)), ({}, None))[0].get("start")
        nxt[(ei, si)] = ((start or nat) - at) / 1000

    rows = []
    total_reps = vol = 0
    for ei, e in enumerate(w["entries"]):
        done = [(si, s) for si, s in enumerate(e["sets"]) if s.get("done")]
        if not done:
            continue
        prev = last_time(e["id"], w, workouts)
        rows.append(f'<tr class="ex"><th colspan="8">{html.escape(name_of(e["id"]))}'
                    f'<span class="prev">{html.escape(prev)}</span></th></tr>')
        for si, s in done:
            meta, a = motions.get((w["id"], e["id"], round(s.get("at") or 0)), ({}, None))
            m = motion_of(a)
            reps = s.get("r") or 0
            weight = s.get("w") or 0
            total_reps += reps
            vol += reps * weight
            counted = m["count"] if m else None
            watch = f'{counted}' if counted is not None else "–"
            if counted is not None and counted != reps:
                watch = f'<span class="off">{counted} ({counted - reps:+d})</span>'
            loss = f'{m["loss"] * 100:.0f}%' if m and "loss" in m else "–"
            tempo = f'{m["tempo"]:.1f} s' if m and "tempo" in m else "–"
            rec = recovery(meta.get("hrCurve"))
            rec_t = ""
            if rec:
                d = f', -20 in {rec["down20"]:.0f} s' if rec["down20"] is not None else ", never -20"
                rec_t = f'<br><span class="dim">before: {rec["high"]:.0f} to {rec["end"]:.0f}{d}</span>'
            rest = nxt.get((ei, si))
            rest_t = f'{rest / 60:.0f}:{rest % 60:02.0f}' if rest else "–"
            rows.append(
                f'<tr><td>{si + 1}</td><td>{weight:g}</td><td>{reps:g}</td><td>{watch}</td>'
                f'<td>{bars(m["speeds"]) if m else ""}</td><td>{loss}</td><td>{tempo}</td>'
                f'<td>{hr_text(s.get("hr"))}<br><span class="dim">rest {hr_text(s.get("restHr"))} · {rest_t}</span>{rec_t}</td></tr>')
    mins = (w["end"] - w["start"]) / 60000 if w.get("end") and w.get("start") else 0
    day = datetime.fromtimestamp(w["start"] / 1000).strftime("%a %d %b %Y")
    head = (f'<h1>{html.escape(w.get("name") or "Workout")}</h1><p class="dim">{day}, '
            f'{clock(w["start"])}–{clock(w["end"])} ({mins:.0f} min)</p>'
            f'<div class="tiles"><div><b>{len(sets)}</b>sets</div><div><b>{total_reps:g}</b>reps</div>'
            f'<div><b>{vol:,.0f}</b>{html.escape(w.get("unit") or "kg")} volume</div></div>')
    table = ('<table><thead><tr><th>Set</th><th>Weight</th><th>Reps</th><th>Watch</th><th>Rep speed</th>'
             '<th>Speed loss</th><th>Tempo</th><th>Heart rate avg / max</th></tr></thead><tbody>'
             + "".join(rows) + '</tbody></table>')
    notes = ('<p class="dim">Watch: what the watch counted (difference to the reps logged). Rep speed: '
             'one bar per rep, relative to the set\'s fastest. Speed loss: the last two reps against '
             'the best of the first three; a rising loss means you are near failure. Rest: from Done '
             'to the next Start set. Before: the heart rate in the rest before the set, from its high just '
             'after the last set to the moment you started, and how long it took to fall 20 bpm.</p>')
    return page(w.get("name") or "Workout", head + table + notes)


def last_time(ex_id, w, workouts):
    for o in reversed(workouts):
        if o["start"] >= w["start"]:
            continue
        for e in o["entries"]:
            if e["id"] == ex_id:
                done = [s for s in e["sets"] if s.get("done") and s.get("r")]
                if done:
                    best = max(done, key=lambda s: (s.get("w") or 0) * (1 + s["r"] / 30))
                    d = datetime.fromtimestamp(o["start"] / 1000).strftime("%d %b")
                    return f'last time ({d}): {len(done)} sets, best {best.get("w") or 0:g} × {best["r"]:g}'
    return "first time"


CSS = """
:root{--bg:#fff;--fg:#1d1d1f;--dim:#6e6e73;--line:#e5e5ea;--accent:#30d158;--off:#ff9f0a}
@media (prefers-color-scheme:dark){:root{--bg:#000;--fg:#f5f5f7;--dim:#98989d;--line:#2c2c2e}}
body{background:var(--bg);color:var(--fg);font:15px/1.5 -apple-system,system-ui,sans-serif;margin:0 auto;max-width:960px;padding:16px}
h1{font-size:22px;margin:0}.dim{color:var(--dim);font-size:13px}
.tiles{display:flex;gap:12px;margin:12px 0 20px}.tiles div{border:1px solid var(--line);border-radius:12px;padding:8px 14px;color:var(--dim);font-size:13px}
.tiles b{display:block;color:var(--fg);font-size:22px}
table{border-collapse:collapse;width:100%}th,td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line);vertical-align:top}
thead th{font-size:12px;color:var(--dim);font-weight:500}tr.ex th{padding-top:18px;font-size:16px}
.prev{display:block;font-weight:400;font-size:12px;color:var(--dim)}.off{color:var(--off)}
.bars rect{fill:var(--accent)}a{color:inherit}.wrap{overflow-x:auto}
"""


def page(title, body):
    return (f'<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{html.escape(title)}</title><style>{CSS}</style><div class="wrap">{body}</div></html>')


def main():
    every = "--all" in sys.argv
    if "--install-watch" in sys.argv:
        return install_watch()
    out_dir = os.path.join(DATA, "reports")
    os.makedirs(out_dir, exist_ok=True)
    made = 0
    links = []
    for state_file in sorted(glob.glob(os.path.join(DATA, "state-*.json"))):
        uid = os.path.basename(state_file)[6:-5]
        s = json.load(open(state_file, encoding="utf-8"))
        s = s.get("state", s)
        workouts = sorted([w for w in s.get("workouts", []) if w.get("start")], key=lambda w: w["start"])
        motions = {}
        for f in glob.glob(os.path.join(DATA, "motion", uid, "*.csv")):
            try:
                meta, a = load_csv(f)
            except (OSError, ValueError):
                continue
            if meta.get("wid") and meta.get("end"):
                motions[(meta["wid"], meta.get("exId"), round(meta["end"]))] = (meta, a)
        newest = max([os.path.getmtime(state_file)] + [os.path.getmtime(f) for f in glob.glob(os.path.join(DATA, "motion", uid, "*.csv"))])
        for w in workouts:
            name = datetime.fromtimestamp(w["start"] / 1000).strftime("%Y-%m-%d-%H%M") + f'-{w["id"]}.html'
            path = os.path.join(out_dir, name)
            links.append((w["start"], name, w.get("name") or "Workout"))
            if every or not os.path.exists(path) or os.path.getmtime(path) < newest:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(report(w, workouts, motions))
                made += 1
    items = "".join(f'<li><a href="{n}">{datetime.fromtimestamp(t / 1000):%a %d %b %Y}</a> – {html.escape(x)}</li>'
                    for t, n, x in sorted(links, reverse=True))
    with open(os.path.join(out_dir, "index.html"), "w", encoding="utf-8") as f:
        f.write(page("Workouts", f'<h1>Workouts</h1><ul>{items}</ul>'))
    print(f"{made} report(s) written to {out_dir}")


def install_watch():
    """A LaunchAgent that runs this script when the server's data changes."""
    label = "com.rippuhonwan.mygym.workout-report"
    plist = os.path.expanduser(f"~/Library/LaunchAgents/{label}.plist")
    watch = [os.path.join(DATA, "motion")] + glob.glob(os.path.join(DATA, "state-*.json"))
    paths = "".join(f"<string>{html.escape(p)}</string>" for p in watch)
    os.makedirs(os.path.dirname(plist), exist_ok=True)
    with open(plist, "w") as f:
        f.write(f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyLists-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>{label}</string>
  <key>ProgramArguments</key><array><string>{sys.executable}</string><string>{os.path.abspath(__file__)}</string></array>
  <key>WatchPaths</key><array>{paths}</array>
  <key>ThrottleInterval</key><integer>60</integer>
  <key>StandardOutPath</key><string>{os.path.expanduser('~/Library/Logs/MyGym/report.log')}</string>
  <key>StandardErrorPath</key><string>{os.path.expanduser('~/Library/Logs/MyGym/report.log')}</string>
</dict></plist>
""")
    os.makedirs(os.path.expanduser("~/Library/Logs/MyGym"), exist_ok=True)
    uid = os.getuid()
    os.system(f"launchctl bootout gui/{uid}/{label} 2>/dev/null; launchctl bootstrap gui/{uid} '{plist}'")
    print(f"Reports now follow the data ({plist}). Remove: launchctl bootout gui/{uid}/{label} && rm '{plist}'")


if __name__ == "__main__":
    main()
