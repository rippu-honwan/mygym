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


def from_detail(meta):
    """The watch's own per-rep data (`repsDetail`: [start, end, speed or None, source] seconds from
    Start set), when the set file has it: each counted rep's speed and the loss from it. Loss is
    unknown ("?") when a rep of the first three has no speed (the speed counter missed it: the
    best is then not known) or fewer than 4 reps have one; never cut to 0 (negative: faster)."""
    d = meta.get("repsDetail")
    if not isinstance(d, list) or not d:
        return None
    speeds = [r[2] for r in d if len(r) > 2 and isinstance(r[2], (int, float))]
    out = {"speeds": speeds, "events": [r[1] for r in d if len(r) > 1]}
    if len(out["events"]) >= 2:
        out["tempo"] = float(np.median(np.diff(out["events"])))
    first_known = all(len(r) > 2 and isinstance(r[2], (int, float)) for r in d[:3])
    out["loss"] = (1 - float(np.mean(speeds[-2:])) / max(speeds[:3])) if first_known and len(speeds) >= 4 else None
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


BANDS = [(0, 100), (100, 120), (120, 140), (140, 160), (160, 999)]


def readiness(daily, day):
    """Today against the usual: resting heart rate and HRV (from the watch's Apple Health, in the
    heart rate file) on `day` (YYYY-MM-DD) against the median of the 28 days before it.
    A rough guide, not a medical measure."""
    if not daily:
        return None
    out = {}
    sl = [v for d, v in sorted(daily.get("sleep") or []) if d == day]
    sl_before = [v for d, v in sorted(daily.get("sleep") or []) if d < day][-28:]
    if sl:
        out["sleep"] = (sl[-1], float(np.median(sl_before)) if len(sl_before) >= 3 else None)
    for key in ("rhr", "hrv"):
        rows = sorted(daily.get(key) or [])
        today = [v for d, v in rows if d == day]
        before = [v for d, v in rows if d < day][-28:]
        if today and len(before) >= 7:
            out[key] = (today[-1], float(np.median(before)))
    if not ("rhr" in out or "hrv" in out):
        return {"label": "Not enough days yet", **out} if out else None
    worse = ("rhr" in out and out["rhr"][0] >= out["rhr"][1] + 5) or ("hrv" in out and out["hrv"][0] <= 0.85 * out["hrv"][1])
    better = ("rhr" not in out or out["rhr"][0] <= out["rhr"][1] - 3) and ("hrv" not in out or out["hrv"][0] >= 1.1 * out["hrv"][1])
    out["label"] = "Lower than usual: an easier day may suit you" if worse else ("Better than usual" if better else "Usual")
    return out


def readiness_html(r):
    if not r:
        return ""
    parts = []
    if "rhr" in r:
        parts.append(f'resting heart rate {r["rhr"][0]:.0f} bpm (usual {r["rhr"][1]:.0f})')
    if "hrv" in r:
        parts.append(f'HRV {r["hrv"][0]:.0f} ms (usual {r["hrv"][1]:.0f})')
    if "sleep" in r:
        u = r["sleep"][1]
        parts.append(f'sleep {r["sleep"][0]:.1f} h' + (f' (usual {u:.1f})' if u else ''))
    return (f'<h2>Readiness</h2><p><b>{html.escape(r["label"])}</b><br><span class="dim">'
            f'{", ".join(parts)}. From Apple Health, against your last 4 weeks; a rough guide only.</span></p>')


def hr_section(w, hr_file, motions):
    """The whole workout's heart rate (the watch's file at Finish): a line over time with each
    recorded set shaded, the time spent in each range, and the highest moments with what was on."""
    if not hr_file or hr_file[1] is None or len(hr_file[1]) < 2:
        return ""
    meta, a = hr_file
    t = meta["start"] / 1000 + a[:, 0]
    bpm = a[:, 1]
    t0, t1 = w["start"] / 1000, max(t[-1], (w.get("end") or 0) / 1000)
    lo, hi = min(bpm.min(), 80), max(bpm.max(), 160)
    W, H = 900, 180
    x = lambda v: (v - t0) / max(1, t1 - t0) * W
    y = lambda v: H - (v - lo) / (hi - lo) * H
    # what was on at a moment: the set whose Start set..Done covers it, else the last Done before it
    sets = []
    for e in w["entries"]:
        for s in e["sets"]:
            if s.get("done") and s.get("at"):
                m = motions.get((w["id"], e["id"], round(s["at"])), ({}, None))[0]
                sets.append(((m.get("start") or s["at"]) / 1000, s["at"] / 1000, name_of(e["id"])))
    sets.sort()
    shade = "".join(f'<rect class="set" x="{x(a_):.1f}" y="0" width="{max(1.5, x(b) - x(a_)):.1f}" height="{H}"/>'
                    for a_, b, _ in sets)
    line = " ".join(f"{x(a_):.1f},{y(b):.1f}" for a_, b in zip(t, bpm))
    grid = "".join(f'<line class="grid" x1="0" x2="{W}" y1="{y(v):.1f}" y2="{y(v):.1f}"/>'
                   f'<text x="2" y="{y(v) - 3:.1f}">{v}</text>' for v in (100, 120, 140, 160) if lo < v < hi)
    svg = (f'<svg class="hr" viewBox="0 0 {W} {H}" preserveAspectRatio="none" role="img" '
           f'aria-label="Heart rate during the workout">{shade}{grid}<polyline points="{line}"/></svg>')
    dt = np.diff(t, append=t[-1])
    dt = np.minimum(dt, 30)  # a gap in the readings is not time at that rate
    bands = "".join(
        f'<div><b>{dt[(bpm >= a_) & (bpm < b)].sum() / 60:.0f} min</b>'
        f'{"under 100" if a_ == 0 else (f"{a_}+" if b == 999 else f"{a_}–{b}")} bpm</div>'
        for a_, b in BANDS)

    def doing(v):
        on = [n for a_, b, n in sets if a_ - 5 <= v <= b + 45]
        before = [n for a_, b, n in sets if b <= v]
        return on[-1] if on else (f"rest after {before[-1]}" if before else "warming up")
    peaks, used = [], []
    for i in np.argsort(-bpm):
        if all(abs(t[i] - u) > 120 for u in used):
            used.append(t[i]); peaks.append(i)
        if len(peaks) == 3:
            break
    top = "".join(f'<li>{datetime.fromtimestamp(t[i]):%H:%M} – {bpm[i]:.0f} bpm – {html.escape(doing(t[i]))}</li>'
                  for i in sorted(peaks, key=lambda i: t[i]))
    return (f'<h2>Heart rate</h2>{svg}<p class="dim">Shaded: from Start set to Done. '
            f'Average {bpm.mean():.0f}, highest {bpm.max():.0f} bpm.</p><div class="tiles">{bands}</div>'
            f'<p class="dim">Highest moments</p><ul>{top}</ul><h2>Sets</h2>')


def report(w, workouts, motions, hr_file=None):
    """One workout's page."""
    sets = []  # every done set in time order, for the real rest lengths
    for ei, e in enumerate(w["entries"]):
        for si, s in enumerate(e["sets"]):
            if s.get("done") and s.get("at"):
                sets.append((s["at"], ei, si))
    sets.sort()
    nxt = {}
    for (at, ei, si), (nat, nei, nsi) in zip(sets, sets[1:]):
        # when the next set began: its own start from the watch (startedAt), else its file's start
        nset = w["entries"][nei]["sets"][nsi]
        start = nset.get("startedAt") or motions.get((w["id"], w["entries"][nei]["id"], round(nat)), ({}, None))[0].get("start")
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
            meta, a = (motions.get((w["id"], e["id"], "set", si + 1, None))
                       or motions.get((w["id"], e["id"], round(s.get("at") or 0)), ({}, None)))
            m = motion_of(a)
            fd = from_detail(meta)
            if m and fd:  # the watch's own reps and speeds win over the Mac replay
                m = {**m, **{k: v for k, v in fd.items() if k != "loss"}, "loss": fd["loss"]}
            reps = s.get("r") or 0
            weight = s.get("w") or 0
            total_reps += reps
            vol += reps * weight
            counted = m["count"] if m else None
            watch = f'{counted}' if counted is not None else "–"
            if counted is not None and counted != reps:
                watch = f'<span class="off">{counted} ({counted - reps:+d})</span>'
            loss = "–" if not m or "loss" not in m else ("?" if m["loss"] is None else f'{m["loss"] * 100:.0f}%')
            if meta.get("checked") or s.get("checked"):
                watch += ' <span class="dim" title="reps checked on the watch">✓</span>'
            rir = s.get("rir")
            tempo_extra = f'<br><span class="dim">RIR {rir:g}</span>' if rir is not None else ""
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
                f'<td>{bars(m["speeds"]) if m else ""}</td><td>{loss}</td><td>{tempo}{tempo_extra}</td>'
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
    day = datetime.fromtimestamp(w["start"] / 1000).strftime("%Y-%m-%d")
    ready = readiness_html(readiness((hr_file[0] if hr_file else {}).get("daily"), day))
    return page(w.get("name") or "Workout", head + ready + hr_section(w, hr_file, motions) + table + notes)


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
.bars rect{fill:var(--accent)}h2{font-size:17px;margin:22px 0 8px}
svg.hr{width:100%;height:180px;display:block}svg.hr polyline{fill:none;stroke:#ff375f;stroke-width:1.5;vector-effect:non-scaling-stroke}
svg.hr .set{fill:var(--line)}svg.dbg{width:100%;height:150px;display:block;border:1px solid var(--line);border-radius:8px;font-size:10px}
svg.dbg .vl{fill:none;stroke:#ff375f;stroke-width:1;vector-effect:non-scaling-stroke}svg.dbg .tl{fill:none;stroke:#0a84ff;stroke-opacity:.5;stroke-width:1;vector-effect:non-scaling-stroke}
svg.hr .set{fill:var(--line)}svg.hr .grid{stroke:var(--line);vector-effect:non-scaling-stroke}svg.hr text{fill:var(--dim);font-size:11px}a{color:inherit}.wrap{overflow-x:auto}
"""


def page(title, body):
    return (f'<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{html.escape(title)}</title><style>{CSS}</style><div class="wrap">{body}</div></html>')


def body_part(ex_id):
    try:
        return json.load(open(os.path.join(ROOT, "catalogue", "exercises", f"{ex_id}.json")))["bodyPart"]
    except (OSError, ValueError, KeyError):
        return "other"


def week_of(ms):
    y, wk, _ = datetime.fromtimestamp(ms / 1000).isocalendar()
    return f"{y}-W{wk:02d}"


def week_numbers(ws, motions, hr_files):
    """One week's totals."""
    n = {"workouts": len(ws), "sets": 0, "reps": 0, "volume": 0.0, "parts": {}, "prs": [], "diffs": [],
         "rests": [], "hr": [], "hot": 0.0, "ready": [], "speed": {}}
    for w in ws:
        n["prs"] += [name_of(x) for x in (w.get("prs") or [])]
        for e in w["entries"]:
            for s in e["sets"]:
                if s.get("done"):
                    r, wt = s.get("r") or 0, s.get("w") or 0
                    n["sets"] += 1; n["reps"] += r; n["volume"] += r * wt
                    bp = body_part(e["id"]); n["parts"][bp] = n["parts"].get(bp, 0) + r * wt
        # sets logged live have a time: the watch's count, speed and real rest (imported ones do not)
        sets = sorted((s["at"], e["id"], s) for e in w["entries"] for s in e["sets"] if s.get("done") and s.get("at"))
        for (at, ex, s), nxt in zip(sets, sets[1:] + [None]):
            r, wt = s.get("r") or 0, s.get("w") or 0
            meta, a = motions.get((w["id"], ex, round(at)), ({}, None))
            if a is not None and r:
                m = motion_of(a)
                if m:
                    n["diffs"].append(m["count"] - r)
                    if m["speeds"]:
                        best = max(m["speeds"][:3])
                        key = (ex, wt)
                        n["speed"][key] = max(n["speed"].get(key, 0), best)
            if nxt:
                nm = motions.get((w["id"], nxt[1], round(nxt[0])), ({}, None))[0]
                gap = ((nm.get("start") or nxt[0]) - at) / 1000
                if 0 < gap < 900:
                    n["rests"].append(gap)
        hf = hr_files.get(w["id"])
        if hf and hf[1] is not None and len(hf[1]) > 1:
            b = hf[1][:, 1]; dt = np.minimum(np.diff(hf[1][:, 0], append=hf[1][-1, 0]), 30)
            n["hr"].append(float(b.mean())); n["hot"] += float(dt[b >= 140].sum()) / 60
            r = readiness(hf[0].get("daily"), datetime.fromtimestamp(w["start"] / 1000).strftime("%Y-%m-%d"))
            if r:
                n["ready"].append((datetime.fromtimestamp(w["start"] / 1000).strftime("%a"), r["label"]))
    return n


def weekly(week, n, prev, earlier_speed):
    def delta(a, b, fmt="{:+,.0f}"):
        return f' <span class="dim">({fmt.format(a - b)})</span>' if prev else ""
    tiles = (f'<div class="tiles"><div><b>{n["workouts"]}</b>workouts{delta(n["workouts"], prev["workouts"] if prev else 0)}</div>'
             f'<div><b>{n["sets"]}</b>sets{delta(n["sets"], prev["sets"] if prev else 0)}</div>'
             f'<div><b>{n["reps"]:,.0f}</b>reps</div><div><b>{n["volume"]:,.0f}</b>kg volume'
             f'{delta(n["volume"], prev["volume"] if prev else 0)}</div></div>')
    total = sum(n["parts"].values()) or 1
    parts = "".join(f'<tr><td>{html.escape(k.title())}</td><td>{v:,.0f} kg</td><td>{v / total * 100:.0f}%</td></tr>'
                    for k, v in sorted(n["parts"].items(), key=lambda kv: -kv[1]))
    out = f'<h1>Week {week}</h1>{tiles}<h2>Volume by body part</h2><table>{parts}</table>'
    if n["prs"]:
        out += '<h2>New records</h2><ul>' + "".join(f'<li>{html.escape(x)}</li>' for x in n["prs"]) + '</ul>'
    sp = []
    for (ex, wt), v in sorted(n["speed"].items()):
        before = earlier_speed.get((ex, wt))
        if before:
            sp.append(f'<tr><td>{html.escape(name_of(ex))}</td><td>{wt:g}</td><td>{(v / before - 1) * 100:+.0f}%</td></tr>')
    if sp:
        out += ('<h2>Speed at the same weight</h2><p class="dim">Best of the first reps, against the best '
                'before this week at that weight. Faster at the same weight: stronger.</p><table>' + "".join(sp) + '</table>')
    if n["rests"]:
        out += f'<h2>Rest</h2><p>Median {np.median(n["rests"]) / 60:.1f} min between sets (from Done to the next Start set).</p>'
    if n["hr"]:
        out += (f'<h2>Heart rate</h2><p>Average {np.mean(n["hr"]):.0f} bpm in workouts, '
                f'{n["hot"]:.0f} min at 140 bpm or more.</p>')
    if n["ready"]:
        out += '<h2>Readiness</h2><ul>' + "".join(f'<li>{d}: {html.escape(l)}</li>' for d, l in n["ready"]) + '</ul>'
    if n["diffs"]:
        d = np.array(n["diffs"])
        out += (f'<h2>Rep counter</h2><p>{len(d)} sets: {np.mean(d == 0) * 100:.0f}% exact, '
                f'{np.mean(np.abs(d) <= 1) * 100:.0f}% within one rep (against the reps you logged).</p>')
    return page(f"Week {week}", out)


def debug_timeline(meta, a):
    """One set as a picture: the speed counter's velocity (red) and the wrist's tilt (blue), the
    watch's reps as it counted them (from the set file's log: green speed, blue tilt, purple both),
    hand edits (orange) and the end (grey), and today's code's reps on the Mac (black ticks below)."""
    c = RepCounter2()
    xs = []
    for i in range(len(a)):
        c.push(a[i, 0], a[i, 1:4], a[i, 7:10])
        xs.append(float(c.vs @ c.axis))
    t = a[:, 0]
    g = a[:, 7:10] - a[:, 7:10].mean(0)
    with np.errstate(all="ignore"):
        u = np.linalg.svd(g, full_matrices=False)[2][0]
        tilt = np.nan_to_num(g @ u)
    W, H = 900, 150
    T = max(t[-1], 1)
    x = lambda v: v / T * W
    def line(v, cls):
        top = max(np.abs(v).max(), 1e-6)
        pts = " ".join(f"{x(a_):.1f},{H / 2 - b / top * (H / 2 - 12):.1f}" for a_, b in zip(t[::2], np.asarray(v)[::2]))
        return f'<polyline class="{cls}" points="{pts}"/>'
    marks = ""
    colors = {"speed": "#30d158", "tilt": "#0a84ff", "both": "#bf5af2"}
    for at, what in (meta.get("helpers") or {}).get("log", []):
        w = str(what)
        if w.startswith("rep "):
            col = colors.get(w.split()[-1], "#888")
            marks += f'<line x1="{x(at):.1f}" x2="{x(at):.1f}" y1="0" y2="{H - 14}" stroke="{col}" stroke-width="2"><title>{html.escape(w)} at {at}s</title></line>'
        else:
            col = "#ff9f0a" if w.startswith("edit") else "#8e8e93"
            marks += (f'<line x1="{x(at):.1f}" x2="{x(at):.1f}" y1="0" y2="{H}" stroke="{col}" stroke-dasharray="3 3"/>'
                      f'<text x="{x(at) + 2:.1f}" y="10" fill="{col}">{html.escape(w)}</text>')
    mac = "".join(f'<line x1="{x(e):.1f}" x2="{x(e):.1f}" y1="{H - 10}" y2="{H}" stroke="currentColor" stroke-width="2"/>' for e in c.events)
    return (f'<svg class="dbg" viewBox="0 0 {W} {H}" preserveAspectRatio="none">{line(tilt, "tl")}{line(xs, "vl")}{marks}{mac}</svg>'
            f'<p class="dim">{T:.0f} s. Mac replay: speed {c.reps}.</p>')


def debug_page(rows):
    """Every recorded set: what the watch counted against the reps logged (on the watch at Done, and
    in the end on the server, where the iPhone may have changed them), worst first."""
    body = ('<h1>Rep counter debug</h1><p class="dim">Watch: what the counter said. At Done: the reps '
            'sent from the watch (after any crown edit). Logged: the reps in the workout now. Sets '
            'with a difference first; each with its timeline: red velocity, blue tilt; watch reps as '
            'green (speed), blue (tilt), purple (both); orange: your edits; grey: the end; black '
            'ticks below: the Mac replay of today\'s code.</p>')
    rows.sort(key=lambda r: (-abs(r["diff"]) if r["diff"] is not None else 1, -r["start"]))
    for r in rows:
        d = "–" if r["diff"] is None else f'{r["diff"]:+d}'
        body += (f'<h2>{datetime.fromtimestamp(r["start"] / 1000):%d %b %H:%M} · {html.escape(r["name"])} · '
                 f'set {r["set"]}</h2><p>Watch {r["auto"] if r["auto"] is not None else "–"} · at Done '
                 f'{r["done"]} · logged {r["logged"] if r["logged"] is not None else "–"} · '
                 f'<b>difference {d}</b></p>{r["svg"]}')
    return page("Rep counter debug", body)


def main():
    every = "--all" in sys.argv
    if "--install-watch" in sys.argv:
        return install_watch()
    out_dir = os.path.join(DATA, "reports")
    os.makedirs(out_dir, exist_ok=True)
    made = 0
    links, week_links = [], []
    for state_file in sorted(glob.glob(os.path.join(DATA, "state-*.json"))):
        uid = os.path.basename(state_file)[6:-5]
        s = json.load(open(state_file, encoding="utf-8"))
        s = s.get("state", s)
        workouts = sorted([w for w in s.get("workouts", []) if w.get("start")], key=lambda w: w["start"])
        motions = {}
        hr_files = {}
        latest = {}
        for f in glob.glob(os.path.join(DATA, "motion", uid, "*.csv")):
            if "_synclog_" in f or "_watchlog_" in f:
                continue  # the sync logs (lib/sync-log.js, the watch's), read by hand
            try:
                meta, a = load_csv(f)
            except (OSError, ValueError):
                continue
            if meta.get("kind") == "hr":
                hr_files[meta.get("wid")] = (meta, a)
            elif meta.get("wid") and meta.get("end"):
                # one file per set (and side): the set number, not the time, joins it to the
                # workout, as the phone may move a set's time (edited, ticked again)
                key = (meta["wid"], meta.get("exId"), meta.get("set"), meta.get("side"))
                if key in latest and latest[key][0] >= meta["end"]:
                    continue  # an older file of a set done again: the newer one is the set
                if key in latest:
                    motions.pop(latest[key][1], None)
                k = (meta["wid"], meta.get("exId"), round(meta["end"]))
                latest[key] = (meta["end"], k)
                motions[k] = (meta, a)
        # the same files by set number, for the workout pages (set numbers count from 1)
        for (wid, ex, sn, side), (_, k) in latest.items():
            if k in motions and sn is not None:
                motions[(wid, ex, "set", int(sn), side)] = motions[k]
        dbg = []
        logged = {}
        for w in workouts:
            for e in w["entries"]:
                for si, st in enumerate(e["sets"]):
                    if st.get("done"):
                        logged[(w["id"], e["id"], si + 1)] = st.get("r")
        for key, (meta, a) in motions.items():
            if len(key) != 3:
                continue  # the same file again, by set number
            wid, ex, end = key
            # under 3 s: Start then Done at once, nothing to learn from
            if a is None or len(a) < 150 or meta.get("auto") is None:
                continue
            lg = logged.get((wid, ex, meta.get("set")))
            truth = lg if lg is not None else meta.get("reps")
            dbg.append({"start": meta.get("start") or end, "name": name_of(ex), "set": meta.get("set"),
                        "auto": meta.get("auto"), "done": meta.get("reps"), "logged": lg,
                        "diff": None if truth is None else int(meta["auto"] - truth), "svg": debug_timeline(meta, a)})
        with open(os.path.join(out_dir, "debug.html"), "w", encoding="utf-8") as f:
            f.write(debug_page(dbg))
        newest = max([os.path.getmtime(state_file)] + [os.path.getmtime(f) for f in glob.glob(os.path.join(DATA, "motion", uid, "*.csv"))])
        for w in workouts:
            name = datetime.fromtimestamp(w["start"] / 1000).strftime("%Y-%m-%d-%H%M") + f'-{w["id"]}.html'
            path = os.path.join(out_dir, name)
            links.append((w["start"], name, w.get("name") or "Workout"))
            if every or not os.path.exists(path) or os.path.getmtime(path) < newest:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(report(w, workouts, motions, hr_files.get(w["id"])))
                made += 1
        # one page per week, the weeks with workouts; the speed "before" grows week by week
        weeks = {}
        for w in workouts:
            weeks.setdefault(week_of(w["start"]), []).append(w)
        prev, earlier = None, {}
        for wk in sorted(weeks):
            n = week_numbers(weeks[wk], motions, hr_files)
            with open(os.path.join(out_dir, f"week-{wk}.html"), "w", encoding="utf-8") as f:
                f.write(weekly(wk, n, prev, earlier))
            week_links.append(wk)
            for k, v in n["speed"].items():
                earlier[k] = max(earlier.get(k, 0), v)
            prev = n
    items = "".join(f'<li><a href="{n}">{datetime.fromtimestamp(t / 1000):%a %d %b %Y}</a> – {html.escape(x)}</li>'
                    for t, n, x in sorted(links, reverse=True))
    wk_items = "".join(f'<li><a href="week-{w}.html">Week {w}</a></li>' for w in sorted(set(week_links), reverse=True))
    with open(os.path.join(out_dir, "index.html"), "w", encoding="utf-8") as f:
        f.write(page("Workouts", f'<p><a href="debug.html">Rep counter debug</a></p><h1>Weeks</h1><ul>{wk_items}</ul><h1>Workouts</h1><ul>{items}</ul>'))
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
